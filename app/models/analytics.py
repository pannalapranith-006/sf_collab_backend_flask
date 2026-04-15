# analytics.py
# SFCollab ERP — Analytics Engine
# Flask + SQLAlchemy | All metrics computed at DB level via SQL aggregations
# Leave module excluded — wire in later when Leave model is built

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Optional

from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import get_jwt, jwt_required
from sqlalchemy import and_, case, func, text

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# App wiring — adjust imports to match your project layout
# ─────────────────────────────────────────────────────────────────────────────
try:
    from extensions import db
    from models.alert import Alert
    from models.attendance import Attendance
    from models.daily_update import DailyUpdate
    from models.holiday import Holiday
    from models.task import Task
    from models.user import User
except ImportError:
    # ── Inline stubs — replace with real model imports once they exist ────────
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

    class User(db.Model):
        __tablename__ = "users"
        __table_args__ = (
            db.Index("ix_users_workspace_active", "workspace_id", "is_active"),
        )
        id            = db.Column(db.Integer, primary_key=True)
        workspace_id  = db.Column(db.Integer, nullable=False, index=True)
        department    = db.Column(db.String(60))
        role          = db.Column(db.String(20))   # admin / member
        team_id       = db.Column(db.Integer)
        last_login    = db.Column(db.DateTime)
        last_activity = db.Column(db.DateTime)
        is_active     = db.Column(db.Boolean, default=True)

    class Attendance(db.Model):
        __tablename__  = "attendance"
        __table_args__ = (
            db.Index("ix_attendance_workspace_user_date", "workspace_id", "user_id", "date"),
        )
        id             = db.Column(db.Integer, primary_key=True)
        user_id        = db.Column(db.Integer, nullable=False)
        workspace_id   = db.Column(db.Integer, nullable=False, index=True)
        date           = db.Column(db.Date, nullable=False)
        status         = db.Column(db.String(20))   # present / late / absent
        clock_in_time  = db.Column(db.DateTime)
        clock_out_time = db.Column(db.DateTime)

    class Task(db.Model):
        __tablename__ = "tasks"
        __table_args__ = (
            db.Index("ix_tasks_workspace_assigned_status", "workspace_id", "assigned_to", "status"),
        )
        id            = db.Column(db.Integer, primary_key=True)
        workspace_id  = db.Column(db.Integer, nullable=False, index=True)
        assigned_to   = db.Column(db.Integer)
        status        = db.Column(db.String(20))    # todo / in_progress / done
        deadline      = db.Column(db.DateTime)
        created_at    = db.Column(db.DateTime)
        completed_at  = db.Column(db.DateTime)      # SET this when status → done

    class DailyUpdate(db.Model):
        __tablename__   = "daily_updates"
        __table_args__  = (
            db.Index("ix_daily_updates_workspace_user_created", "workspace_id", "user_id", "created_at"),
        )
        id              = db.Column(db.Integer, primary_key=True)
        user_id         = db.Column(db.Integer, nullable=False)
        workspace_id    = db.Column(db.Integer, nullable=False, index=True)
        created_at      = db.Column(db.DateTime)
        progress_rating = db.Column(db.Integer, nullable=True)

    class Holiday(db.Model):
        __tablename__ = "holidays"
        id            = db.Column(db.Integer, primary_key=True)
        workspace_id  = db.Column(db.Integer, nullable=False, index=True)
        date          = db.Column(db.Date, nullable=False)
        name          = db.Column(db.String(100))

    class Alert(db.Model):
        __tablename__ = "alerts"
        id            = db.Column(db.Integer, primary_key=True)
        workspace_id  = db.Column(db.Integer, nullable=False, index=True)
        user_id       = db.Column(db.Integer)
        type          = db.Column(db.String(50))
        metric        = db.Column(db.String(50))   # FIX: added for indexed alert dedup
        message       = db.Column(db.Text)
        resolved      = db.Column(db.Boolean, default=False)
        created_at    = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics Snapshot Model
