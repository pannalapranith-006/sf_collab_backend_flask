"""
app/routes/drive_file_relation_routes.py
Endpoints for linking DriveFiles to execution objects (milestones, tasks, meetings, etc.).
"""

from flask import Blueprint, abort, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.drive_file import DriveFile
from app.models.drive_file_relation import DriveFileRelation, RELATION_TYPES, ENTITY_TYPES
from app.utils.response_helpers import success_response, error_response
from app.services.drive_event_service import emit_event

drive_file_relation_bp = Blueprint('drive_file_relations', __name__, url_prefix='/api/drive')

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _safe_int(value, field_name="value"):
    """Convert value to int or raise a clear error."""
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f"'{field_name}' must be a valid integer, got: {value!r}")


def _get_live_file(file_id):
    """Fetch a non‑deleted DriveFile or abort 404."""
    f = DriveFile.query.get_or_404(file_id)
    if f.state == "deleted":
        abort(404, description="File not found")
    return f


def _sync_denorm(file, relation_type, entity_id_val, add: bool):
    """Keep denormalised linkage fields on DriveFile in sync."""
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


def _relation_metadata(relation):
    """Standardised metadata dict for audit events."""
    return {
        "relation_type": relation.relation_type,
        "related_entity_id": relation.related_entity_id,
        "related_entity_type": relation.related_entity_type,
    }


def _validate_relation_body(body, require_entity_type=True):
    """
    Validate the common fields of a relation request.
    Returns (error_response, relation_type, entity_type, entity_id, creator_id).
    If validation fails, the first element is a Flask response.
    """
    required = ["relation_type", "related_entity_id"]
    if require_entity_type:
        required.append("related_entity_type")

    for field in required:
        if not body.get(field):
            return (
                error_response(f"'{field}' is required", 400),
                None, None, None, None,
            )

    relation_type = body["relation_type"]
    if relation_type not in RELATION_TYPES:
        return (
            error_response(f"Invalid relation_type '{relation_type}'", 400),
            None, None, None, None,
        )

    entity_type = None
    if require_entity_type:
        entity_type = body.get("related_entity_type")
        if entity_type not in ENTITY_TYPES:
            return (
                error_response(f"Invalid related_entity_type '{entity_type}'", 400),
                None, None, None, None,
            )

    try:
        entity_id = _safe_int(body["related_entity_id"], "related_entity_id")
        creator_id = _safe_int(body.get("created_by_user_id"), "created_by_user_id")
    except ValueError as exc:
        return (
            error_response(str(exc), 400),
            None, None, None, None,
        )

    return (None, relation_type, entity_type, entity_id, creator_id)


def _remove_relation(file, relation, current_user_id):
    """Shared logic for deleting a relation and syncing denorm fields."""
    _sync_denorm(file, relation.relation_type, relation.related_entity_id, add=False)
    db.session.delete(relation)
    db.session.commit()
    emit_event(
        "file_unlinked_from_entity",
        file.file_id,
        current_user_id,
        metadata=_relation_metadata(relation),
    )


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------

@drive_file_relation_bp.post("/files/<int:file_id>/links")
@jwt_required()
def create_link(file_id):
    """Create a relation between a file and an external entity."""
    current_user_id = int(get_jwt_identity())
    file = _get_live_file(file_id)
    body = request.get_json(silent=True) or {}

    err, relation_type, entity_type, entity_id, creator_id = _validate_relation_body(
        body, require_entity_type=True
    )
    if err:
        return err

    # Duplicate check
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

    emit_event(
        "file_linked_to_entity",
        file_id,
        current_user_id,
        metadata=_relation_metadata(relation),
    )
    return success_response(relation.to_dict(), 201)


@drive_file_relation_bp.get("/files/<int:file_id>/links")
@jwt_required()
def list_links(file_id):
    """Return all relations for a file, optionally filtered by type."""
    _get_live_file(file_id)
    q = DriveFileRelation.query.filter_by(file_id=file_id)

    rtype = request.args.get("relation_type")
    if rtype:
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
    """Delete a single relation by its ID."""
    current_user_id = int(get_jwt_identity())
    file = _get_live_file(file_id)
    relation = DriveFileRelation.query.filter_by(
        id=relation_id, file_id=file_id
    ).first_or_404()

    _remove_relation(file, relation, current_user_id)
    return success_response({"message": "Link removed", "relation_id": relation_id})


@drive_file_relation_bp.delete("/files/<int:file_id>/links")
@jwt_required()
def delete_link_by_entity(file_id):
    """
    Delete a relation by specifying the entity details (instead of relation ID).
    Body: { "relation_type": "...", "related_entity_id": <int> }
    """
    current_user_id = int(get_jwt_identity())
    file = _get_live_file(file_id)
    body = request.get_json(silent=True) or {}

    err, relation_type, _, entity_id, _ = _validate_relation_body(
        body, require_entity_type=False   # entity_type not needed for deletion lookup
    )
    if err:
        return err

    relation = DriveFileRelation.query.filter_by(
        file_id=file_id,
        relation_type=relation_type,
        related_entity_id=entity_id,
    ).first_or_404()

    _remove_relation(file, relation, current_user_id)
    return success_response({"message": "Link removed"})


# ----------------------------------------------------------------------
# Reverse lookup
# ----------------------------------------------------------------------

@drive_file_relation_bp.get("/links/by-entity")
@jwt_required()
def files_by_entity():
    """Return all files linked to a given entity (e.g., a milestone)."""
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

    base_query = (
        db.session.query(DriveFile)
        .join(DriveFileRelation, DriveFileRelation.file_id == DriveFile.file_id)
        .filter(
            DriveFileRelation.related_entity_type == entity_type,
            DriveFileRelation.related_entity_id == entity_id,
            DriveFile.state != "deleted",
        )
    )
    pagination = base_query.order_by(DriveFile.updated_at.desc()).paginate(
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
