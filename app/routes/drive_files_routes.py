from datetime import datetime
from flask import Blueprint, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.drive_file import DriveFile
from app.services.drive_storage_service import (
    StorageError,
    delete_from_storage,
    open_for_download,
    save_upload,
)
from app.utils.drive_lifecycle import validate_transition
from app.utils.response_helpers import success_response, error_response
from app.services.drive_event_service import emit_event

drive_file_bp = Blueprint("drive_file", __name__, url_prefix="/api/drive/files")

# ── Helpers ───────────────────────────────────────────────────────────────────
ALLOWED_VISIBILITY = (
    "private", "shared-with-specific-users", "startup-members",
    "organization-members", "public-link", "marketplace-customer",
    "mentor-visible", "advisor-visible", "finance-team-only", "legal-team-only",
)

ALLOWED_SENSITIVITY = ("public", "internal", "restricted", "confidential")
VALID_STATES = ["uploaded", "active", "archived", "deleted"]


def _safe_int(value, field_name="value"):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f"'{field_name}' must be a valid integer, got: {value!r}")


def _build_filter_query(args):
    """Build a DriveFile query from common query-string filters."""
    q = DriveFile.query.filter(DriveFile.state != "deleted")

    if startup_id := args.get("startup_id"):
        q = q.filter_by(startup_id=_safe_int(startup_id, "startup_id"))
    if workspace_id := args.get("workspace_id"):
        q = q.filter_by(workspace_id=_safe_int(workspace_id, "workspace_id"))
    if organization_id := args.get("organization_id"):
        q = q.filter_by(organization_id=_safe_int(organization_id, "organization_id"))
    if owner_user_id := args.get("owner_user_id"):
        q = q.filter_by(owner_user_id=_safe_int(owner_user_id, "owner_user_id"))
    if state := args.get("state"):
        q = q.filter_by(state=state)
    if knowledge_type := args.get("knowledge_type"):
        q = q.filter_by(knowledge_type=knowledge_type)
    if visibility_scope := args.get("visibility_scope"):
        q = q.filter_by(visibility_scope=visibility_scope)
    if parent_folder_id := args.get("parent_folder_id"):
        q = q.filter_by(parent_folder_id=_safe_int(parent_folder_id, "parent_folder_id"))

    return q


# ── Routes ────────────────────────────────────────────────────────────────────

@drive_file_bp.post("/upload")
@jwt_required()
def upload_file():
    current_user_id = int(get_jwt_identity())

    for field in ("owner_scope_type", "owner_scope_id"):
        if not request.form.get(field):
            return error_response(f"'{field}' is required", 400)

    if "file" not in request.files or request.files["file"].filename == "":
        return error_response("'file' is required and must not be empty", 400)

    upload = request.files["file"]
    owner_scope_type = request.form["owner_scope_type"]
    owner_scope_id_raw = request.form["owner_scope_id"]

    try:
        owner_scope_id = _safe_int(owner_scope_id_raw, "owner_scope_id")
    except ValueError as e:
        return error_response(str(e), 400)

    vis = request.form.get("visibility_scope", "private")
    sens = request.form.get("sensitivity_level", "internal")

    if vis not in ALLOWED_VISIBILITY:
        return error_response(f"Invalid visibility_scope: {vis}", 400)
    if sens not in ALLOWED_SENSITIVITY:
        return error_response(f"Invalid sensitivity_level: {sens}", 400)

    try:
        stored = save_upload(
            file_stream=upload.stream,
            original_filename=upload.filename,
            declared_mime=upload.content_type,
            owner_scope_type=owner_scope_type,
            owner_scope_id=str(owner_scope_id),
        )
    except StorageError as exc:
        return error_response(str(exc), exc.status_code)

    import json as _json
    tags_raw = request.form.get("tags_json", "[]")
    try:
        tags = _json.loads(tags_raw)
        if not isinstance(tags, list):
            raise ValueError
    except (ValueError, TypeError):
        return error_response("'tags_json' must be a JSON-encoded list", 400)

    drive_file = DriveFile(
        filename=upload.filename,
        extension=stored["extension"],
        mime_type=stored["mime_type"],
        size_bytes=stored["size_bytes"],
        storage_key=stored["storage_key"],
        checksum=stored["checksum"],
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
        owner_user_id=_safe_int(request.form.get("owner_user_id")),
        workspace_id=_safe_int(request.form.get("workspace_id")),
        startup_id=_safe_int(request.form.get("startup_id")),
        organization_id=_safe_int(request.form.get("organization_id")),
        parent_folder_id=_safe_int(request.form.get("parent_folder_id")),
        visibility_scope=vis,
        sensitivity_level=sens,
        document_type=request.form.get("document_type"),
        knowledge_type=request.form.get("knowledge_type"),
        state="uploaded",
        tags_json=tags,
        uploaded_at=datetime.utcnow(),
    )

    db.session.add(drive_file)
    db.session.flush()

    db.session.commit()

    emit_event("file_uploaded", drive_file.id, current_user_id, event_metadata={"filename": drive_file.filename})

    return success_response(drive_file.to_dict(), 201)


