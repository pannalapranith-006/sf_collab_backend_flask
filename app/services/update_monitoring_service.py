from datetime import date, datetime, timedelta, time
from app import db
from app.models.workspace_membership import WorkspaceMembership
from app.models.daily_update import DailyUpdate
from app.services.warning_service import create_warning

DEADLINE_TIME = time(12, 0)  # noon UTC

def check_missing_late_updates(workspace_id, target_date=None):
    """
    Check all workspace members for missing/late daily updates on target_date.
    Default target_date = yesterday (so we run checks after the day ends).
    Returns dict with counts of warnings generated.
    """
    if target_date is None:
        # Check yesterday’s updates by default
        target_date = date.today() - timedelta(days=1)

    # Get all active workspace members
    memberships = WorkspaceMembership.query.filter_by(workspace_id=workspace_id).all()

    warnings_created = {'missing': 0, 'late': 0}

    for membership in memberships:
        user_id = membership.user_id
        # Find today's update (if any)
        update = DailyUpdate.query.filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
            log_date=target_date
        ).first()

        if not update:
            # Missing update
            create_warning(
                user_id=user_id,
                workspace_id=workspace_id,
                type='missing_update',
                message=f'Missing daily update for {target_date.isoformat()}'
            )
            warnings_created['missing'] += 1
        else:
            # Check if it was created after the deadline (late)
            # The update.created_at is UTC; compare only time part
            if update.created_at.time() > DEADLINE_TIME:
                create_warning(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    type='late_update',
                    message=f'Late daily update on {target_date.isoformat()} (submitted after 12:00 UTC)'
                )
                warnings_created['late'] += 1

    return warnings_created