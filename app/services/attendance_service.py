from datetime import datetime, date, time
from app import db
from app.models.attendance_log import AttendanceLog
from app.services.membership_audit_service import log_membership_action
from app.models.workspace_membership import WorkspaceMembership

WORK_START = time(9, 0)           # 09:00 UTC
GRACE_END  = time(9, 15)          # 09:15 UTC

def clock_in(workspace_id, user_id):
    """Record clock-in for today. Raises ValueError on duplicate."""
    today = date.today()
    existing = AttendanceLog.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        log_date=today
    ).first()

    if existing and existing.clock_in is not None:
        raise ValueError('Already clocked in today.')

    now_utc = datetime.utcnow()
    now_time = now_utc.time()

    # Determine status
    if now_time <= GRACE_END:
        status = 'present'
    else:
        status = 'late'

    if existing:
        # record exists (maybe absent set by job), update it
        existing.clock_in = now_utc
        existing.status = status
    else:
        entry = AttendanceLog(
            user_id=user_id,
            workspace_id=workspace_id,
            log_date=today,
            clock_in=now_utc,
            status=status
        )
        db.session.add(entry)

    db.session.commit()
    log_membership_action(
        'clock_in',
        workspace_id=workspace_id,
        details={'user_id': user_id, 'time': now_utc.isoformat(), 'status': status}
    )
    return entry if not existing else existing

def clock_out(workspace_id, user_id):
    """Record clock-out for today. Must have an open clock-in."""
    today = date.today()
    entry = AttendanceLog.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        log_date=today
    ).first()

    if not entry or entry.clock_in is None:
        raise ValueError('No clock-in record found for today.')
    if entry.clock_out is not None:
        raise ValueError('Already clocked out today.')

    entry.clock_out = datetime.utcnow()
    db.session.commit()
    log_membership_action(
        'clock_out',
        workspace_id=workspace_id,
        details={'user_id': user_id, 'time': entry.clock_out.isoformat()}
    )
    return entry

def mark_absentees(workspace_id, target_date=None):
    """
    For a given date (default today), mark all members who have
    no attendance record as 'absent'.
    Returns the number of new absent records created.
    """
    if target_date is None:
        target_date = date.today()

    # 1. Get all active members of the workspace
    memberships = WorkspaceMembership.query.filter_by(
        workspace_id=workspace_id
    ).all()

    created_count = 0

    for membership in memberships:
        user_id = membership.user_id
        # Check if an attendance record already exists for this day
        existing = AttendanceLog.query.filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
            log_date=target_date
        ).first()

        if not existing:
            # Create a new absent record
            absent_entry = AttendanceLog(
                user_id=user_id,
                workspace_id=workspace_id,
                log_date=target_date,
                status='absent'
            )
            db.session.add(absent_entry)
            created_count += 1

    db.session.commit()

    if created_count > 0:
        log_membership_action(
            'mark_absentees',
            workspace_id=workspace_id,
            details={
                'date': target_date.isoformat(),
                'absent_count': created_count
            }
        )

    return created_count