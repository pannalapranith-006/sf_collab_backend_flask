from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.drive_audit_log import DriveAuditLog
from app.utils.response_helpers import success_response

drive_audit_bp = Blueprint('drive_audit', __name__, url_prefix='/api/drive/audit')

@drive_audit_bp.get("/<int:file_id>")
@jwt_required()
def get_file_logs(file_id):
    logs = DriveAuditLog.query.filter_by(file_id=file_id).order_by(DriveAuditLog.created_at.desc()).all()
    return success_response([log.to_dict() for log in logs])