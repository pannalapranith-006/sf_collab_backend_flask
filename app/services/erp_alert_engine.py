from datetime import date, datetime, timedelta

from app.extensions import db
from app.models.attendance import Attendance
from app.models.daily_update import DailyUpdate
from app.models.erp_alert import ErpAlert
from app.models.erp_task import ErpTask
from app.models.erp_user_activity import ErpUserActivity
from app.models.holiday import Holiday
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember


def _today(target_date=None):
    return target_date or date.today()


def _active_member_ids(workspace_id):
    rows = WorkspaceMember.query.filter_by(workspace_id=workspace_id, status='active').all()
    return [row.user_id for row in rows]


def _dedupe_key(workspace_id, user_id, alert_type, source_date, reference_id=None):
    ref = reference_id if reference_id is not None else 'none'
    uid = user_id if user_id is not None else 'none'
    return f'{workspace_id}:{uid}:{alert_type}:{source_date.isoformat()}:{ref}'


def _create_alert_once(workspace_id, user_id, alert_type, message, source_date, priority='medium', reference_id=None):
    key = _dedupe_key(workspace_id, user_id, alert_type, source_date, reference_id)
    existing = ErpAlert.query.filter_by(dedupe_key=key).first()
    if existing:
        return None

    alert = ErpAlert(
        workspace_id=workspace_id,
        user_id=user_id,
        type=alert_type,
        priority=priority,
        message=message,
        reference_id=reference_id,
        source_date=source_date,
        dedupe_key=key,
    )
    db.session.add(alert)
    return alert


def generate_missing_update_alerts(workspace_id, target_date=None):
    current_day = _today(target_date)
    member_ids = _active_member_ids(workspace_id)

    updates = DailyUpdate.query.filter_by(workspace_id=workspace_id, date=current_day).all()
    submitted = {u.user_id for u in updates}

    created = 0
    for user_id in member_ids:
        if user_id in submitted:
            continue
        alert = _create_alert_once(
            workspace_id=workspace_id,
            user_id=user_id,
            alert_type='missing_update',
            priority='medium',
            source_date=current_day,
            message=f'No daily update submitted for {current_day.isoformat()}',
        )
        if alert:
            created += 1

    return created


def generate_late_attendance_alerts(workspace_id, target_date=None):
    current_day = _today(target_date)

    holiday = Holiday.query.filter_by(workspace_id=workspace_id, date=current_day).first()
    if holiday:
        return 0

    member_ids = _active_member_ids(workspace_id)
    records = Attendance.query.filter_by(workspace_id=workspace_id, date=current_day).all()
    by_user = {r.user_id: r for r in records}

    created = 0
    for user_id in member_ids:
        record = by_user.get(user_id)
        if not record or not record.clock_in_time:
            alert = _create_alert_once(
                workspace_id=workspace_id,
                user_id=user_id,
                alert_type='late_attendance',
                priority='high',
                source_date=current_day,
                message=f'No clock-in recorded for {current_day.isoformat()}',
            )
            if alert:
                created += 1
            continue

        status = record.status.value if hasattr(record.status, 'value') else record.status
        if status == 'late':
            alert = _create_alert_once(
                workspace_id=workspace_id,
                user_id=user_id,
                alert_type='late_attendance',
                priority='medium',
                source_date=current_day,
                reference_id=record.id,
                message=f'Late clock-in detected at {record.clock_in_time.isoformat()}',
            )
            if alert:
                created += 1

    return created


def generate_task_overdue_alerts(workspace_id, target_date=None):
    current_day = _today(target_date)

    overdue_tasks = ErpTask.query.filter(
        ErpTask.workspace_id == workspace_id,
        ErpTask.deadline.isnot(None),
        ErpTask.deadline < datetime.utcnow(),
        ErpTask.status != 'done',
    ).all()

    created = 0
    for task in overdue_tasks:
        owner_user_id = task.assigned_to or task.created_by
        alert = _create_alert_once(
            workspace_id=workspace_id,
            user_id=owner_user_id,
            alert_type='task_overdue',
            priority='high',
            source_date=current_day,
            reference_id=task.id,
            message=f'Task "{task.title}" is overdue',
        )
        if alert:
            created += 1

    return created


def generate_inactive_user_alerts(workspace_id, target_date=None, inactivity_days=3):
    current_day = _today(target_date)
    cutoff = datetime.utcnow() - timedelta(days=inactivity_days)

    member_ids = _active_member_ids(workspace_id)
    if not member_ids:
        return 0

    users = User.query.filter(User.id.in_(member_ids)).all()
    activity_rows = ErpUserActivity.query.filter(
        ErpUserActivity.workspace_id == workspace_id,
        ErpUserActivity.user_id.in_(member_ids),
    ).all()
    activity_map = {row.user_id: row for row in activity_rows}

    created = 0
    for user in users:
        row = activity_map.get(user.id)
        if row and row.last_activity:
            last_activity_dt = row.last_activity
        elif row and row.last_login:
            last_activity_dt = row.last_login
        else:
            last_activity_dt = user.last_login or user.updated_at
        if last_activity_dt and last_activity_dt >= cutoff:
            continue

        alert = _create_alert_once(
            workspace_id=workspace_id,
            user_id=user.id,
            alert_type='inactive_user',
            priority='low',
            source_date=current_day,
            message=f'User inactive for more than {inactivity_days} day(s)',
        )
        if alert:
            created += 1

    return created


def run_alert_jobs(workspace_id=None, target_date=None, inactivity_days=3):
    current_day = _today(target_date)

    if workspace_id is not None:
        workspace_ids = [workspace_id]
    else:
        workspace_ids = [w.id for w in Workspace.query.filter_by(is_active=True).all()]

    totals = {
        'missing_update': 0,
        'late_attendance': 0,
        'task_overdue': 0,
        'inactive_user': 0,
        'total_created': 0,
    }

    for wid in workspace_ids:
        totals['missing_update'] += generate_missing_update_alerts(wid, current_day)
        totals['late_attendance'] += generate_late_attendance_alerts(wid, current_day)
        totals['task_overdue'] += generate_task_overdue_alerts(wid, current_day)
        totals['inactive_user'] += generate_inactive_user_alerts(wid, current_day, inactivity_days)

    totals['total_created'] = (
        totals['missing_update']
        + totals['late_attendance']
        + totals['task_overdue']
        + totals['inactive_user']
    )

    db.session.commit()
    return totals