@drive_file_bp.get("/<int:file_id>/download")
@jwt_required()
def download_file(file_id):
    current_user_id = int(get_jwt_identity())

    drive_file = DriveFile.query.get_or_404(file_id)

    if drive_file.state == "deleted":
        return error_response("File not found", 404)

    if not drive_file.storage_key:
        return error_response("No stored binary found for this file record", 404)

    try:
        fh = open_for_download(drive_file.storage_key)
    except StorageError as exc:
        return error_response(str(exc), exc.status_code)

    inline = request.args.get("inline", "false").lower() == "true"

    return send_file(
        fh,
        mimetype=drive_file.mime_type or "application/octet-stream",
        as_attachment=not inline,
        download_name=drive_file.filename,
    )


@drive_file_bp.post("/")
@jwt_required()
def create_file():
    current_user_id = int(get_jwt_identity())
    body = request.get_json(silent=True) or {}

    for field in ("filename", "owner_scope_type", "owner_scope_id"):
        if not body.get(field):
            return error_response(f"'{field}' is required", 400)

    if body.get("visibility_scope") and body["visibility_scope"] not in ALLOWED_VISIBILITY:
        return error_response(f"Invalid visibility_scope: {body['visibility_scope']}", 400)
    if body.get("sensitivity_level") and body["sensitivity_level"] not in ALLOWED_SENSITIVITY:
        return error_response(f"Invalid sensitivity_level: {body['sensitivity_level']}", 400)

    try:
        owner_scope_id = _safe_int(body["owner_scope_id"], "owner_scope_id")
    except ValueError as e:
        return error_response(str(e), 400)

    file = DriveFile(
        filename=body["filename"],
        owner_scope_type=body["owner_scope_type"],
        owner_scope_id=owner_scope_id,
        extension=body.get("extension"),
        mime_type=body.get("mime_type"),
        size_bytes=body.get("size_bytes"),
        storage_key=body.get("storage_key"),
        checksum=body.get("checksum"),
        workspace_id=_safe_int(body.get("workspace_id")),
        startup_id=_safe_int(body.get("startup_id")),
        organization_id=_safe_int(body.get("organization_id")),
        parent_folder_id=_safe_int(body.get("parent_folder_id")),
        owner_user_id=_safe_int(body.get("owner_user_id")),
        visibility_scope=body.get("visibility_scope", "private"),
        sensitivity_level=body.get("sensitivity_level", "internal"),
        document_type=body.get("document_type"),
        knowledge_type=body.get("knowledge_type"),
        state="uploaded",
        tags_json=body.get("tags_json", []),
        uploaded_at=datetime.utcnow(),
        linked_vision_id=_safe_int(body.get("linked_vision_id")),
        linked_milestone_ids=body.get("linked_milestone_ids", []),
        linked_task_ids=body.get("linked_task_ids", []),
        linked_meeting_id=_safe_int(body.get("linked_meeting_id")),
        linked_crm_entity_ids=body.get("linked_crm_entity_ids", []),
        linked_marketplace_listing_id=_safe_int(body.get("linked_marketplace_listing_id")),
        linked_dispute_case_id=_safe_int(body.get("linked_dispute_case_id")),
        linked_wallet_transaction_id=_safe_int(body.get("linked_wallet_transaction_id")),
    )

    db.session.add(file)
    db.session.commit()
    emit_event("file_created", file.id, current_user_id)
    return success_response(file.to_dict(), 201)


