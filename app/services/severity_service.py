from datetime import date, timedelta
from app.models.warning import Warning

# Base severity for each warning type (before escalation)
BASE_SEVERITY = {
    'missing_attendance': 'notice',
    'missing_update': 'notice',
    'late_update': 'notice',
    'overdue_task': 'warning',
    'inactivity': 'notice',
}

SEVERITY_LEVELS = ['notice', 'warning', 'serious', 'admin_review']

def determine_severity(user_id, workspace_id, warning_type):
    """
    Calculate the appropriate severity for a new warning of given type,
    based on recent unresolved warnings of the same type for this user/workspace.
    """
    base = BASE_SEVERITY.get(warning_type, 'notice')
    base_index = SEVERITY_LEVELS.index(base)

    # Count unresolved warnings of the same type in the last 30 days
    recent_window = date.today() - timedelta(days=30)
    count = Warning.query.filter(
        Warning.user_id == user_id,
        Warning.workspace_id == workspace_id,
        Warning.type == warning_type,
        Warning.is_resolved == False,
        Warning.created_at >= recent_window
    ).count()

    # Escalate: each previous warning pushes severity up by one step
    # but never beyond 'admin_review'
    new_index = min(base_index + count, 3)   # 3 is index of 'admin_review'
    return SEVERITY_LEVELS[new_index]