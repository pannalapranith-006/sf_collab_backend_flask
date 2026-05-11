"""
app/routes/drive_routes.py
SF Drive API — upload, tagging, retrieval.
"""
import os
import threading
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.DriveFile import DriveFile

drive_bp = Blueprint('drive', __name__)

# ── Upload config ─────────────────────────────────────────────────────────────
BASE_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
UPLOAD_DIR   = os.path.join(BASE_DIR, 'uploads', 'drive_files')
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_SIZE     = 50 * 1024 * 1024   # 50 MB
ALLOWED_EXT  = {
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'txt', 'md', 'csv', 'json', 'yaml', 'yml',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg',
    'mp4', 'mov', 'mp3', 'zip',
}

KNOWLEDGE_TYPES = {
    'roadmap', 'milestone-proof', 'meeting-transcript', 'meeting-notes',
    'research', 'pitch', 'contract', 'invoice', 'design', 'spec',
    'architecture', 'gtm', 'product', 'legal', 'recording', 'other',
}

def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def _run_pipeline_async(file_id):
    """Run ingestion pipeline in a background thread so upload returns immediately."""
    try:
        from app.services.drive_pipeline import run_pipeline
        run_pipeline(file_id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Async pipeline error file_id=%s: %s", file_id, exc)


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/drive/upload
# Upload a file → save → trigger pipeline in background
# ══════════════════════════════════════════════════════════════════════════════
@drive_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    user_id = int(get_jwt_identity())

    if 'file' not in request.files:
        return jsonify({'error': 'No file in request'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not _allowed(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    # Size check
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE:
        return jsonify({'error': 'File exceeds 50 MB limit'}), 400

    original_name = secure_filename(file.filename)
    extension     = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
    timestamp     = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    stored_name   = f"{timestamp}_{user_id}_{original_name}"
    file_path     = os.path.join(UPLOAD_DIR, stored_name)
    file.save(file_path)

    # Optional fields from form
    body              = request.form
    knowledge_type    = body.get('knowledge_type', 'other')
    visibility_scope  = body.get('visibility_scope', 'private')
    startup_id        = body.get('startup_id')
    linked_milestone  = body.get('linked_milestone_id')
    linked_meeting    = body.get('linked_meeting_id')
    manual_tags       = body.getlist('tags')   # repeated field: tags=roadmap&tags=q2

    if knowledge_type not in KNOWLEDGE_TYPES:
        knowledge_type = 'other'

    drive_file = DriveFile(
        filename          = stored_name,
        original_name     = original_name,
        extension         = extension,
        mime_type         = file.content_type,
        size_bytes        = size,
        file_url          = f"/api/drive/serve/{stored_name}",
        owner_user_id     = user_id,
        startup_id        = int(startup_id)       if startup_id        else None,
        linked_milestone_id = int(linked_milestone) if linked_milestone else None,
        linked_meeting_id   = int(linked_meeting)   if linked_meeting   else None,
        visibility_scope  = visibility_scope,
        knowledge_type    = knowledge_type,
        file_state        = 'uploaded',
        indexing_status   = 'pending',
    )

    if manual_tags:
        drive_file.set_tags(manual_tags)

    db.session.add(drive_file)
    db.session.commit()

    # Run pipeline in background — upload returns immediately
    thread = threading.Thread(target=_run_pipeline_async, args=(drive_file.id,), daemon=True)
    thread.start()

    return jsonify({
        'message':    'File uploaded. Processing started in background.',
        'file':       drive_file.to_dict(include_summaries=False),
        'pipeline':   'running',
    }), 201


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/drive/files
# List files with optional filters
# ══════════════════════════════════════════════════════════════════════════════
@drive_bp.route('/files', methods=['GET'])
@jwt_required()
def list_files():
    user_id = int(get_jwt_identity())

    query = DriveFile.query.filter_by(owner_user_id=user_id)

    # Filters
    startup_id     = request.args.get('startup_id')
    knowledge_type = request.args.get('knowledge_type')
    milestone_id   = request.args.get('linked_milestone_id')
    tag            = request.args.get('tag')
    state          = request.args.get('file_state')

    if startup_id:
        query = query.filter_by(startup_id=int(startup_id))
    if knowledge_type:
        query = query.filter_by(knowledge_type=knowledge_type)
    if milestone_id:
        query = query.filter_by(linked_milestone_id=int(milestone_id))
    if state:
        query = query.filter_by(file_state=state)
    if tag:
        # JSON contains search — works in SQLite
        query = query.filter(DriveFile.tags_json.contains(f'"{tag.lower()}"'))

    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    paginated = query.order_by(DriveFile.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'files':      [f.to_dict(include_summaries=False) for f in paginated.items],
        'total':      paginated.total,
        'page':       page,
        'per_page':   per_page,
        'pages':      paginated.pages,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/drive/files/<file_id>
# Get a single file with full summaries
# ══════════════════════════════════════════════════════════════════════════════
@drive_bp.route('/files/<int:file_id>', methods=['GET'])
@jwt_required()
def get_file(file_id):
    user_id = int(get_jwt_identity())
    df = DriveFile.query.get(file_id)
    if not df:
        return jsonify({'error': 'File not found'}), 404
    if df.owner_user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403
    return jsonify({'file': df.to_dict(include_summaries=True)}), 200


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/drive/files/<file_id>/tags
# Add or replace tags manually
# Body: { "tags": ["roadmap", "q2"], "mode": "replace" | "merge" }
# ══════════════════════════════════════════════════════════════════════════════
@drive_bp.route('/files/<int:file_id>/tags', methods=['PATCH'])
@jwt_required()
def update_tags(file_id):
    user_id = int(get_jwt_identity())
    df = DriveFile.query.get(file_id)
    if not df:
        return jsonify({'error': 'File not found'}), 404
    if df.owner_user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    body = request.get_json(silent=True) or {}
    tags = body.get('tags', [])
    mode = body.get('mode', 'merge')   # 'replace' or 'merge'

    if not isinstance(tags, list):
        return jsonify({'error': 'tags must be a list'}), 400

    if mode == 'replace':
        df.set_tags(tags)
    else:
        df.add_tags(tags)

    db.session.commit()
    return jsonify({'message': 'Tags updated', 'tags': df.get_tags()}), 200


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/drive/files/<file_id>/knowledge-type
# Update knowledge_type manually
# Body: { "knowledge_type": "roadmap" }
# ══════════════════════════════════════════════════════════════════════════════
@drive_bp.route('/files/<int:file_id>/knowledge-type', methods=['PATCH'])
@jwt_required()
def update_knowledge_type(file_id):
    user_id = int(get_jwt_identity())
    df = DriveFile.query.get(file_id)
    if not df:
        return jsonify({'error': 'File not found'}), 404
    if df.owner_user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    body = request.get_json(silent=True) or {}
    kt   = body.get('knowledge_type', '')

    if kt not in KNOWLEDGE_TYPES:
        return jsonify({'error': f'Invalid knowledge_type. Must be one of: {", ".join(sorted(KNOWLEDGE_TYPES))}'}), 400

    df.knowledge_type = kt
    db.session.commit()
    return jsonify({'message': 'Knowledge type updated', 'knowledge_type': df.knowledge_type}), 200


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/drive/files/<file_id>/reprocess
# Manually trigger pipeline re-run (e.g. after AI key is added)
# ══════════════════════════════════════════════════════════════════════════════
@drive_bp.route('/files/<int:file_id>/reprocess', methods=['POST'])
@jwt_required()
def reprocess_file(file_id):
    user_id = int(get_jwt_identity())
    df = DriveFile.query.get(file_id)
    if not df:
        return jsonify({'error': 'File not found'}), 404
    if df.owner_user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    thread = threading.Thread(target=_run_pipeline_async, args=(file_id,), daemon=True)
    thread.start()
    return jsonify({'message': 'Reprocessing started'}), 202


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/drive/files/<file_id>
# ══════════════════════════════════════════════════════════════════════════════
@drive_bp.route('/files/<int:file_id>', methods=['DELETE'])
@jwt_required()
def delete_file(file_id):
    user_id = int(get_jwt_identity())
    df = DriveFile.query.get(file_id)
    if not df:
        return jsonify({'error': 'File not found'}), 404
    if df.owner_user_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    disk_path = os.path.join(UPLOAD_DIR, df.filename)
    if os.path.exists(disk_path):
        os.remove(disk_path)

    db.session.delete(df)
    db.session.commit()
    return jsonify({'message': 'File deleted'}), 200


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/drive/serve/<filename>
# Serve raw file bytes
# ══════════════════════════════════════════════════════════════════════════════
@drive_bp.route('/serve/<path:filename>', methods=['GET'])
def serve_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.drive_file import DriveFile
from app.models.drive_folder import DriveFolder
from app.models.startup import Startup
from app.models.startUpMember import StartupMember

drive_bp = Blueprint('drive', __name__, url_prefix='/api/drive')


def _authorize_workspace(workspace_id, user_id):
    startup = Startup.query.get(workspace_id)
    if not startup:
        return None, jsonify({'error': 'Workspace not found'}), 404
    is_member = StartupMember.query.filter_by(
        startup_id=workspace_id, user_id=user_id, is_active=True
    ).first()
    if not is_member and startup.creator_id != user_id:
        return None, jsonify({'error': 'Unauthorized access to this workspace'}), 403
    return startup, None, None


@drive_bp.route('/files', methods=['GET'])
@jwt_required()
def list_files():
    workspace_id = request.args.get('workspace_id', type=int)
    if workspace_id is None:
        return jsonify({'error': 'workspace_id is required'}), 400
    current_user_id = get_jwt_identity()
    _, error_resp, status = _authorize_workspace(workspace_id, current_user_id)
    if error_resp:
        return error_resp, status
    files = DriveFile.query.filter_by(workspace_id=workspace_id).all()
    return jsonify([f.to_dict() for f in files])


@drive_bp.route('/folders', methods=['GET'])
@jwt_required()
def list_folders():
    workspace_id = request.args.get('workspace_id', type=int)
    if workspace_id is None:
        return jsonify({'error': 'workspace_id is required'}), 400
    current_user_id = get_jwt_identity()
    _, error_resp, status = _authorize_workspace(workspace_id, current_user_id)
    if error_resp:
        return error_resp, status
    folders = DriveFolder.query.filter_by(workspace_id=workspace_id).all()
    return jsonify([f.to_dict() for f in folders])