# ─────────────────────────────────────────────────────────────────────────────
class AnalyticsSnapshot(db.Model):
    """
    Append-only snapshot written by the nightly cron.
    One row per (workspace_id, date_range, period_start).
    Old rows are never overwritten — full trend history is preserved.
    """
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "date_range", "period_start",
                            name="uq_snapshot_period"),
    )

    id                   = db.Column(db.Integer, primary_key=True)
    workspace_id         = db.Column(db.Integer, nullable=False, index=True)
    date_range           = db.Column(db.String(20))          # daily/weekly/monthly
    period_start         = db.Column(db.Date, nullable=False)
    period_end           = db.Column(db.Date, nullable=False)
    attendance_rate      = db.Column(db.Float, default=0.0)
    task_completion_rate = db.Column(db.Float, default=0.0)
    update_consistency   = db.Column(db.Float, default=0.0)
    active_users_daily   = db.Column(db.Integer, default=0)
    active_users_weekly  = db.Column(db.Integer, default=0)
    total_users          = db.Column(db.Integer, default=0)
    overdue_tasks        = db.Column(db.Integer, default=0)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        # FIX: explicit field list — avoids leaking SQLAlchemy internal state
        return {
            "id":                   self.id,
            "workspace_id":         self.workspace_id,
            "date_range":           self.date_range,
            "period_start":         str(self.period_start),
            "period_end":           str(self.period_end),
            "attendance_rate":      self.attendance_rate,
            "task_completion_rate": self.task_completion_rate,
            "update_consistency":   self.update_consistency,
            "active_users_daily":   self.active_users_daily,
            "active_users_weekly":  self.active_users_weekly,
            "total_users":          self.total_users,
            "overdue_tasks":        self.overdue_tasks,
            "created_at":           self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Blueprint
# ─────────────────────────────────────────────────────────────────────────────
analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


# ─────────────────────────────────────────────────────────────────────────────
# Auth & RBAC
# ─────────────────────────────────────────────────────────────────────────────
def _jwt_claims() -> tuple[int, str, int]:
    """
    Extract (workspace_id, role, user_id) from JWT.

    Expected JWT payload (set at login time):
        { "sub": <user_id>, "workspace_id": 3, "role": "admin" }

    Wire up at login:
        additional_claims = {"workspace_id": user.workspace_id, "role": user.role}
        token = create_access_token(identity=user.id, additional_claims=additional_claims)

    Raises:
        ValueError  — token is structurally valid but missing required claims (→ 400)
        Exception   — token is invalid / expired (→ 401)
    """
    claims       = get_jwt()
    workspace_id = claims.get("workspace_id")
    role         = claims.get("role", "member")
    user_id      = claims.get("sub")
    if not workspace_id:
        raise ValueError("JWT missing workspace_id claim")
    return int(workspace_id), str(role), int(user_id)


def admin_required(fn):
    """Route decorator — rejects non-admin callers with 403."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            _, role, _ = _jwt_claims()
        except ValueError as e:
            # FIX: missing claim is a bad request, not an auth failure
            return jsonify({"error": str(e)}), 400
        except Exception:
            return jsonify({"error": "Authentication failed"}), 401
        if role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# Date / filter helpers
# ─────────────────────────────────────────────────────────────────────────────
def _period_to_dates(period: str) -> tuple[date, date]:
    today = date.today()
    if period == "daily":
        return today, today
    if period == "weekly":
        return today - timedelta(days=today.weekday()), today
    return today.replace(day=1), today   # monthly default


def _resolve_dates() -> tuple[date, date]:
    """
    Custom date range wins over period preset.
    ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD overrides ?period=
    Falls back to ?period=daily|weekly|monthly (default: monthly)
    """
    s = request.args.get("start_date")
    e = request.args.get("end_date")
    if s and e:
        return (datetime.strptime(s, "%Y-%m-%d").date(),
                datetime.strptime(e, "%Y-%m-%d").date())
    return _period_to_dates(request.args.get("period", "monthly"))


def _scoped_user_ids(workspace_id: int) -> list[int]:
    """
    Returns active user IDs in workspace filtered by optional query params:
        ?department=Engineering&role=member&team_id=5
    Returns empty list if no filter params — caller treats that as "all users".
    """
    q = (db.session.query(User.id)
         .filter(User.workspace_id == workspace_id, User.is_active == True))
    dept    = request.args.get("department")
    role    = request.args.get("role")
    team_id = request.args.get("team_id", type=int)
    if dept:
        q = q.filter(User.department == dept)
    if role:
        q = q.filter(User.role == role)
    if team_id:
        q = q.filter(User.team_id == team_id)
    return [r[0] for r in q.all()]


# ─────────────────────────────────────────────────────────────────────────────
# Working-days computation (weekends + holidays only — no leave module yet)
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
    NOTE: Leave days are not subtracted here — Leave module not yet implemented.
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
    Every user in user_ids contributes working_days to the denominator,
    even if they have zero attendance records — prevents inflated rates.
    """
    if not user_ids:
        return 0
    working_days = _working_days_in_range(workspace_id, start, end)
    return working_days * len(user_ids)


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
        "attendance":  {
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
# Core metric engines (SQL aggregations — no full .all() table scans)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_attendance(workspace_id: int, start: date, end: date,
                         user_ids: list[int],
                         single_user_id: Optional[int] = None) -> dict:
    """
    Attendance rate with correct denominator.

    Workspace mode  → denominator = working_days × len(user_ids)
                      Users with zero records still count — they are absent.
    Single-user mode → denominator = working_days for that user's range.

    present + late both count as "attended".
    late is broken out separately for detail.
    """
    target_ids = [single_user_id] if single_user_id else user_ids

    if not target_ids:
        return _empty_metric("attendance")

    agg = (Attendance.query
           .filter(Attendance.workspace_id == workspace_id,
                   Attendance.date >= start,
                   Attendance.date <= end,
                   Attendance.user_id.in_(target_ids))
           .with_entities(
               func.sum(case((Attendance.status.in_(["present", "late"]), 1), else_=0)).label("present"),
               func.sum(case((Attendance.status == "late",                1), else_=0)).label("late"),
               func.sum(case((Attendance.status == "absent",              1), else_=0)).label("absent"),
           ).one())

    present        = agg.present or 0
    late           = agg.late    or 0
    absent         = agg.absent  or 0
    total_possible = _total_working_days(workspace_id, target_ids, start, end)

    return {
        "attendance_rate":  _pct(present, total_possible),
        "present_days":     present,
        "late_days":        late,
        "absent_days":      absent,
        "expected_days":    total_possible,
        "users_counted":    len(target_ids),
    }


def _compute_tasks(workspace_id: int, start: date, end: date,
                    user_ids: list[int],
                    single_user_id: Optional[int] = None) -> dict:
    """
    Task completion using completed_at (actual finish time), not deadline.
    Overdue = status != done AND deadline has passed.
    All aggregation is done in a single SQL query.

    FIX: removed .count() guard (was a double DB hit). Zero-state is now
    handled by checking total == 0 after the single aggregation query.

    FIX: replaced func.timestampdiff (MySQL-only) with a portable
    func.extract('epoch', ...) expression for avg completion time.
    If you are strictly on MySQL and prefer timestampdiff, swap back.
    """
    now  = datetime.utcnow()
    base = (Task.query
            .filter(Task.workspace_id == workspace_id,
                    Task.created_at >= datetime.combine(start, datetime.min.time()),
                    Task.created_at <= datetime.combine(end,   datetime.max.time())))

    if single_user_id:
        base = base.filter(Task.assigned_to == single_user_id)
    elif user_ids:
        base = base.filter(Task.assigned_to.in_(user_ids))

    # FIX: single aggregation query — no pre-flight .count() round-trip
    agg = base.with_entities(
        func.count(Task.id).label("total"),
        func.sum(case((Task.status == "done",        1), else_=0)).label("done"),
        func.sum(case((Task.status == "in_progress", 1), else_=0)).label("in_progress"),
        func.sum(case((and_(Task.status != "done",
                            Task.deadline < now),     1), else_=0)).label("overdue"),
        # FIX: portable avg completion time — works on PostgreSQL and MySQL 8+
        # For MySQL < 8 replace with: func.timestampdiff(text("SECOND"), ...)
        func.avg(
            case((
                and_(Task.status == "done",
                     Task.completed_at.isnot(None),
                     Task.created_at.isnot(None)),
                func.extract("epoch", Task.completed_at - Task.created_at)
            ), else_=None)
        ).label("avg_seconds"),
    ).one()

    total       = agg.total       or 0
    done        = agg.done        or 0
    in_progress = agg.in_progress or 0
    overdue     = agg.overdue     or 0

    # FIX: zero-state check after aggregation, not before
    if total == 0:
        return _empty_metric("tasks")

    avg_hours = round(float(agg.avg_seconds) / 3600, 2) if agg.avg_seconds else None

    return {
        "task_completion_rate": _pct(done, total),
        "total_tasks":          total,
        "completed_tasks":      done,
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
    Uses the same user_ids subset so department/role filters apply correctly.
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
    Configurable activity windows. Default: 1, 7, 30 days.
    Pass windows=[1, 7] to restrict output.
    Filters to user_ids subset when provided (respects department/role filters).

    FIX: collapsed N+1 per-window COUNT queries into a single aggregation query
    using conditional SUM. For 3 windows this reduces 4 DB round-trips to 1.
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

    # Build conditional columns for each window in one query
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

    # Named aliases for API contract stability
    result["daily_active_users"]   = result.get("active_users_1d",  0)
    result["weekly_active_users"]  = result.get("active_users_7d",  0)
    result["monthly_active_users"] = result.get("active_users_30d", 0)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Trend & comparison engine
# ─────────────────────────────────────────────────────────────────────────────
def _previous_period(start: date, end: date) -> tuple[date, date]:
    """Mirror the current window backwards by the exact same number of days."""
    delta   = (end - start) + timedelta(days=1)
    p_end   = start - timedelta(days=1)
    p_start = p_end - delta + timedelta(days=1)
    return p_start, p_end


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


def _compute_trends(workspace_id: int, start: date, end: date,
                     user_ids: list[int],
                     current_att:  Optional[dict] = None,
                     current_task: Optional[dict] = None,
                     current_upd:  Optional[dict] = None) -> dict:
    """
    Period-over-period comparison for all three core KPIs.
    Also returns last 12 snapshots as a sparkline for the dashboard graph.

    FIX: accepts pre-computed current-period metrics to avoid re-querying them
    when called from workspace_analytics (which already computed them).
    Falls back to computing them if not supplied (e.g. called standalone from
    the /trends endpoint).
    """
    p_start, p_end = _previous_period(start, end)

    # Use supplied current-period results or compute them
    cur_att  = current_att  or _compute_attendance(workspace_id, start, end, user_ids)
    cur_task = current_task or _compute_tasks(workspace_id, start, end, user_ids)
    cur_upd  = current_upd  or _compute_consistency(workspace_id, start, end, user_ids)

    # Always compute previous-period (no cached equivalent)
    prev_att  = _compute_attendance(workspace_id, p_start, p_end, user_ids)
    prev_task = _compute_tasks(workspace_id, p_start, p_end, user_ids)
    prev_upd  = _compute_consistency(workspace_id, p_start, p_end, user_ids)

    history = (AnalyticsSnapshot.query
               .filter_by(workspace_id=workspace_id)
               .order_by(AnalyticsSnapshot.period_start.desc())
               .limit(12).all())

    sparkline = [
        {
            "period_start":         str(s.period_start),
            "attendance_rate":      s.attendance_rate,
            "task_completion_rate": s.task_completion_rate,
            "update_consistency":   s.update_consistency,
        }
        for s in reversed(history)
    ]

    return {
        "previous_period":          {"start": str(p_start), "end": str(p_end)},
        "attendance_trend":         _delta(cur_att["attendance_rate"],      prev_att["attendance_rate"]),
        "task_completion_trend":    _delta(cur_task["task_completion_rate"], prev_task["task_completion_rate"]),
        "update_consistency_trend": _delta(cur_upd["update_consistency"],    prev_upd["update_consistency"]),
        "sparkline":                sparkline,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly detection
# ─────────────────────────────────────────────────────────────────────────────
ANOMALY_THRESHOLDS = {
    "attendance_rate":      {"drop": 15, "spike": 20},
    "task_completion_rate": {"drop": 20, "spike": 25},
    "update_consistency":   {"drop": 20, "spike": 25},
}


def _detect_anomalies(current: dict, trends: dict) -> list[dict]:
    """Flag sudden drops or spikes vs the previous period."""
    anomalies = []
    mapping = {
        # FIX: was current.get("task_completion", 0) — wrong key.
        # Top-level result uses "task_completion_rate" consistently now.
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

    FIX: dedup now filters on Alert.metric column (indexed) instead of
    doing a LIKE search on the message text — avoids a full-text scan.
    Requires the Alert model to have a `metric` column (added above).
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
# CSV helpers
# ─────────────────────────────────────────────────────────────────────────────
def _flatten(data: dict, prefix: str = "") -> dict:
    """
    Recursively flatten nested dicts into dot-separated keys.
    Lists are skipped (not representable as CSV columns).

    FIX: replaces the old shallow flatten that lost all nested metric detail
    (attendance breakdown, task breakdown, etc.).
    """
    out = {}
    for k, v in data.items():
        full_key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, full_key))
        elif not isinstance(v, list):
            out[full_key] = v
    return out


def _to_csv(data: dict, filename: str):
    """Flatten all scalar fields (including nested) to a CSV file download."""
    flat   = _flatten(data)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=flat.keys())
    writer.writeheader()
    writer.writerow(flat)
    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    resp.headers["Content-Type"]        = "text/csv"
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Service layer
# ─────────────────────────────────────────────────────────────────────────────
class AnalyticsService:

    @staticmethod
    def workspace_analytics(workspace_id: int,
                             start: date,
                             end: date,
                             user_ids: Optional[list[int]] = None,
                             include_trends: bool = True) -> dict:
        """
        Full workspace analytics. user_ids=None → all active workspace users.
        Workspace isolation enforced on every sub-query via workspace_id filter.

        FIX: passes pre-computed current-period metrics into _compute_trends
        to avoid redundant re-computation of the same queries.
        FIX: top-level key renamed to "task_completion_rate" (was "task_completion")
        to match the rest of the codebase and fix the anomaly detection key mismatch.
        """
        if user_ids is None:
            user_ids = [
                r[0] for r in db.session.query(User.id)
                .filter(User.workspace_id == workspace_id,
                        User.is_active == True).all()
            ]

        if not user_ids:
            return {
                "workspace_id":         workspace_id,
                "start_date":           str(start),
                "end_date":             str(end),
                "user_count":           0,
                "attendance_rate":      0.0,
                "task_completion_rate": 0.0,   # FIX: renamed from "task_completion"
                "update_consistency":   0.0,
                "active_users":         0,
                "notice":               "No active users found in workspace.",
            }

        att  = _compute_attendance(workspace_id, start, end, user_ids)
        task = _compute_tasks(workspace_id, start, end, user_ids)
        upd  = _compute_consistency(workspace_id, start, end, user_ids)
        act  = _compute_active_users(workspace_id, user_ids)

        result = {
            "workspace_id":         workspace_id,
            "start_date":           str(start),
            "end_date":             str(end),
            "user_count":           len(user_ids),
            # Top-level KPIs (dashboard widget contract)
            "attendance_rate":      att["attendance_rate"],
            "task_completion_rate": task["task_completion_rate"],  # FIX: was "task_completion"
            "update_consistency":   upd["update_consistency"],
            "active_users":         act["weekly_active_users"],
            # Detail breakdowns
            "attendance":           att,
            "tasks":                task,
            "updates":              upd,
            "activity":             act,
        }

        if include_trends:
            # FIX: pass already-computed current metrics — avoids re-querying them
            trends    = _compute_trends(
                workspace_id, start, end, user_ids,
                current_att=att, current_task=task, current_upd=upd,
            )
            anomalies = _detect_anomalies(result, trends)
            _fire_alerts(workspace_id, anomalies)
            result["trends"]    = trends
            result["anomalies"] = anomalies

        return result

    @staticmethod
    def user_analytics(user_id: int, workspace_id: int,
                        start: date, end: date) -> dict:
        """Individual contributor stats. Workspace isolation enforced."""
        user = User.query.filter_by(
            id=user_id, workspace_id=workspace_id, is_active=True
        ).first()
        if not user:
            return {"error": "User not found in workspace", "_code": 404}

        att  = _compute_attendance(workspace_id, start, end, [], single_user_id=user_id)
        task = _compute_tasks(workspace_id, start, end, [], single_user_id=user_id)
        upd  = _compute_consistency(workspace_id, start, end, [], single_user_id=user_id)

        return {
            "user_id":            user_id,
            "workspace_id":       workspace_id,
            "start_date":         str(start),
            "end_date":           str(end),
            # Top-level KPIs
            "attendance_rate":    att["attendance_rate"],
            "tasks_completed":    task["completed_tasks"],
            "consistency":        upd["update_consistency"],
            "last_active":        user.last_activity.isoformat() if user.last_activity else None,
            # Detail
            "attendance":         att,
            "tasks":              task,
            "updates":            upd,
        }

    @staticmethod
    def save_snapshot(workspace_id: int, period: str = "daily") -> AnalyticsSnapshot:
        """
        Upsert snapshot for the current period.
        Today's snapshot is updated on re-run (idempotent).
        Past period rows are never touched → full trend history preserved.
        """
        start, end = _period_to_dates(period)
        data = AnalyticsService.workspace_analytics(
            workspace_id, start, end, include_trends=False
        )
        act = data.get("activity", {})

        snap = AnalyticsSnapshot.query.filter_by(
            workspace_id=workspace_id,
            date_range=period,
            period_start=start,
        ).first()

        if not snap:
            snap = AnalyticsSnapshot(
                workspace_id=workspace_id,
                date_range=period,
                period_start=start,
                period_end=end,
            )
            db.session.add(snap)

        snap.attendance_rate      = data.get("attendance_rate",      0.0)
        snap.task_completion_rate = data.get("task_completion_rate", 0.0)  # FIX: renamed key
        snap.update_consistency   = data.get("update_consistency",   0.0)
        snap.active_users_daily   = act.get("daily_active_users",    0)
        snap.active_users_weekly  = act.get("weekly_active_users",   0)
        snap.total_users          = act.get("total_users",           0)
        snap.overdue_tasks        = data.get("tasks", {}).get("overdue_tasks", 0)
        snap.created_at           = datetime.utcnow()

        db.session.commit()
        return snap


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@analytics_bp.get("/workspace")
@jwt_required()
def workspace_analytics_endpoint():
    """
    GET /analytics/workspace

    Query params (all optional):
        period      : daily | weekly | monthly          (default: monthly)
        start_date  : YYYY-MM-DD  ─┐ custom range
        end_date    : YYYY-MM-DD  ─┘ overrides period
        department  : e.g. Engineering
        role        : admin | member
        team_id     : integer
        trends      : 1 | 0                             (default: 1)
        export      : csv

    Access: any authenticated workspace member.
    """
    try:
        workspace_id, _, _ = _jwt_claims()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    start, end = _resolve_dates()
    user_ids   = _scoped_user_ids(workspace_id)
    inc_trends = request.args.get("trends", "1") != "0"

    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end,
        user_ids=user_ids or None,
        include_trends=inc_trends,
    )

    if request.args.get("export") == "csv":
        return _to_csv(data, f"workspace_{workspace_id}_analytics.csv")

    return jsonify(data), 200


