from app import db
from app.models.warning import Warning
from app.services.membership_audit_service import log_membership_action
from app.services.severity_service import determine_severity

def create_warning(user_id, workspace_id, type, message,
                   reference_date=None, reference_id=None, severity=None):
    if severity is None:
        severity = determine_severity(user_id, workspace_id, type)

    warning = Warning(
        user_id=user_id,
        workspace_id=workspace_id,
        type=type,
        severity=severity,
        message=message,
        reference_date=reference_date,
        reference_id=reference_id
    )
    db.session.add(warning)
    db.session.commit()

    log_membership_action(
        'warning_created',
        workspace_id=workspace_id,
        details={
            'warning_id': warning.id,
            'user_id': user_id,
            'type': type,
            'severity': severity,
            'message': message,
            'reference_date': reference_date.isoformat() if reference_date else None,
            'reference_id': reference_id
        }
    )
    return warning