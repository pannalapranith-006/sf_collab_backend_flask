"""
app/routes/drive_file_relation_routes.py
All endpoints for linking DriveFiles to execution objects.
"""

from flask import Blueprint, abort, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.drive_file import DriveFile
from app.models.drive_file_relation import ENTITY_TYPES, RELATION_TYPES, DriveFileRelation
from app.utils.response_helpers import success_response, error_response
from app.services.drive_event_service import emit_event

drive_file_relation_bp = Blueprint(
    "drive_file_relation",
    __name__,
    url_prefix="/api/drive",
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe_int(value, field_name="value"):
    """Return an integer or raise ValueError with a clear message."""
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f"'{field_name}' must be a valid integer, got: {value!r}")


def _get_live_file(file_id):
    """Return a non-deleted DriveFile or abort with 404."""
    f = DriveFile.query.get_or_404(file_id)
    if f.state == "deleted":
        abort(404, description="File not found")
    return f


def _sync_denorm(file, relation_type, entity_id_val, *, add: bool):
    """
    Keep the denormalised fields on DriveFile in sync with the relation table.
    """
    array_map = {
        "milestone": "linked_milestone_ids",
        "task": "linked_task_ids",
        "crm_entity": "linked_crm_entity_ids",
    }
    single_map = {
        "meeting": "linked_meeting_id",
        "marketplace_listing": "linked_marketplace_listing_id",
        "dispute_case": "linked_dispute_case_id",
        "wallet_transaction": "linked_wallet_transaction_id",
        "vision": "linked_vision_id",
    }

    if relation_type in array_map:
        field = array_map[relation_type]
        current = list(getattr(file, field) or [])
        if add:
            if entity_id_val not in current:
                current.append(entity_id_val)
        else:
            current = [x for x in current if x != entity_id_val]
        setattr(file, field, current)

    elif relation_type in single_map:
        field = single_map[relation_type]
        setattr(file, field, entity_id_val if add else None)


# ── File-centric routes ──────────────────────────────────────────────────────
@drive_file_relation_bp.post("/files/<int:file_id>/links")
@jwt_required()
def create_link(file_id):
    # TODO: permission check
    current_user_id = int(get_jwt_identity())
    file = _get_live_file(file_id)

    body = request.get_json(silent=True) or {}

    for field in ("relation_type", "related_entity_id", "related_entity_type"):
        if not body.get(field):
            return error_response(f"'{field}' is required", 400)

    relation_type = body["relation_type"]
    if relation_type not in RELATION_TYPES:
        return error_response(f"Invalid relation_type '{relation_type}'. Allowed: {list(RELATION_TYPES)}", 400)

    entity_type = body["related_entity_type"]
    if entity_type not in ENTITY_TYPES:
        return error_response(f"Invalid related_entity_type '{entity_type}'. Allowed: {list(ENTITY_TYPES)}", 400)

    try:
        entity_id = _safe_int(body["related_entity_id"], "related_entity_id")
        creator_id = _safe_int(body.get("created_by_user_id"), "created_by_user_id")
    except ValueError as exc:
        return error_response(str(exc), 400)

    existing = DriveFileRelation.query.filter_by(
        file_id=file_id,
        relation_type=relation_type,
        related_entity_id=entity_id,
    ).first()
    if existing:
        return error_response("This link already exists.", 409)

    relation = DriveFileRelation(
        file_id=file_id,
        relation_type=relation_type,
        related_entity_id=entity_id,
        related_entity_type=entity_type,
        related_entity_label=body.get("related_entity_label"),
        created_by_user_id=creator_id,
    )
    db.session.add(relation)
    _sync_denorm(file, relation_type, entity_id, add=True)
    
    db.session.commit()

    emit_event("file_linked_to_entity", file_id, current_user_id, event_metadata={
    "relation_type": relation_type,
    "related_entity_id": entity_id,
    "related_entity_type": entity_type
    })

    return success_response(relation.to_dict(), 201)


@drive_file_relation_bp.get("/files/<int:file_id>/links")
@jwt_required()
def list_links(file_id):
    current_user_id = int(get_jwt_identity())
    file = _get_live_file(file_id)

    q = DriveFileRelation.query.filter_by(file_id=file_id)

    if rtype := request.args.get("relation_type"):
        if rtype not in RELATION_TYPES:
            return error_response(f"Invalid relation_type: {rtype}", 400)
        q = q.filter_by(relation_type=rtype)

    relations = q.order_by(DriveFileRelation.created_at.desc()).all()
    return success_response({
        "file_id": file_id,
        "count": len(relations),
        "relations": [r.to_dict() for r in relations],
    })


@drive_file_relation_bp.delete("/files/<int:file_id>/links/<int:relation_id>")
@jwt_required()
def delete_link(file_id, relation_id):
    current_user_id = int(get_jwt_identity())
    file = _get_live_file(file_id)

    relation = DriveFileRelation.query.filter_by(
        id=relation_id, file_id=file_id
    ).first_or_404()

    _sync_denorm(file, relation.relation_type, relation.related_entity_id, add=False)
    db.session.delete(relation)
    db.session.commit()
    emit_event("file_unlinked_from_entity", file_id, current_user_id, event_metadata={
        "relation_type": relation.relation_type,
        "related_entity_id": relation.related_entity_id,
        "related_entity_type": relation.related_entity_type
    })

    return success_response({"message": "Link removed", "relation_id": relation_id})