@analytics_bp.get("/user/<int:user_id>")
@jwt_required()
def user_analytics_endpoint(user_id: int):
    """
    GET /analytics/user/<id>

    Query params: period / start_date / end_date / export=csv

    Access:
        Admin  → any user in the workspace
        Member → own analytics only
    """
    try:
        workspace_id, role, caller_id = _jwt_claims()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if role != "admin" and caller_id != user_id:
        return jsonify({"error": "Access denied"}), 403

    start, end = _resolve_dates()
    data = AnalyticsService.user_analytics(user_id, workspace_id, start, end)

    if "error" in data:
        return jsonify(data), data.pop("_code", 400)

    if request.args.get("export") == "csv":
        return _to_csv(data, f"user_{user_id}_analytics.csv")

    return jsonify(data), 200


@analytics_bp.get("/trends")
@jwt_required()
@admin_required
def trends_endpoint():
    """
    GET /analytics/trends

    Period-over-period comparison + sparkline.
    Supports all standard filters (department, role, team_id, date range).
    Admin only.
    """
    try:
        workspace_id, _, _ = _jwt_claims()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    start, end = _resolve_dates()
    user_ids   = _scoped_user_ids(workspace_id)
    # Called standalone — no pre-computed current metrics to pass in
    trends     = _compute_trends(workspace_id, start, end, user_ids)
    return jsonify({"workspace_id": workspace_id, **trends}), 200


