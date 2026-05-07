from app.extensions import db
from app.models.drive_audit_log import DriveAuditLog


def log_action(file_id, action, performed_by=None, metadata=None):
    log = DriveAuditLog(
        file_id=file_id,
        action=action,
        performed_by=performed_by,
        event_metadata=metadata or {},
    )
    db.session.add(log)