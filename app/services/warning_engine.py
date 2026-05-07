from datetime import date, datetime, timedelta
from app import db
from app.models.warning import Warning
from app.models.workspace_membership import WorkspaceMembership
from app.models.attendance_log import AttendanceLog
from app.models.daily_update import DailyUpdate
from app.models.erp_task import ErpTask
from app.services.warning_service import create_warning

def _unresolved_warning_exists(user_id, workspace_id, type, reference_date=None, reference_id=None):
    query = Warning.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        type=type,
        is_resolved=False
    )
    if reference_date:
        query = query.filter_by(reference_date=reference_date)
    if reference_id:
        query = query.filter_by(reference_id=reference_id)
    return query.first() is not None

def scan_missing_attendance(workspace_id, target_date=None):
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    members = WorkspaceMembership.query.filter_by(workspace_id=workspace_id).all()
    count = 0

    for m in members:
        user_id = m.user_id
        log = AttendanceLog.query.filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
            log_date=target_date
        ).first()

        if not log:
            if not _unresolved_warning_exists(user_id, workspace_id, 'missing_attendance', reference_date=target_date):
                create_warning(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    type='missing_attendance',
                    message=f'No attendance recorded for {target_date.isoformat()}',
                    reference_date=target_date
                )
                count += 1
    return count

def scan_missing_updates(workspace_id, target_date=None):
    from app.services.update_monitoring_service import check_missing_late_updates
    return check_missing_late_updates(workspace_id, target_date)

def scan_overdue_tasks(workspace_id, current_date=None):
    if current_date is None:
        current_date = date.today()

    tasks = ErpTask.query.filter(
        ErpTask.workspace_id == workspace_id,
        ErpTask.status.notin_(['done', 'approved', 'rejected']),
        ErpTask.due_date.isnot(None),
        ErpTask.due_date < current_date
    ).all()

    count = 0
    for task in tasks:
        user_id = task.assignee_id
        if not user_id:
            continue
        if not _unresolved_warning_exists(user_id, workspace_id, 'overdue_task', reference_id=task.id):
            create_warning(
                user_id=user_id,
                workspace_id=workspace_id,
                type='overdue_task',
                message=f'Task "{task.title}" is overdue (due {task.due_date.isoformat()})',
                reference_date=current_date,
                reference_id=task.id
            )
            count += 1
    return count

def scan_inactivity(workspace_id, days_threshold=7, current_date=None):
    if current_date is None:
        current_date = date.today()
    cutoff_date = current_date - timedelta(days=days_threshold)

    members = WorkspaceMembership.query.filter_by(workspace_id=workspace_id).all()
    count = 0

    for m in members:
        user_id = m.user_id
        last_attendance = db.session.query(db.func.max(AttendanceLog.clock_in)).filter_by(
            user_id=user_id, workspace_id=workspace_id).scalar()
        last_update = db.session.query(db.func.max(DailyUpdate.created_at)).filter_by(
            user_id=user_id, workspace_id=workspace_id).scalar()
        last_task = db.session.query(db.func.max(ErpTask.updated_at)).filter(
            ErpTask.assignee_id == user_id,
            ErpTask.workspace_id == workspace_id
        ).scalar()

        latest = max(
            last_attendance or datetime.min,
            last_update or datetime.min,
            last_task or datetime.min
        )

        if latest < cutoff_date:
            if not _unresolved_warning_exists(user_id, workspace_id, 'inactivity'):
                create_warning(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    type='inactivity',
                    message=f'No activity for {days_threshold}+ days (last seen {latest.strftime("%Y-%m-%d") if latest != datetime.min else "never"})',
                    reference_date=current_date
                )
                count += 1
    return count