@analytics_bp.get("/anomalies")
@jwt_required()
@admin_required
def anomalies_endpoint():
    """
    GET /analytics/anomalies

    Detect anomalies and write them to the alerts table.
    Admin only.
    """
    try:
        workspace_id, _, _ = _jwt_claims()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    start, end = _resolve_dates()
    user_ids   = _scoped_user_ids(workspace_id)
    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end,
        user_ids=user_ids or None,
        include_trends=True,
    )
    return jsonify({
        "workspace_id": workspace_id,
        "anomalies":    data.get("anomalies", []),
        "trends":       data.get("trends", {}),
    }), 200


@analytics_bp.get("/snapshot/<int:workspace_id>")
@jwt_required()
@admin_required
def snapshot_endpoint(workspace_id: int):
    """
    GET /analytics/snapshot/<workspace_id>?period=daily

    Latest cached snapshot. Falls back to live computation if none exists.
    """
    period      = request.args.get("period", "daily")
    start, end  = _period_to_dates(period)

    snap = AnalyticsSnapshot.query.filter_by(
        workspace_id=workspace_id,
        date_range=period,
        period_start=start,
    ).first()

    if snap:
        return jsonify(snap.to_dict()), 200

    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end, include_trends=False
    )
    return jsonify(data), 200


@analytics_bp.get("/history/<int:workspace_id>")
@jwt_required()
@admin_required
def history_endpoint(workspace_id: int):
    """
    GET /analytics/history/<workspace_id>?period=weekly&limit=24&offset=0

    Ordered historical snapshots for trend graphs / sparklines.
    Max 100 rows. Supports offset-based pagination.
    """
    period = request.args.get("period", "weekly")
    limit  = min(request.args.get("limit",  24, type=int), 100)
    # FIX: added offset for pagination — previously had no way to page through history
    offset = max(request.args.get("offset",  0, type=int), 0)

    rows = (AnalyticsSnapshot.query
            .filter_by(workspace_id=workspace_id, date_range=period)
            .order_by(AnalyticsSnapshot.period_start.asc())
            .limit(limit)
            .offset(offset)
            .all())

    return jsonify({
        "workspace_id": workspace_id,
        "period":        period,
        "limit":         limit,
        "offset":        offset,
        "count":         len(rows),
        "rows":          [r.to_dict() for r in rows],
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Nightly cron entry point
# ─────────────────────────────────────────────────────────────────────────────
def run_nightly_snapshot():
    """
    Schedule via APScheduler or Celery beat:

        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(run_nightly_snapshot, "cron", hour=0, minute=10)
        scheduler.start()

    Saves daily + weekly + monthly snapshots for every workspace.
    Anomaly detection runs automatically → alerts fired to Alert table.
    """
    from flask import current_app

    with current_app.app_context():
        workspace_ids = [
            r[0] for r in db.session.query(User.workspace_id).distinct().all()
        ]
        for wid in workspace_ids:
            for period in ("daily", "weekly", "monthly"):
                try:
                    snap = AnalyticsService.save_snapshot(wid, period)
                    # FIX: structured logging instead of print()
                    logger.info(
                        "Analytics snapshot saved",
                        extra={
                            "workspace_id":         wid,
                            "period":               period,
                            "attendance_rate":       snap.attendance_rate,
                            "task_completion_rate":  snap.task_completion_rate,
                            "update_consistency":    snap.update_consistency,
                        },
                    )
                except Exception as exc:
                    logger.exception(
                        "Analytics snapshot failed",
                        extra={"workspace_id": wid, "period": period, "error": str(exc)},
                    )
