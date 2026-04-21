# services/analytics_service.py
# SFCollab ERP — Analytics business logic
# Pure computation: no Flask request/response objects, no auth, no Blueprint

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import case, func

from extensions import db
from models.alert import Alert
from models.attendance import Attendance
from models.daily_update import DailyUpdate
from models.holiday import Holiday
from models.task import Task
from models.user import User
from models.analytics import AnalyticsSnapshot
from utils.date_utils import period_to_dates, previous_period

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

ANOMALY_THRESHOLDS = {
    "attendance_rate":      {"drop": 15, "spike": 20},
    "task_completion_rate": {"drop": 20, "spike": 25},
    "update_consistency":   {"drop": 20, "spike": 25},
}


# ─────────────────────────────────────────────────────────────────────────────
# Safe math
# ─────────────────────────────────────────────────────────────────────────────

def _pct(num, den) -> float:
    return round(num / den * 100, 2) if den else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Empty metric payloads (zero-state guard)
# ─────────────────────────────────────────────────────────────────────────────

def _empty_metric(kind: str) -> dict:
    bases = {
        "attendance": {
            "attendance_rate": 0.0, "present_days": 0, "late_days": 0,
            "absent_days": 0, "expected_days": 0, "users_counted": 0,
        },
        "tasks": {
            "task_completion_rate": 0.0, "total_tasks": 0, "completed_tasks": 0,
            "in_progress_tasks": 0, "overdue_tasks": 0, "avg_completion_hours": None,
        },
        "consistency": {
            "update_consistency": 0.0, "submitted_updates": 0, "expected_updates": 0,
            "avg_progress_rating": None, "users_counted": 0,
        },
    }
    return bases.get(kind, {})


# ─────────────────────────────────────────────────────────────────────────────
# Working-days computation (weekends + holidays — leave module wired in later)
# ─────────────────────────────────────────────────────────────────────────────

def _holiday_set(workspace_id: int, start: date, end: date) -> set[date]:
    rows = (Holiday.query
            .filter(Holiday.workspace_id == workspace_id,
                    Holiday.date >= start,
                    Holiday.date <= end)
            .with_entities(Holiday.date).all())
    return {r[0] for r in rows}


def _working_days_in_range(workspace_id: int, start: date, end: date) -> int:
    """
    Count working days excluding weekends and workspace holidays.
    NOTE: Leave days are not subtracted — Leave module not yet implemented.
    When Leave model is added, fetch approved leave dates per user and subtract.
    """
    holidays  = _holiday_set(workspace_id, start, end)
    count, cur = 0, start
    while cur <= end:
        if cur.weekday() < 5 and cur not in holidays:
            count += 1
        cur += timedelta(days=1)
    return count


def _total_working_days(workspace_id: int, user_ids: list[int],
                         start: date, end: date) -> int:
    """
    Total expected attendance slots = working_days × number_of_users.
    Every user in user_ids contributes to the denominator even with zero
    attendance records — prevents inflated rates.
    """
    if not user_ids:
        return 0
    return _working_days_in_range(workspace_id, start, end) * len(user_ids)


# ─────────────────────────────────────────────────────────────────────────────
# Core metric engines (SQL aggregations — no full table scans)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_attendance(workspace_id: int, start: date, end: date,
                         user_ids: list[int],
                         single_user_id: Optional[int] = None) -> dict:
    target_ids = [single_user_id] if single_user_id else user_ids

    if not target_ids:
        return _empty_metric("attendance")

    agg = (Attendance.query
           .filter(Attendance.workspace_id == workspace_id,
                   Attendance.date >= start,
                   Attendance.date <= end,
                   Attendance.user_id.in_(target_ids))
           .with_entities(
               func.count(Attendance.id).label("total"),
               func.sum(case((Attendance.status == "present", 1), else_=0)).label("present"),
               func.sum(case((Attendance.status == "late",    1), else_=0)).label("late"),
               func.sum(case((Attendance.status == "absent",  1), else_=0)).label("absent"),
           ).one())

    total    = agg.total   or 0
    present  = agg.present or 0
    late     = agg.late    or 0
    absent   = agg.absent  or 0
    expected = _total_working_days(workspace_id, target_ids, start, end)

    return {
        "attendance_rate": _pct(present + late, expected),
        "present_days":    present,
        "late_days":       late,
        "absent_days":     absent,
        "expected_days":   expected,
        "users_counted":   len(target_ids),
    }