@drive_file_bp.get("/")
@jwt_required()
def list_files():
    current_user_id = int(get_jwt_identity())
    try:
        q = _build_filter_query(request.args)
    except ValueError as e:
        return error_response(str(e), 400)

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    pagination = q.order_by(DriveFile.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return success_response({
        "items": [f.to_dict() for f in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": per_page,
    })


@drive_file_bp.get("/<int:file_id>")
@jwt_required()
def get_file(file_id):
    current_user_id = int(get_jwt_identity())
    file = DriveFile.query.get_or_404(file_id)
    if file.state == "deleted":
        return error_response("File not found", 404)

    include_ai = request.args.get("include_ai", "false").lower() == "true"
    return success_response(file.to_dict(include_ai=include_ai))


@drive_file_bp.patch("/<int:file_id>")
@jwt_required()
def update_file_metadata(file_id):
    current_user_id = int(get_jwt_identity())
    file = DriveFile.query.get_or_404(file_id)
    if file.state == "deleted":
        return error_response("File not found", 404)

    body = request.get_json(silent=True) or {}

    mutable_fields = (
        "extension", "mime_type", "document_type", "knowledge_type",
        "visibility_scope", "sensitivity_level", "tags_json",
        "parent_folder_id", "summary_short", "summary_long",
        "key_entities_json", "semantic_topics_json",
        "decision_markers_json", "risk_markers_json",
        "freshness_score", "canonicality_score",
        "linked_vision_id", "linked_milestone_ids", "linked_task_ids",
        "linked_meeting_id", "linked_crm_entity_ids",
        "linked_marketplace_listing_id", "linked_dispute_case_id",
        "linked_wallet_transaction_id",
    )

    int_fields = (
        "parent_folder_id", "linked_vision_id", "linked_meeting_id",
        "linked_marketplace_listing_id", "linked_dispute_case_id",
        "linked_wallet_transaction_id",
    )

    for field in mutable_fields:
        if field not in body:
            continue
        if field == "visibility_scope" and body[field] not in ALLOWED_VISIBILITY:
            return error_response(f"Invalid visibility_scope: {body[field]}", 400)
        if field == "sensitivity_level" and body[field] not in ALLOWED_SENSITIVITY:
            return error_response(f"Invalid sensitivity_level: {body[field]}", 400)
        value = _safe_int(body[field]) if field in int_fields and body[field] else body[field]
        setattr(file, field, value)

    
    db.session.commit()
    emit_event("file_updated", file.id, current_user_id)

    return success_response(file.to_dict(include_ai=True))


@drive_file_bp.delete("/<int:file_id>")
@jwt_required()
def delete_file(file_id):
    current_user_id = int(get_jwt_identity())
    file = DriveFile.query.get_or_404(file_id)
    if file.state == "deleted":
        return error_response("File not found", 404)

    if file.storage_key:
        delete_from_storage(file.storage_key)
        file.storage_key = None

    
    file.state = "deleted"
    db.session.commit()
    emit_event("file_deleted", file_id, current_user_id)
    
    return success_response({"message": "File soft-deleted", "id": file.id})


@drive_file_bp.post("/<int:file_id>/mark-canonical")
@jwt_required()
def mark_canonical(file_id):
    current_user_id = int(get_jwt_identity())
    file = DriveFile.query.get_or_404(file_id)

    if file.state == "deleted":
        return error_response("File not found", 404)

    file.canonicality_score = 1.0
    
    db.session.commit()
    emit_event("file_marked_canonical", file.id, current_user_id)
    
    return success_response(file.to_dict(include_ai=True))


@drive_file_bp.get("/scope/startup/<int:startup_id>")
@jwt_required()
def list_by_startup(startup_id):
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    pagination = (
        DriveFile.query
        .filter_by(startup_id=startup_id)
        .filter(DriveFile.state != "deleted")
        .order_by(DriveFile.updated_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return success_response({
        "items": [f.to_dict() for f in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": per_page,
    })


@drive_file_bp.get("/scope/workspace/<int:workspace_id>")
@jwt_required()
def list_by_workspace(workspace_id):
    current_user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    pagination = (
        DriveFile.query
        .filter_by(workspace_id=workspace_id)
        .filter(DriveFile.state != "deleted")
        .order_by(DriveFile.updated_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return success_response({
        "items": [f.to_dict() for f in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": per_page,
    })


@drive_file_bp.patch("/<int:file_id>/state")
@jwt_required()
def update_file_state(file_id):
    current_user_id = int(get_jwt_identity())
    file = DriveFile.query.get_or_404(file_id)

    data = request.get_json() or {}
    new_state = data.get("state")

    if not new_state:
        return error_response("'state' is required", 400)

    if new_state not in VALID_STATES:
        return error_response(f"Invalid state '{new_state}'", 400)

    current_state = file.state
    if not validate_transition(current_state, new_state):
        return error_response(f"Invalid state transition: {current_state} → {new_state}", 400)
    
    file.state = new_state
    db.session.commit()

    emit_event("file_state_changed", file.id, current_user_id, event_metadata={
    "old_state": current_state,
    "new_state": new_state
    })
   
    return success_response({
        "message": "State updated successfully",
        "file_id": file.id,
        "old_state": current_state,
        "new_state": new_state
    })