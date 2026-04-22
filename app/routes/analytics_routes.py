"""
routes/analytics_routes.py
────────────────────────────────────────────────────────────────────────────
Analytics engine for SFCollab ERP.

workspace_id passed as ?workspace_id=N query param.
User has no workspace_id column — workspace membership is tracked via
UserActivity records (user_id + workspace_id pairs).
User.is_active is a method, not a column — filter by status enum instead.
User name = first_name + last_name.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Optional

from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import and_, case, func

from app.extensions import db
from app.models.user import User
from app.models.Enums import UserStatus
from app.models.attendance import Attendance
from app.models.analytics import AnalyticsSnapshot
from app.models.erp_support import DailyUpdate, Holiday

logger = logging.getLogger(__name__)

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


# ─────────────────────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────────────────────

def _uid() -> int:
    return int(get_jwt_identity())


def _parse_workspace_id():
    raw = request.args.get('workspace_id')
    if not raw:
        return None, (jsonify({'error': 'workspace_id is required'}), 400)
    try:
        return int(raw), None
    except (ValueError, TypeError):
        return None, (jsonify({'error': 'workspace_id must be an integer'}), 400)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = User.query.get(_uid())
        if not user:
            return jsonify({'error': 'User not found'}), 401
        from app.models.Enums import UserRoles
        if user.role not in (UserRoles.admin,):
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────────────────────────────────────

def _period_to_dates(period: str) -> tuple[date, date]:
    today = date.today()
    if period == 'daily':  return today, today
    if period == 'weekly': return today - timedelta(days=today.weekday()), today
    return today.replace(day=1), today


def _resolve_dates() -> tuple[date, date]:
    s = request.args.get('start_date')
    e = request.args.get('end_date')
    if s and e:
        return (datetime.strptime(s, '%Y-%m-%d').date(),
                datetime.strptime(e, '%Y-%m-%d').date())
    return _period_to_dates(request.args.get('period', 'monthly'))


def _get_workspace_user_ids(workspace_id: int) -> list[int]:
    """
    Returns user IDs that have activity records in this workspace.
    Supports optional ?department / ?role / ?team_id filters if those
    columns exist on User (they don't yet — filters are no-ops until added).
    """
    rows = (UserActivity.query
            .filter_by(workspace_id=workspace_id)
            .with_entities(UserActivity.user_id)
            .distinct().all())
    ids = [r[0] for r in rows]

    # Optional scoping filters — harmless if columns don't exist yet
    dept    = request.args.get('department')
    role    = request.args.get('role')
    if dept or role:
        q = db.session.query(User.id).filter(User.id.in_(ids))
        if hasattr(User, 'department') and dept: q = q.filter(User.department == dept)
        if hasattr(User, 'role') and role:       q = q.filter(User.role == role)
        ids = [r[0] for r in q.all()]

    return ids


# ─────────────────────────────────────────────────────────────────────────────
# Holiday helpers
# ─────────────────────────────────────────────────────────────────────────────

def _holiday_set(workspace_id: int, start: date, end: date) -> set[date]:
    rows = Holiday.query.filter(
        Holiday.workspace_id == workspace_id,
        Holiday.start_date   <= end,
        Holiday.end_date     >= start,
    ).all()
    dates = set()
    for h in rows:
        cur = max(h.start_date, start)
        while cur <= min(h.end_date, end):
            dates.add(cur)
            cur += timedelta(days=1)
    return dates


def _working_days(workspace_id: int, start: date, end: date) -> int:
    holidays = _holiday_set(workspace_id, start, end)
    count, cur = 0, start
    while cur <= end:
        if cur.weekday() < 5 and cur not in holidays:
            count += 1
        cur += timedelta(days=1)
    return count


def _pct(num, den) -> float:
    return round(num / den * 100, 2) if den else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Metric engines
# ─────────────────────────────────────────────────────────────────────────────

def _compute_attendance(workspace_id, start, end, user_ids,
                         single_user_id=None) -> dict:
    target = [single_user_id] if single_user_id else user_ids
    if not target:
        return {'attendance_rate': 0.0, 'present_days': 0, 'late_days': 0,
                'absent_days': 0, 'expected_days': 0, 'users_counted': 0}

    agg = (Attendance.query
           .filter(Attendance.workspace_id == workspace_id,
                   Attendance.date >= start, Attendance.date <= end,
                   Attendance.user_id.in_(target))
           .with_entities(
               func.sum(case((Attendance.status.in_(['present', 'late']), 1), else_=0)).label('present'),
               func.sum(case((Attendance.status == 'late',   1), else_=0)).label('late'),
               func.sum(case((Attendance.status == 'absent', 1), else_=0)).label('absent'),
           ).one())

    present  = agg.present or 0
    expected = _working_days(workspace_id, start, end) * len(target)
    return {
        'attendance_rate': _pct(present, expected),
        'present_days':    present,
        'late_days':       agg.late   or 0,
        'absent_days':     agg.absent or 0,
        'expected_days':   expected,
        'users_counted':   len(target),
    }


def _compute_tasks(workspace_id, start, end, user_ids, single_user_id=None) -> dict:
    from app.models.task import Task
    now  = datetime.utcnow()
    base = Task.query.filter(
        Task.workspace_id == workspace_id,
        Task.created_at   >= datetime.combine(start, datetime.min.time()),
        Task.created_at   <= datetime.combine(end,   datetime.max.time()),
    )
    if single_user_id: base = base.filter(Task.assigned_to == single_user_id)
    elif user_ids:     base = base.filter(Task.assigned_to.in_(user_ids))

    if not base.count():
        return {'task_completion_rate': 0.0, 'total_tasks': 0,
                'completed_tasks': 0, 'in_progress_tasks': 0, 'overdue_tasks': 0}

    agg = base.with_entities(
        func.count(Task.id).label('total'),
        func.sum(case((Task.status == 'done',        1), else_=0)).label('done'),
        func.sum(case((Task.status == 'in_progress', 1), else_=0)).label('in_progress'),
        func.sum(case((and_(Task.status != 'done', Task.deadline < now), 1), else_=0)).label('overdue'),
    ).one()

    total = agg.total or 0
    done  = agg.done  or 0
    return {
        'task_completion_rate': _pct(done, total),
        'total_tasks':          total,
        'completed_tasks':      done,
        'in_progress_tasks':    agg.in_progress or 0,
        'overdue_tasks':        agg.overdue     or 0,
    }


def _compute_consistency(workspace_id, start, end, user_ids, single_user_id=None) -> dict:
    target = [single_user_id] if single_user_id else user_ids
    if not target:
        return {'update_consistency': 0.0, 'submitted_updates': 0,
                'expected_updates': 0, 'avg_progress_rating': None}

    agg = (DailyUpdate.query
           .filter(DailyUpdate.workspace_id == workspace_id,
                   DailyUpdate.created_at >= datetime.combine(start, datetime.min.time()),
                   DailyUpdate.created_at <= datetime.combine(end,   datetime.max.time()),
                   DailyUpdate.user_id.in_(target))
           .with_entities(
               func.count(DailyUpdate.id).label('submitted'),
               func.avg(DailyUpdate.progress_rating).label('avg_rating'),
           ).one())

    submitted = agg.submitted or 0
    expected  = _working_days(workspace_id, start, end) * len(target)
    return {
        'update_consistency':  _pct(submitted, expected),
        'submitted_updates':   submitted,
        'expected_updates':    expected,
        'avg_progress_rating': round(float(agg.avg_rating), 2) if agg.avg_rating else None,
    }


def _compute_active_users(workspace_id, user_ids) -> dict:
    now    = datetime.utcnow()
    base_q = UserActivity.query.filter_by(workspace_id=workspace_id)
    if user_ids:
        base_q = base_q.filter(UserActivity.user_id.in_(user_ids))
    total  = base_q.count()
    result = {'total_users': total}
    for days in [1, 7, 30]:
        cutoff = now - timedelta(days=days)
        result[f'active_users_{days}d'] = base_q.filter(
            UserActivity.last_activity >= cutoff).count()
    result['daily_active_users']   = result.get('active_users_1d',  0)
    result['weekly_active_users']  = result.get('active_users_7d',  0)
    result['monthly_active_users'] = result.get('active_users_30d', 0)
    return result


def _previous_period(start, end):
    delta   = (end - start) + timedelta(days=1)
    p_end   = start - timedelta(days=1)
    p_start = p_end - delta + timedelta(days=1)
    return p_start, p_end


def _delta(current, previous) -> dict:
    change = round(current - previous, 2)
    return {
        'current':    current,
        'previous':   previous,
        'change':     change,
        'change_pct': round(change / previous * 100, 2) if previous else None,
        'direction':  'up' if change > 0 else ('down' if change < 0 else 'flat'),
    }


def _compute_trends(workspace_id, start, end, user_ids) -> dict:
    p_start, p_end = _previous_period(start, end)
    cur_att  = _compute_attendance(workspace_id, start,   end,   user_ids)
    prev_att = _compute_attendance(workspace_id, p_start, p_end, user_ids)
    cur_task = _compute_tasks(workspace_id, start,   end,   user_ids)
    prev_task= _compute_tasks(workspace_id, p_start, p_end, user_ids)
    cur_upd  = _compute_consistency(workspace_id, start,   end,   user_ids)
    prev_upd = _compute_consistency(workspace_id, p_start, p_end, user_ids)

    history  = (AnalyticsSnapshot.query
                .filter_by(workspace_id=workspace_id)
                .order_by(AnalyticsSnapshot.period_start.desc())
                .limit(12).all())
    sparkline = [
        {'period_start':         str(s.period_start),
         'attendance_rate':      s.attendance_rate,
         'task_completion_rate': s.task_completion_rate,
         'update_consistency':   s.update_consistency}
        for s in reversed(history)
    ]
    return {
        'previous_period':          {'start': str(p_start), 'end': str(p_end)},
        'attendance_trend':         _delta(cur_att['attendance_rate'],      prev_att['attendance_rate']),
        'task_completion_trend':    _delta(cur_task['task_completion_rate'],prev_task['task_completion_rate']),
        'update_consistency_trend': _delta(cur_upd['update_consistency'],   prev_upd['update_consistency']),
        'sparkline':                sparkline,
    }


def _detect_anomalies(current, trends) -> list[dict]:
    THRESHOLDS = {
        'attendance_rate':      {'drop': 15, 'spike': 20},
        'task_completion_rate': {'drop': 20, 'spike': 25},
        'update_consistency':   {'drop': 20, 'spike': 25},
    }
    mapping = {
        'attendance_rate':      ('attendance_trend',         current.get('attendance_rate', 0)),
        'task_completion_rate': ('task_completion_trend',    current.get('task_completion', 0)),
        'update_consistency':   ('update_consistency_trend', current.get('update_consistency', 0)),
    }
    anomalies = []
    for metric, (trend_key, value) in mapping.items():
        change = trends.get(trend_key, {}).get('change', 0)
        thr    = THRESHOLDS[metric]
        if change <= -thr['drop']:
            anomalies.append({'metric': metric, 'type': 'sudden_drop',
                               'change': change, 'current': value,
                               'description': f"{metric.replace('_',' ')} dropped by {abs(change):.1f}pp"})
        elif change >= thr['spike']:
            anomalies.append({'metric': metric, 'type': 'sudden_spike',
                               'change': change, 'current': value,
                               'description': f"{metric.replace('_',' ')} spiked by {change:.1f}pp"})
    return anomalies


# ─────────────────────────────────────────────────────────────────────────────
# Service layer
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsService:

    @staticmethod
    def workspace_analytics(workspace_id, start, end,
                             user_ids=None, include_trends=True) -> dict:
        if user_ids is None:
            user_ids = _get_workspace_user_ids(workspace_id)

        if not user_ids:
            return {'workspace_id': workspace_id, 'start_date': str(start),
                    'end_date': str(end), 'user_count': 0,
                    'attendance_rate': 0.0, 'task_completion': 0.0,
                    'update_consistency': 0.0, 'active_users': 0,
                    'notice': 'No users found in workspace.'}

        att  = _compute_attendance(workspace_id, start, end, user_ids)
        task = _compute_tasks(workspace_id, start, end, user_ids)
        upd  = _compute_consistency(workspace_id, start, end, user_ids)
        act  = _compute_active_users(workspace_id, user_ids)

        result = {
            'workspace_id':         workspace_id,
            'start_date':           str(start),
            'end_date':             str(end),
            'user_count':           len(user_ids),
            'total_users':          act['total_users'],
            'attendance_rate':      att['attendance_rate'],
            'task_completion':      task['task_completion_rate'],
            'task_completion_rate': task['task_completion_rate'],
            'update_consistency':   upd['update_consistency'],
            'active_users':         act['weekly_active_users'],
            'active_users_daily':   act['daily_active_users'],
            'active_users_weekly':  act['weekly_active_users'],
            'overdue_tasks':        task['overdue_tasks'],
            'attendance':           att,
            'tasks':                task,
            'updates':              upd,
            'activity':             act,
        }

        if include_trends:
            trends    = _compute_trends(workspace_id, start, end, user_ids)
            anomalies = _detect_anomalies(result, trends)
            result['trends']    = trends
            result['anomalies'] = anomalies

        return result

    @staticmethod
    def user_analytics(user_id, workspace_id, start, end) -> dict:
        user = User.query.get(user_id)
        if not user:
            return {'error': 'User not found', '_code': 404}

        att  = _compute_attendance(workspace_id, start, end, [], single_user_id=user_id)
        task = _compute_tasks(workspace_id, start, end, [], single_user_id=user_id)
        upd  = _compute_consistency(workspace_id, start, end, [], single_user_id=user_id)

        return {
            'user_id':         user_id,
            'workspace_id':    workspace_id,
            'start_date':      str(start),
            'end_date':        str(end),
            'attendance_rate': att['attendance_rate'],
            'tasks_completed': task['completed_tasks'],
            'consistency':     upd['update_consistency'],
            'attendance':      att,
            'tasks':           task,
            'updates':         upd,
        }

    @staticmethod
    def save_snapshot(workspace_id, period='daily') -> AnalyticsSnapshot:
        start, end = _period_to_dates(period)
        data = AnalyticsService.workspace_analytics(
            workspace_id, start, end, include_trends=False)
        act  = data.get('activity', {})

        snap = AnalyticsSnapshot.query.filter_by(
            workspace_id=workspace_id, date_range=period, period_start=start).first()
        if not snap:
            snap = AnalyticsSnapshot(workspace_id=workspace_id, date_range=period,
                                     period_start=start, period_end=end)
            db.session.add(snap)

        snap.attendance_rate      = data.get('attendance_rate', 0.0)
        snap.task_completion_rate = data.get('task_completion', 0.0)
        snap.update_consistency   = data.get('update_consistency', 0.0)
        snap.active_users_daily   = act.get('daily_active_users', 0)
        snap.active_users_weekly  = act.get('weekly_active_users', 0)
        snap.total_users          = act.get('total_users', 0)
        snap.overdue_tasks        = data.get('tasks', {}).get('overdue_tasks', 0)
        snap.created_at           = datetime.utcnow()
        db.session.commit()
        return snap


# ─────────────────────────────────────────────────────────────────────────────
# CSV helper
# ─────────────────────────────────────────────────────────────────────────────

def _to_csv(data, filename):
    flat   = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=flat.keys())
    writer.writeheader()
    writer.writerow(flat)
    resp = make_response(output.getvalue())
    resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
    resp.headers['Content-Type']        = 'text/csv'
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.get('/workspace')
@jwt_required()
def workspace_analytics_endpoint():
    workspace_id, err = _parse_workspace_id()
    if err: return err

    start, end = _resolve_dates()
    user_ids   = _get_workspace_user_ids(workspace_id)
    inc_trends = request.args.get('trends', '1') != '0'

    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end,
        user_ids=user_ids or None,
        include_trends=inc_trends,
    )
    if request.args.get('export') == 'csv':
        return _to_csv(data, f'workspace_{workspace_id}_analytics.csv')
    return jsonify(data), 200


@analytics_bp.get('/user/<int:user_id>')
@jwt_required()
def user_analytics_endpoint(user_id):
    caller_id    = _uid()
    caller       = User.query.get(caller_id)
    from app.models.Enums import UserRoles
    if caller.role != UserRoles.admin and caller_id != user_id:
        return jsonify({'error': 'Access denied'}), 403

    workspace_id, err = _parse_workspace_id()
    if err: return err

    start, end = _resolve_dates()
    data = AnalyticsService.user_analytics(user_id, workspace_id, start, end)
    if 'error' in data:
        code = data.pop('_code', 400)
        return jsonify(data), code
    if request.args.get('export') == 'csv':
        return _to_csv(data, f'user_{user_id}_analytics.csv')
    return jsonify(data), 200


@analytics_bp.get('/trends')
@jwt_required()
@admin_required
def trends_endpoint():
    workspace_id, err = _parse_workspace_id()
    if err: return err

    start, end = _resolve_dates()
    user_ids   = _get_workspace_user_ids(workspace_id)
    trends     = _compute_trends(workspace_id, start, end, user_ids)
    return jsonify({'workspace_id': workspace_id, **trends}), 200


@analytics_bp.get('/anomalies')
@jwt_required()
@admin_required
def anomalies_endpoint():
    workspace_id, err = _parse_workspace_id()
    if err: return err

    start, end = _resolve_dates()
    user_ids   = _get_workspace_user_ids(workspace_id)
    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end, user_ids=user_ids or None, include_trends=True)
    return jsonify({'workspace_id': workspace_id,
                    'anomalies': data.get('anomalies', []),
                    'trends':    data.get('trends', {})}), 200


@analytics_bp.get('/snapshot/<int:workspace_id>')
@jwt_required()
@admin_required
def snapshot_endpoint(workspace_id):
    period     = request.args.get('period', 'daily')
    start, end = _period_to_dates(period)
    snap = AnalyticsSnapshot.query.filter_by(
        workspace_id=workspace_id, date_range=period, period_start=start).first()
    if snap:
        return jsonify(snap.to_dict()), 200
    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end, include_trends=False)
    return jsonify(data), 200


@analytics_bp.get('/history/<int:workspace_id>')
@jwt_required()
@admin_required
def history_endpoint(workspace_id):
    period = request.args.get('period', 'weekly')
    limit  = min(request.args.get('limit', 24, type=int), 100)
    rows   = (AnalyticsSnapshot.query
              .filter_by(workspace_id=workspace_id, date_range=period)
              .order_by(AnalyticsSnapshot.period_start.asc())
              .limit(limit).all())
    return jsonify([r.to_dict() for r in rows]), 200


def run_nightly_snapshot():
    from flask import current_app
    with current_app.app_context():
        workspace_ids = [r[0] for r in
                         db.session.query(UserActivity.workspace_id).distinct().all()]
        for wid in workspace_ids:
            for period in ('daily', 'weekly', 'monthly'):
                try:
                    AnalyticsService.save_snapshot(wid, period)
                except Exception as exc:
                    logger.error(f'[Analytics][ERR] workspace={wid} period={period} → {exc}')