def _compute_tasks(workspace_id: int, start: date, end: date,
                    user_ids: list[int],
                    single_user_id: Optional[int] = None) -> dict:
    target_ids = [single_user_id] if single_user_id else user_ids
    now        = datetime.utcnow()

    q = Task.query.filter(Task.workspace_id == workspace_id)
    if target_ids:
        q = q.filter(Task.assigned_to.in_(target_ids))

    agg = q.with_entities(
        func.count(Task.id).label("total"),
        func.sum(case((Task.status == "done",        1), else_=0)).label("completed"),
        func.sum(case((Task.status == "in_progress", 1), else_=0)).label("in_progress"),
        func.sum(case(
            ((Task.status != "done", Task.deadline < now), 1), else_=0
        )).label("overdue"),
        func.avg(
            case(
                (Task.status == "done",
                 func.timestampdiff(
                    ("HOUR"), Task.created_at, Task.completed_at
                 )),
                else_=None,
            )
        ).label("avg_hours"),
    ).one()

    total       = agg.total       or 0
    completed   = agg.completed   or 0
    in_progress = agg.in_progress or 0
    overdue     = agg.overdue     or 0
    avg_hours   = round(float(agg.avg_hours), 2) if agg.avg_hours else None

    return {
        "task_completion_rate": _pct(completed, total),
        "total_tasks":          total,
        "completed_tasks":      completed,
        "in_progress_tasks":    in_progress,
        "overdue_tasks":        overdue,
        "avg_completion_hours": avg_hours,
    }


def _compute_consistency(workspace_id: int, start: date, end: date,
                          user_ids: list[int],
                          single_user_id: Optional[int] = None) -> dict:
    """
    Update consistency = submitted / expected.
    Expected = 1 update per working day per active user in the target subset.
    """
    target_ids = [single_user_id] if single_user_id else user_ids

    if not target_ids:
        return _empty_metric("consistency")

    agg = (DailyUpdate.query
           .filter(DailyUpdate.workspace_id == workspace_id,
                   DailyUpdate.created_at >= datetime.combine(start, datetime.min.time()),
                   DailyUpdate.created_at <= datetime.combine(end,   datetime.max.time()),
                   DailyUpdate.user_id.in_(target_ids))
           .with_entities(
               func.count(DailyUpdate.id).label("submitted"),
               func.avg(DailyUpdate.progress_rating).label("avg_rating"),
           ).one())

    submitted  = agg.submitted or 0
    avg_rating = round(float(agg.avg_rating), 2) if agg.avg_rating else None
    expected   = _total_working_days(workspace_id, target_ids, start, end)

    return {
        "update_consistency":  _pct(submitted, expected),
        "submitted_updates":   submitted,
        "expected_updates":    expected,
        "avg_progress_rating": avg_rating,
        "users_counted":       len(target_ids),
    }


def _compute_active_users(workspace_id: int,
                           user_ids: list[int],
                           windows: Optional[list[int]] = None) -> dict:
    """
    Configurable activity windows (default: 1, 7, 30 days).
    Collapses N window queries into a single aggregation via conditional SUM.
    """
    if windows is None:
        windows = [1, 7, 30]

    now  = datetime.utcnow()
    base = db.session.query(User).filter(
        User.workspace_id == workspace_id,
        User.is_active == True,
    )
    if user_ids:
        base = base.filter(User.id.in_(user_ids))

    window_cases = [
        func.sum(
            case((User.last_activity >= now - timedelta(days=d), 1), else_=0)
        ).label(f"active_{d}d")
        for d in windows
    ]

    row = base.with_entities(
        func.count(User.id).label("total"),
        *window_cases,
    ).one()

    result = {"total_users": row.total or 0}
    for d in windows:
        result[f"active_users_{d}d"] = getattr(row, f"active_{d}d") or 0

    result["daily_active_users"]   = result.get("active_users_1d",  0)
    result["weekly_active_users"]  = result.get("active_users_7d",  0)
    result["monthly_active_users"] = result.get("active_users_30d", 0)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Trend helpers
# ─────────────────────────────────────────────────────────────────────────────

