from datetime import datetime
from flask import Blueprint, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import drive_file
from app.models.drive_file import DriveFile, DriveFileVersion
from app.services.drive_storage_service import StorageError, save_upload, open_for_download, delete_from_storage
from app.utils.drive_lifecycle import validate_transition
from app.utils.response_helpers import success_response, error_response
from app.services.drive_event_service import emit_event

drive_file_bp = Blueprint('drive_files', __name__, url_prefix='/api/drive/files')

ALLOWED_VISIBILITY = (
    "private", "shared-with-specific-users", "startup-members",
    "organization-members", "public-link", "marketplace-customer",
    "mentor-visible", "advisor-visible", "finance-team-only", "legal-team-only",
)
ALLOWED_SENSITIVITY = ("public", "internal", "restricted", "confidential")
VALID_STATES = ["uploaded", "processing", "indexed", "active", "archived", "deleted"]

def _safe_int(value, field_name="value"):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f"'{field_name}' must be a valid integer, got: {value!r}")

# ─── Upload ───
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
    owner_user_id=current_user_id,
    created_by=current_user_id,
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

    # create initial version
    version = DriveFileVersion(
    file_id=drive_file.file_id,
    version_number=1,
    file_path=stored["storage_key"],
    file_url=None,
    created_by=current_user_id,
    size_bytes=stored["size_bytes"],
    mime_type=stored["mime_type"],
    )
    db.session.add(version)
    db.session.commit()

    emit_event("file_uploaded", drive_file.file_id, current_user_id, metadata={"filename": drive_file.filename})
    return success_response(drive_file.to_dict(), 201)

@drive_file_bp.get("/list")
@jwt_required()
def list_files_advanced():
    """Enhanced file listing with pagination, filtering, sorting."""
    workspace_id = request.args.get('workspace_id', type=int)
    folder_id = request.args.get('folder_id', type=int)
    state = request.args.get('state')
    document_type = request.args.get('document_type')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sort_by = request.args.get('sort', 'updated_at')  # updated_at, filename, size_bytes
    order = request.args.get('order', 'desc')         # asc or desc

    query = DriveFile.query.filter(DriveFile.state != 'deleted')
    if workspace_id:
        query = query.filter_by(workspace_id=workspace_id)
    if folder_id is not None:
        query = query.filter_by(folder_id=folder_id)
    if state:
        query = query.filter_by(state=state)
    if document_type:
        query = query.filter_by(document_type=document_type)

    # Sorting
    sort_col = getattr(DriveFile, sort_by, DriveFile.updated_at)
    query = query.order_by(sort_col.desc() if order == 'desc' else sort_col.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return success_response({
        'items': [f.to_dict() for f in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
        'per_page': per_page
    })
# ─── Download ───
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

# ─── Version History ───
@drive_file_bp.get("/<int:file_id>/versions")
@jwt_required()
def list_versions(file_id):
    drive_file = DriveFile.query.get_or_404(file_id)
    if drive_file.state == "deleted":
        return error_response("File not found", 404)
    versions = DriveFileVersion.query.filter_by(file_id=file_id).order_by(DriveFileVersion.version_number.desc()).all()
    return success_response([v.to_dict() for v in versions])

@drive_file_bp.post("/<int:file_id>/versions")
@jwt_required()
def upload_new_version(file_id):
    current_user_id = int(get_jwt_identity())
    drive_file = DriveFile.query.get_or_404(file_id)
    if drive_file.state == "deleted":
        return error_response("File not found", 404)
    if "file" not in request.files or request.files["file"].filename == "":
        return error_response("'file' is required", 400)

    upload = request.files["file"]
    owner_scope_type = drive_file.owner_scope_type
    owner_scope_id = str(drive_file.owner_scope_id)

    try:
        stored = save_upload(
            file_stream=upload.stream,
            original_filename=upload.filename,
            declared_mime=upload.content_type,
            owner_scope_type=owner_scope_type,
            owner_scope_id=owner_scope_id,
        )
    except StorageError as exc:
        return error_response(str(exc), exc.status_code)

    latest = DriveFileVersion.query.filter_by(file_id=file_id).order_by(DriveFileVersion.version_number.desc()).first()
    next_ver = (latest.version_number + 1) if latest else 1

    version = DriveFileVersion(
        file_id=file_id,
        version_number=next_ver,
        file_path=stored["storage_key"],
        file_url=None,
        created_by=current_user_id,
        size_bytes=stored["size_bytes"],
        mime_type=stored["mime_type"],
    )
    db.session.add(version)
    drive_file.storage_key = stored["storage_key"]
    drive_file.size_bytes = stored["size_bytes"]
    drive_file.mime_type = stored["mime_type"]
    drive_file.extension = stored["extension"]
    drive_file.updated_at = datetime.utcnow()
    db.session.commit()
    emit_event("file_updated", file_id, current_user_id, metadata={"version": next_ver})
    return success_response(version.to_dict(), 201)

@drive_file_bp.post("/<int:file_id>/versions/<int:version_id>/restore")
@jwt_required()
def restore_version(file_id, version_id):
    current_user_id = int(get_jwt_identity())
    drive_file = DriveFile.query.get_or_404(file_id)
    version = DriveFileVersion.query.filter_by(id=version_id, file_id=file_id).first_or_404()
    drive_file.storage_key = version.file_path
    drive_file.size_bytes = version.size_bytes
    drive_file.mime_type = version.mime_type
    db.session.commit()
    emit_event("file_updated", file_id, current_user_id, metadata={"restored_version": version.version_number})
    return success_response({"message": "Version restored", "version": version.version_number})

# ─── State Management ───
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
    if not validate_transition(file.state, new_state):
        return error_response(f"Invalid transition from '{file.state}' to '{new_state}'", 400)
    old_state = file.state
    file.state = new_state
    db.session.commit()
    emit_event("file_state_changed", file_id, current_user_id, metadata={"old_state": old_state, "new_state": new_state})
    return success_response({"message": "State updated", "file_id": file_id, "old_state": old_state, "new_state": new_state})

# ─── AI Processing Stub ───
@drive_file_bp.post("/<int:file_id>/process")
@jwt_required()
def process_file(file_id):
    current_user_id = int(get_jwt_identity())
    file = DriveFile.query.get_or_404(file_id)
    if file.state not in ("uploaded", "indexed", "active"):
        return error_response("File not in a processable state", 400)
    file.state = "processing"
    db.session.commit()
    emit_event("file_processing_started", file_id, current_user_id)
    return success_response({"message": "Processing started"}, 202)

# ─── Semantic Search Stub ───
@drive_file_bp.get("/search")
@jwt_required()
def search_files():
    q = request.args.get("q", "")
    workspace_id = request.args.get("workspace_id", type=int)
    query = DriveFile.query.filter(DriveFile.state.in_(["indexed", "active"]))
    if workspace_id:
        query = query.filter_by(workspace_id=workspace_id)
    if q:
        query = query.filter(DriveFile.filename.ilike(f"%{q}%"))
    files = query.limit(20).all()
    return success_response([f.to_dict(include_ai=True) for f in files])