from datetime import date, datetime, timedelta

from app.models.attendance import Attendance
from app.models.daily_update import DailyUpdate
from app.models.erp_task import ErpTask
from app.models.holiday import Holiday
from app.models.user import User
from app.models.workspace_member import WorkspaceMember


def _working_days(workspace_id, start_date, end_date):
    holidays = {h.date for h in Holiday.query.filter(
        Holiday.workspace_id == workspace_id,
        Holiday.date >= start_date,
        Holiday.date <= end_date,
    ).all()}

    count = 0
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5 and cur not in holidays:
            count += 1
        cur += timedelta(days=1)
    return count


def _active_member_ids(workspace_id):
    rows = WorkspaceMember.query.filter_by(workspace_id=workspace_id, status='active').all()
    return [r.user_id for r in rows]


def _safe_pct(num, den):
    if not den:
        return 0.0
    return round((num / den) * 100, 2)


def _attendance_rate(workspace_id, start_date, end_date, user_ids):
    if not user_ids:
        return 0.0, 0, 0

    records = Attendance.query.filter(
        Attendance.workspace_id == workspace_id,
        Attendance.user_id.in_(user_ids),
        Attendance.date >= start_date,
        Attendance.date <= end_date,
    ).all()

    presentish = 0
    for r in records:
        status = r.status.value if hasattr(r.status, 'value') else r.status
        if status in ('present', 'late'):
            presentish += 1

    expected = _working_days(workspace_id, start_date, end_date) * len(user_ids)
    return _safe_pct(presentish, expected), presentish, expected


def _task_completion_rate(workspace_id, user_ids=None):
    query = ErpTask.query.filter_by(workspace_id=workspace_id)

    if user_ids is not None:
        query = query.filter(
            (ErpTask.assigned_to.in_(user_ids)) |
            ((ErpTask.assigned_to.is_(None)) & (ErpTask.created_by.in_(user_ids)))
        )

    tasks = query.all()
    total = len(tasks)
    done = 0
    for t in tasks:
        status = t.status.value if hasattr(t.status, 'value') else t.status
        if status == 'done':
            done += 1

    return _safe_pct(done, total), done, total


def _update_consistency(workspace_id, start_date, end_date, user_ids):
    if not user_ids:
        return 0.0, 0, 0

    submitted = DailyUpdate.query.filter(
        DailyUpdate.workspace_id == workspace_id,
        DailyUpdate.user_id.in_(user_ids),
        DailyUpdate.date >= start_date,
        DailyUpdate.date <= end_date,
    ).count()

    expected = _working_days(workspace_id, start_date, end_date) * len(user_ids)
    return _safe_pct(submitted, expected), submitted, expected


def _active_users_metric(user_ids):
    if not user_ids:
        return {'active': 0, 'total': 0, 'rate': 0.0}

    threshold = datetime.utcnow() - timedelta(days=7)
    active = User.query.filter(
        User.id.in_(user_ids),
        User.last_login.isnot(None),
        User.last_login >= threshold,
    ).count()

    total = len(user_ids)
    return {'active': active, 'total': total, 'rate': _safe_pct(active, total)}


def workspace_kpis(workspace_id, start_date, end_date):
    user_ids = _active_member_ids(workspace_id)

    attendance_rate, attendance_presentish, attendance_expected = _attendance_rate(
        workspace_id, start_date, end_date, user_ids
    )
    task_completion_rate, tasks_done, tasks_total = _task_completion_rate(workspace_id)
    update_consistency, updates_submitted, updates_expected = _update_consistency(
        workspace_id, start_date, end_date, user_ids
    )
    active_users = _active_users_metric(user_ids)

    return {
        'attendance_rate': attendance_rate,
        'task_completion_rate': task_completion_rate,
        'update_consistency': update_consistency,
        'active_users': active_users,
        'details': {
            'attendance_presentish': attendance_presentish,
            'attendance_expected': attendance_expected,
            'tasks_done': tasks_done,
            'tasks_total': tasks_total,
            'updates_submitted': updates_submitted,
            'updates_expected': updates_expected,
            'date_start': start_date.isoformat(),
            'date_end': end_date.isoformat(),
        },
    }


def user_kpis(user_id, workspace_id, start_date, end_date):
    attendance_rate, attendance_presentish, attendance_expected = _attendance_rate(
        workspace_id, start_date, end_date, [user_id]
    )
    task_completion_rate, tasks_done, tasks_total = _task_completion_rate(workspace_id, [user_id])
    update_consistency, updates_submitted, updates_expected = _update_consistency(
        workspace_id, start_date, end_date, [user_id]
    )

    user = User.query.get(user_id)
    active = False
    if user and user.last_login:
        active = user.last_login >= (datetime.utcnow() - timedelta(days=7))

    return {
        'attendance_rate': attendance_rate,
        'task_completion_rate': task_completion_rate,
        'update_consistency': update_consistency,
        'active_users': {
            'active': 1 if active else 0,
            'total': 1,
            'rate': 100.0 if active else 0.0,
            'last_login': user.last_login.isoformat() if (user and user.last_login) else None,
        },
        'details': {
            'attendance_presentish': attendance_presentish,
            'attendance_expected': attendance_expected,
            'tasks_done': tasks_done,
            'tasks_total': tasks_total,
            'updates_submitted': updates_submitted,
            'updates_expected': updates_expected,
            'date_start': start_date.isoformat(),
            'date_end': end_date.isoformat(),
        },
    }