def _delta(current: float, previous: float) -> dict:
    change = round(current - previous, 2)
    pct    = round(change / previous * 100, 2) if previous else None
    return {
        "current":    current,
        "previous":   previous,
        "change":     change,
        "change_pct": pct,
        "direction":  "up" if change > 0 else ("down" if change < 0 else "flat"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_anomalies(current: dict, trends: dict) -> list[dict]:
    """Flag sudden drops or spikes vs the previous period."""
    anomalies = []
    mapping = {
        "attendance_rate":      ("attendance_trend",         current.get("attendance_rate",      0)),
        "task_completion_rate": ("task_completion_trend",    current.get("task_completion_rate", 0)),
        "update_consistency":   ("update_consistency_trend", current.get("update_consistency",   0)),
    }
    for metric, (trend_key, value) in mapping.items():
        trend  = trends.get(trend_key, {})
        change = trend.get("change", 0)
        thr    = ANOMALY_THRESHOLDS[metric]
        if change <= -thr["drop"]:
            anomalies.append({
                "metric":   metric,
                "type":     "sudden_drop",
                "change":   change,
                "current":  value,
                "severity": "high" if abs(change) > thr["drop"] * 1.5 else "medium",
            })
        elif change >= thr["spike"]:
            anomalies.append({
                "metric":   metric,
                "type":     "sudden_spike",
                "change":   change,
                "current":  value,
                "severity": "low",
            })
    return anomalies


def _fire_alerts(workspace_id: int, anomalies: list[dict]) -> None:
    """
    Write anomaly alerts to the Alert table. Skips duplicates.
    Dedup filters on Alert.metric column (indexed) — avoids full-text scan.
    """
    for a in anomalies:
        alert_type = f"analytics_{a['type']}"
        exists = (Alert.query
                  .filter_by(
                      workspace_id=workspace_id,
                      type=alert_type,
                      metric=a["metric"],
                      resolved=False,
                  )
                  .first())
        if exists:
            continue
        db.session.add(Alert(
            workspace_id=workspace_id,
            type=alert_type,
            metric=a["metric"],
            message=(
                f"{a['metric'].replace('_', ' ').title()} {a['type'].replace('_', ' ')} "
                f"by {abs(a['change'])}pp. Current: {a['current']}%. "
                f"Severity: {a['severity']}."
            ),
            resolved=False,
        ))
    db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# AnalyticsService — public API consumed by routes
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsService:

    @staticmethod
    def workspace_analytics(
        workspace_id: int,
        start: date,
        end: date,
        user_ids: Optional[list[int]] = None,
        include_trends: bool = True,
    ) -> dict:
        ids = user_ids or []

        attendance  = _compute_attendance(workspace_id, start, end, ids)
        tasks       = _compute_tasks(workspace_id, start, end, ids)
        consistency = _compute_consistency(workspace_id, start, end, ids)
        active      = _compute_active_users(workspace_id, ids)

        result: dict = {
            "workspace_id":         workspace_id,
            "period_start":         str(start),
            "period_end":           str(end),
            "attendance_rate":      attendance["attendance_rate"],
            "task_completion_rate": tasks["task_completion_rate"],
            "update_consistency":   consistency["update_consistency"],
            "attendance":           attendance,
            "tasks":                tasks,
            "consistency":          consistency,
            "active_users":         active,
        }

        if include_trends:
            p_start, p_end = previous_period(start, end)
            prev_att  = _compute_attendance(workspace_id, p_start, p_end, ids)
            prev_task = _compute_tasks(workspace_id, p_start, p_end, ids)
            prev_cons = _compute_consistency(workspace_id, p_start, p_end, ids)

            trends = {
                "attendance_trend":         _delta(attendance["attendance_rate"],      prev_att["attendance_rate"]),
                "task_completion_trend":    _delta(tasks["task_completion_rate"],      prev_task["task_completion_rate"]),
                "update_consistency_trend": _delta(consistency["update_consistency"],  prev_cons["update_consistency"]),
            }
            anomalies = _detect_anomalies(result, trends)
            if anomalies:
                _fire_alerts(workspace_id, anomalies)

            result["trends"]    = trends
            result["anomalies"] = anomalies

        return result

    @staticmethod
    def user_analytics(
        user_id: int,
        workspace_id: int,
        start: date,
        end: date,
    ) -> dict:
        user = User.query.filter_by(id=user_id, workspace_id=workspace_id).first()
        if not user:
            return {"error": "User not found", "_code": 404}

        return {
            "user_id":      user_id,
            "workspace_id": workspace_id,
            "period_start": str(start),
            "period_end":   str(end),
            "attendance":   _compute_attendance(workspace_id, start, end, [], single_user_id=user_id),
            "tasks":        _compute_tasks(workspace_id, start, end, [], single_user_id=user_id),
            "consistency":  _compute_consistency(workspace_id, start, end, [], single_user_id=user_id),
        }

    @staticmethod
    def save_snapshot(workspace_id: int, period: str) -> AnalyticsSnapshot:
        start, end = period_to_dates(period)
        data       = AnalyticsService.workspace_analytics(
            workspace_id, start, end, include_trends=False
        )
        active = data["active_users"]

        snap = AnalyticsSnapshot.query.filter_by(
            workspace_id=workspace_id,
            date_range=period,
            period_start=start,
        ).first()

        if snap is None:
            snap = AnalyticsSnapshot(
                workspace_id=workspace_id,
                date_range=period,
                period_start=start,
            )
            db.session.add(snap)

        snap.period_end           = end
        snap.attendance_rate      = data["attendance_rate"]
        snap.task_completion_rate = data["task_completion_rate"]
        snap.update_consistency   = data["update_consistency"]
        snap.active_users_daily   = active.get("daily_active_users",   0)
        snap.active_users_weekly  = active.get("weekly_active_users",  0)
        snap.total_users          = active.get("total_users",           0)
        snap.overdue_tasks        = data["tasks"]["overdue_tasks"]

        db.session.commit()
        return snap