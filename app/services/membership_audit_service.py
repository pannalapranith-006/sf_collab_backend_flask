from flask_jwt_extended import get_jwt_identity
from app import db
from app.models.membership_audit_log import MembershipAuditLog
from datetime import datetime

def log_membership_action(action, workspace_id=None, details=None):
    """Log membership-related actions."""
    user_id = int(get_jwt_identity())
    log = MembershipAuditLog(
        user_id=user_id,
        workspace_id=workspace_id,
        action=action,
        details=details or {}
    )
    db.session.add(log)
    db.session.commit()