@drive_file_relation_bp.delete("/files/<int:file_id>/links")
@jwt_required()
def delete_link_by_entity(file_id):
    current_user_id = int(get_jwt_identity())
    file = _get_live_file(file_id)

    body = request.get_json(silent=True) or {}
    for field in ("relation_type", "related_entity_id"):
        if not body.get(field):
            return error_response(f"'{field}' is required", 400)

    try:
        entity_id = _safe_int(body["related_entity_id"], "related_entity_id")
    except ValueError as exc:
        return error_response(str(exc), 400)

    relation = DriveFileRelation.query.filter_by(
        file_id=file_id,
        relation_type=body["relation_type"],
        related_entity_id=entity_id,
    ).first_or_404()

    _sync_denorm(file, relation.relation_type, entity_id, add=False)
    db.session.delete(relation)
    db.session.commit()
    
    emit_event("file_unlinked_from_entity", file_id, current_user_id, event_metadata={
        "relation_type": relation.relation_type,
        "related_entity_id": relation.related_entity_id,
        "related_entity_type": relation.related_entity_type
    })

    return success_response({"message": "Link removed"})


# ── Reverse-lookup route ─────────────────────────────────────────────────────
@drive_file_relation_bp.get("/links/by-entity")
@jwt_required()
def files_by_entity():
    current_user_id = int(get_jwt_identity())

    entity_type = request.args.get("entity_type")
    entity_id_raw = request.args.get("entity_id")

    if not entity_type or not entity_id_raw:
        return error_response("'entity_type' and 'entity_id' are required", 400)
    if entity_type not in ENTITY_TYPES:
        return error_response(f"Invalid entity_type: {entity_type}", 400)

    try:
        entity_id = _safe_int(entity_id_raw, "entity_id")
    except ValueError as exc:
        return error_response(str(exc), 400)

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    state_filter = request.args.get("state")

    q = (
        db.session.query(DriveFile)
        .join(DriveFileRelation, DriveFileRelation.file_id == DriveFile.id)
        .filter(
            DriveFileRelation.related_entity_type == entity_type,
            DriveFileRelation.related_entity_id == entity_id,
            DriveFile.state != "deleted",
        )
    )
    if state_filter:
        q = q.filter(DriveFile.state == state_filter)

    pagination = q.order_by(DriveFile.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return success_response({
        "entity_type": entity_type,
        "entity_id": entity_id,
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": per_page,
        "items": [f.to_dict() for f in pagination.items],
    })


# ── Bulk link route ───────────────────────────────────────────────────────────
@drive_file_relation_bp.post("/files/<int:file_id>/links/bulk")
@jwt_required()
def bulk_create_links(file_id):
    current_user_id = int(get_jwt_identity())
    file = _get_live_file(file_id)

    body = request.get_json(silent=True) or {}
    links = body.get("links")
    if not isinstance(links, list) or not links:
        return error_response("'links' must be a non-empty list", 400)

    try:
        creator_id = _safe_int(body.get("created_by_user_id"), "created_by_user_id")
    except ValueError as exc:
        return error_response(str(exc), 400)

    # ── Pass 1: validate everything ───────────────────────────────────────────
    to_insert = []   # list of (DriveFileRelation, relation_type, entity_id_val)
    skipped = []

    for i, item in enumerate(links):
        rtype = item.get("relation_type")
        etype = item.get("related_entity_type")
        eid_raw = item.get("related_entity_id")

        if not rtype or not etype or not eid_raw:
            skipped.append({"index": i, "reason": "missing required fields"})
            continue
        if rtype not in RELATION_TYPES:
            skipped.append({"index": i, "reason": f"invalid relation_type: {rtype}"})
            continue
        if etype not in ENTITY_TYPES:
            skipped.append({"index": i, "reason": f"invalid related_entity_type: {etype}"})
            continue

        try:
            eid = _safe_int(eid_raw, "related_entity_id")
        except ValueError as exc:
            skipped.append({"index": i, "reason": str(exc)})
            continue

        existing = DriveFileRelation.query.filter_by(
            file_id=file_id,
            relation_type=rtype,
            related_entity_id=eid,
        ).first()
        if existing:
            skipped.append({"index": i, "reason": "already exists", "relation_id": existing.id})
            continue

        relation = DriveFileRelation(
            file_id=file_id,
            relation_type=rtype,
            related_entity_id=eid,
            related_entity_type=etype,
            related_entity_label=item.get("related_entity_label"),
            created_by_user_id=creator_id,
        )
        to_insert.append((relation, rtype, eid))

    # ── Pass 2: stage and commit ──────────────────────────────────────────────
    try:
        for relation, rtype, eid in to_insert:
            db.session.add(relation)
            _sync_denorm(file, rtype, eid, add=True)

        db.session.commit()

        for relation, rtype, eid in to_insert:
            emit_event("file_linked_to_entity", file_id, current_user_id, event_metadata={
                "relation_type": rtype,
                "related_entity_id": eid,
                "related_entity_type": relation.related_entity_type
            })
            
    except SQLAlchemyError as exc:
        db.session.rollback()
        return error_response(
            f"Database error — no links were created. {exc}", 500
        )

    return success_response({
        "created": [r.to_dict() for r, _, _ in to_insert],
        "skipped": skipped,
    }, 201)