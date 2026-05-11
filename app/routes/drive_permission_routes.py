from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.drive_file import DriveFile
from app.models.drive_permission import DriveFilePermission
from app.utils.response_helpers import success_response, error_response

drive_permission_bp = Blueprint('drive_permissions', __name__, url_prefix='/api/drive')

def _get_file_or_404(file_id):
    file = DriveFile.query.get(file_id)
    if not file or file.state == 'deleted':
        from flask import abort
        abort(404, description="File not found")
    return file

# ── Grant permission ──────────────────────────────────────────────────────────
@drive_permission_bp.route('/files/<int:file_id>/permissions/grant', methods=['POST'])
@jwt_required()
def grant_permission(file_id):
    """
    Grant a user permission to a file.
    Body: { "user_id": int, "role": "viewer" | "editor" | "owner" }
    """
    current_user_id = int(get_jwt_identity())
    file = _get_file_or_404(file_id)

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    role = data.get('role', 'viewer')

    if not user_id:
        return error_response("'user_id' is required", 400)

    if role not in ('viewer', 'editor', 'owner'):
        return error_response("'role' must be one of: viewer, editor, owner", 400)

    # Check if permission already exists
    existing = DriveFilePermission.query.filter_by(
        file_id=file_id, user_id=user_id
    ).first()
    if existing:
        existing.role = role  # update role if already granted
        db.session.commit()
        return success_response(existing.to_dict())

    permission = DriveFilePermission(
        file_id=file_id,
        user_id=user_id,
        role=role
    )
    db.session.add(permission)
    db.session.commit()
    return success_response(permission.to_dict(), 201)


# ── Revoke permission ─────────────────────────────────────────────────────────
@drive_permission_bp.route('/files/<int:file_id>/permissions/revoke', methods=['DELETE'])
@jwt_required()
def revoke_permission(file_id):
    """
    Revoke a user's permission from a file.
    Body: { "user_id": int }
    """
    current_user_id = int(get_jwt_identity())
    file = _get_file_or_404(file_id)

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return error_response("'user_id' is required", 400)

    permission = DriveFilePermission.query.filter_by(
        file_id=file_id, user_id=user_id
    ).first()

    if not permission:
        return error_response("Permission not found for that user", 404)

    db.session.delete(permission)
    db.session.commit()
    return success_response({"message": "Permission revoked"})


# ── List permissions for a file ───────────────────────────────────────────────
@drive_permission_bp.route('/files/<int:file_id>/permissions', methods=['GET'])
@jwt_required()
def list_permissions(file_id):
    """
    List all user permissions for a file.
    """
    file = _get_file_or_404(file_id)

    permissions = DriveFilePermission.query.filter_by(file_id=file_id).all()
    return success_response([p.to_dict() for p in permissions])