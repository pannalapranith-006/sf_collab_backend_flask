from datetime import date, timedelta
from app import db
from app.models.consistency_point import ConsistencyPoint
from app.models.workspace_membership import WorkspaceMembership
from app.models.attendance_log import AttendanceLog
from app.models.daily_update import DailyUpdate
from app.models.warning import Warning
from app.services.membership_audit_service import log_membership_action

def _already_awarded(user_id, workspace_id, log_date, type):
    return ConsistencyPoint.query.filter_by(
        user_id=user_id, workspace_id=workspace_id,
        log_date=log_date, type=type
    ).first() is not None

def award_clock_in_points(user_id, workspace_id, log_date):
    """Award 1 point for clocking in, if not already awarded."""
    if _already_awarded(user_id, workspace_id, log_date, 'clock_in'):
        return
    # Check attendance log for that day
    log = AttendanceLog.query.filter_by(
        user_id=user_id, workspace_id=workspace_id, log_date=log_date
    ).first()
    if log and log.clock_in:
        cp = ConsistencyPoint(
            user_id=user_id, workspace_id=workspace_id,
            log_date=log_date, type='clock_in', points=1
        )
        db.session.add(cp)
        db.session.commit()
        # No audit log for every tiny point; skip or log if needed.

def award_daily_update_points(user_id, workspace_id, log_date):
    """Award 2 points for submitting a daily update, if not already awarded."""
    if _already_awarded(user_id, workspace_id, log_date, 'daily_update'):
        return
    update = DailyUpdate.query.filter_by(
        user_id=user_id, workspace_id=workspace_id, log_date=log_date
    ).first()
    if update:
        cp = ConsistencyPoint(
            user_id=user_id, workspace_id=workspace_id,
            log_date=log_date, type='daily_update', points=2
        )
        db.session.add(cp)
        db.session.commit()

def is_full_productive_day(user_id, workspace_id, log_date):
    """Check if a day qualifies as a full productive day."""
    # 1. Clocked in
    attendance = AttendanceLog.query.filter_by(
        user_id=user_id, workspace_id=workspace_id, log_date=log_date
    ).first()
    if not attendance or not attendance.clock_in:
        return False

    # 2. Daily update submitted
    update = DailyUpdate.query.filter_by(
        user_id=user_id, workspace_id=workspace_id, log_date=log_date
    ).first()
    if not update:
        return False

    # 3. No unresolved serious warning that day (warnings with severity 'serious' or 'admin_review' and unresolved)
    serious_warning = Warning.query.filter(
        Warning.user_id == user_id,
        Warning.workspace_id == workspace_id,
        Warning.severity.in_(['serious', 'admin_review']),
        Warning.is_resolved == False,
        db.func.date(Warning.created_at) == log_date
    ).first()
    if serious_warning:
        return False

    # 4. At least one task/activity signal (we'll check erp_task updated that day)
    from app.models.erp_task import ErpTask
    task_activity = ErpTask.query.filter(
        ErpTask.assignee_id == user_id,
        ErpTask.workspace_id == workspace_id,
        db.func.date(ErpTask.updated_at) == log_date
    ).first()
    if not task_activity:
        return False

    return True

def award_productive_day_points(user_id, workspace_id, log_date):
    """Award 5 points if it's a full productive day and not yet awarded."""
    if _already_awarded(user_id, workspace_id, log_date, 'productive_day'):
        return
    if is_full_productive_day(user_id, workspace_id, log_date):
        cp = ConsistencyPoint(
            user_id=user_id, workspace_id=workspace_id,
            log_date=log_date, type='productive_day', points=5
        )
        db.session.add(cp)
        db.session.commit()

def calculate_daily_consistency(workspace_id, target_date=None):
    """
    For a given date, award all applicable daily consistency points
    to all workspace members. Default date = yesterday.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    members = WorkspaceMembership.query.filter_by(workspace_id=workspace_id).all()
    awarded = 0

    for m in members:
        user_id = m.user_id
        # Award in order (productive day includes the other checks)
        award_clock_in_points(user_id, workspace_id, target_date)
        award_daily_update_points(user_id, workspace_id, target_date)
        award_productive_day_points(user_id, workspace_id, target_date)
        awarded += 1   # count members processed

    log_membership_action(
        'consistency_daily_calc',
        workspace_id=workspace_id,
        details={'date': target_date.isoformat(), 'members_processed': awarded}
    )
    return awarded

def award_perfect_week_points(user_id, workspace_id, week_end_date):
    """
    Award 20 points if the user had a full productive day every weekday
    of the week ending on week_end_date (a Friday). Points awarded for that Friday.
    """
    if week_end_date.weekday() != 4:   # Friday
        raise ValueError("week_end_date must be a Friday")
    start_date = week_end_date - timedelta(days=4)   # Monday

    # Check all weekdays
    current = start_date
    while current <= week_end_date:
        if not is_full_productive_day(user_id, workspace_id, current):
            return False
        current += timedelta(days=1)

    # Already awarded?
    if _already_awarded(user_id, workspace_id, week_end_date, 'perfect_week'):
        return False

    cp = ConsistencyPoint(
        user_id=user_id, workspace_id=workspace_id,
        log_date=week_end_date, type='perfect_week', points=20
    )
    db.session.add(cp)
    db.session.commit()
    return True

def calculate_weekly_consistency(workspace_id, week_end_date=None):
    """
    Award perfect week points to all members for the week ending Friday.
    Default: yesterday if yesterday is Friday, else last Friday.
    """
    if week_end_date is None:
        today = date.today()
        # find last Friday
        days_since_fri = (today.weekday() - 4) % 7
        week_end_date = today - timedelta(days=days_since_fri)
    else:
        if week_end_date.weekday() != 4:
            raise ValueError("week_end_date must be a Friday")

    members = WorkspaceMembership.query.filter_by(workspace_id=workspace_id).all()
    awarded_count = 0
    for m in members:
        if award_perfect_week_points(m.user_id, workspace_id, week_end_date):
            awarded_count += 1

    log_membership_action(
        'consistency_weekly_calc',
        workspace_id=workspace_id,
        details={'week_end': week_end_date.isoformat(), 'perfect_weeks_awarded': awarded_count}
    )
    return awarded_count