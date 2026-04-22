import os
from datetime import datetime
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.MilestoneFile import MilestoneFile

milestone_files_bp = Blueprint('milestone_files', __name__)

# ---------------------------------------------------------------------------
# Upload config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'milestone_files')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp',          # images
    'pdf', 'doc', 'docx', 'xls', 'xlsx',           # documents
    'txt', 'csv', 'ppt', 'pptx',                   # misc docs
    'zip', 'mp4', 'mov',                            # archives / video
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _category(mime: str) -> str:
    if mime and mime.startswith('image/'):
        return 'image'
    if mime in ('application/pdf', 'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/plain', 'text/csv'):
        return 'document'
    return 'other'


# ---------------------------------------------------------------------------
# POST /api/milestone-files/<milestone_id>/upload
# Attach a file to a milestone
# ---------------------------------------------------------------------------
@milestone_files_bp.route('/<int:milestone_id>/upload', methods=['POST'])
@jwt_required()
def upload_milestone_file(milestone_id):
    user_id = int(get_jwt_identity())

    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not _allowed(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    # Size check
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return jsonify({'error': 'File exceeds 20 MB limit'}), 400

    # Build unique filename: timestamp_userId_original
    original_name = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    stored_name = f"{timestamp}_{user_id}_{original_name}"
    file_path = os.path.join(UPLOAD_FOLDER, stored_name)
    file.save(file_path)

    milestone_file = MilestoneFile(
        milestone_id  = milestone_id,
        uploaded_by   = user_id,
        original_name = original_name,
        stored_name   = stored_name,
        file_url      = f"/api/milestone-files/serve/{stored_name}",
        file_size     = size,
        file_type     = file.content_type,
        file_category = _category(file.content_type),
        is_proof      = False,
    )
    db.session.add(milestone_file)
    db.session.commit()

    return jsonify({
        'message': 'File uploaded successfully',
        'file':    milestone_file.to_dict(),
    }), 201


# ---------------------------------------------------------------------------
# PATCH /api/milestone-files/<file_id>/mark-proof
# Toggle is_proof on a specific file
# ---------------------------------------------------------------------------
@milestone_files_bp.route('/<int:file_id>/mark-proof', methods=['PATCH'])
@jwt_required()
def mark_as_proof(file_id):
    user_id = int(get_jwt_identity())

    mf = MilestoneFile.query.get(file_id)
    if not mf:
        return jsonify({'error': 'File not found'}), 404

    # Accept optional body: { "is_proof": true/false }
    body = request.get_json(silent=True) or {}
    mf.is_proof = bool(body.get('is_proof', not mf.is_proof))   # toggle if not supplied
    db.session.commit()

    return jsonify({
        'message': f"File marked as {'proof' if mf.is_proof else 'not proof'}",
        'file':    mf.to_dict(),
    }), 200


# ---------------------------------------------------------------------------
# GET /api/milestone-files/<milestone_id>
# Return all files for a milestone (split into proof / documents)
# ---------------------------------------------------------------------------
@milestone_files_bp.route('/<int:milestone_id>', methods=['GET'])
@jwt_required()
def get_milestone_files(milestone_id):
    files = (
        MilestoneFile.query
        .filter_by(milestone_id=milestone_id)
        .order_by(MilestoneFile.created_at.desc())
        .all()
    )

    proof_files = [f.to_dict() for f in files if f.is_proof]
    other_files = [f.to_dict() for f in files if not f.is_proof]

    return jsonify({
        'milestone_id': milestone_id,
        'proof_files':  proof_files,
        'documents':    other_files,
        'total':        len(files),
    }), 200


# ---------------------------------------------------------------------------
# DELETE /api/milestone-files/<file_id>
# Delete a file record and remove from disk
# ---------------------------------------------------------------------------
@milestone_files_bp.route('/<int:file_id>', methods=['DELETE'])
@jwt_required()
def delete_milestone_file(file_id):
    user_id = int(get_jwt_identity())

    mf = MilestoneFile.query.get(file_id)
    if not mf:
        return jsonify({'error': 'File not found'}), 404

    # Remove physical file
    disk_path = os.path.join(UPLOAD_FOLDER, mf.stored_name)
    if os.path.exists(disk_path):
        os.remove(disk_path)

    db.session.delete(mf)
    db.session.commit()

    return jsonify({'message': 'File deleted'}), 200


# ---------------------------------------------------------------------------
# GET /api/milestone-files/serve/<filename>
# Serve the actual file bytes (static-file style)
# ---------------------------------------------------------------------------
@milestone_files_bp.route('/serve/<path:filename>', methods=['GET'])
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)