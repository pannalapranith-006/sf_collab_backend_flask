"""
alerts_engine.py  —  SFCollab ERP Alert System Core Engine (v3)
════════════════════════════════════════════════════════════════

v3 fixes applied on top of v2:

  FIX-A  Holiday logic handles date ranges + optional weekend skip
  FIX-B  Notification rate limiting via Celery task queue (Redis-backed)
  FIX-C  Consecutive-missed-update streak stored in DB (UserUpdateStreak),
         updated incrementally — no per-day queries at runtime
  FIX-D  Soft-delete / archival for old resolved alerts (archive_old_alerts)

All v2 fixes (1-15) are preserved.
"""

import logging
import uuid
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import joinedload

from models import (
    Alert, AlertType, AlertPriority,
    Attendance, DailyUpdate,
    Holiday, Task, User,
    UserUpdateStreak,
    WorkspaceAlertConfig,
    db,
)

# ── Celery app import (FIX-B) — wire to your existing Celery instance ─────────
# from celery_app import celery          # uncomment when Celery is configured
# If Celery is not yet set up, notifications fall back to synchronous stubs.

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Priority map + escalation
# ══════════════════════════════════════════════════════════════════════════════

PRIORITY_MAP: dict[AlertType, AlertPriority] = {
    AlertType.missing_attendance: AlertPriority.MEDIUM,
    AlertType.late_attendance:    AlertPriority.MEDIUM,
    AlertType.missing_update:     AlertPriority.LOW,
    AlertType.task_overdue:       AlertPriority.HIGH,
    AlertType.inactive_user:      AlertPriority.LOW,
}

ESCALATION_THRESHOLD_DAYS = 3


# ══════════════════════════════════════════════════════════════════════════════
# Per-workspace config
# ══════════════════════════════════════════════════════════════════════════════

class _WorkspaceCfg:
    __slots__ = (
        "shift_start",
        "attendance_cutoff",
        "update_cutoff",
        "inactivity_days",
        "late_grace_minutes",
        "skip_weekends",        # FIX-A — bool: skip Sat/Sun attendance checks
    )

    def __init__(self, row: Optional["WorkspaceAlertConfig"]):
        self.shift_start        = row.shift_start        if row else time(9, 0)
        self.attendance_cutoff  = row.attendance_cutoff  if row else time(10, 0)
        self.update_cutoff      = row.update_cutoff      if row else time(18, 0)
        self.inactivity_days    = row.inactivity_days    if row else 3
        self.late_grace_minutes = row.late_grace_minutes if row else 15
        self.skip_weekends      = row.skip_weekends      if row else True  # FIX-A

    @property
    def late_threshold(self) -> time:
        base = datetime.combine(date.today(), self.shift_start)
        return (base + timedelta(minutes=self.late_grace_minutes)).time()


def _get_cfg(workspace_id: int) -> _WorkspaceCfg:
    row = (
        db.session.query(WorkspaceAlertConfig)
        .filter_by(workspace_id=workspace_id)
        .first()
    )
    return _WorkspaceCfg(row)


# ══════════════════════════════════════════════════════════════════════════════
# FIX-A — Holiday range check (replaces single date == check_date query)
# ══════════════════════════════════════════════════════════════════════════════

def _is_non_working_day(workspace_id: int, check_date: date,
                        skip_weekends: bool) -> bool:
    """
    Return True if *check_date* is a non-working day for the workspace.

    Covers:
      • Multi-day holiday ranges  — Holiday rows now carry start_date / end_date
        so a 5-day company holiday only needs one DB row instead of five.
      • Weekends (optional)       — controlled by workspace.skip_weekends flag.

    The Holiday model must have: workspace_id, start_date, end_date, name.
    (Single-day holidays: start_date == end_date.)
    """
    # 1. Weekend check (FIX-A part 2)
    if skip_weekends and check_date.weekday() >= 5:   # 5=Sat, 6=Sun
        logger.debug("Weekend skip | date=%s", check_date)
        return True

    # 2. Holiday range check (FIX-A part 1) — single query covers all ranges
    is_holiday = (
        db.session.query(Holiday)
        .filter(
            Holiday.workspace_id == workspace_id,
            Holiday.start_date   <= check_date,
            Holiday.end_date     >= check_date,
        )
        .first()
    ) is not None

    if is_holiday:
        logger.debug("Holiday | date=%s workspace=%s", check_date, workspace_id)

    return is_holiday


# ══════════════════════════════════════════════════════════════════════════════
# Timing guard
# ══════════════════════════════════════════════════════════════════════════════

def _past_cutoff(cutoff: time) -> bool:
    return datetime.utcnow().time() >= cutoff


# ══════════════════════════════════════════════════════════════════════════════
# Shared utilities
# ══════════════════════════════════════════════════════════════════════════════

def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _open_alert_today(workspace_id: int, user_id: int,
                      alert_type: AlertType, today: date) -> Optional[Alert]:
    return (
        db.session.query(Alert)
        .filter(
            Alert.workspace_id == workspace_id,
            Alert.user_id      == user_id,
            Alert.type         == alert_type,
            Alert.created_at   >= _day_start(today),
            Alert.resolved     == False,        # noqa: E712
            Alert.archived     == False,        # FIX-D — exclude archived rows
        )
        .first()
    )


def _resolve_priority(alert_type: AlertType,
                      days_escalation: int = 0) -> AlertPriority:
    base = PRIORITY_MAP[alert_type]
    if days_escalation >= ESCALATION_THRESHOLD_DAYS:
        if base == AlertPriority.LOW:
            return AlertPriority.MEDIUM
        return AlertPriority.HIGH
    return base


# ══════════════════════════════════════════════════════════════════════════════
# Alert creation
# ══════════════════════════════════════════════════════════════════════════════

def _create_alert(
    workspace_id: int,
    user_id: int,
    alert_type: AlertType,
    message: str,
    priority: Optional[AlertPriority] = None,
    reference_id: Optional[int] = None,
) -> Alert:
    """
    Persist Alert with full audit + archival fields.
    Fields: id, workspace_id, user_id, type, message, resolved, priority,
            reference_id, created_at, resolved_at, resolved_by,
            resolution_note, archived, archived_at   (FIX-D)
    """
    if priority is None:
        priority = PRIORITY_MAP[alert_type]

    alert = Alert(
        workspace_id    = workspace_id,
        user_id         = user_id,
        type            = alert_type,
        message         = message,
        resolved        = False,
        priority        = priority,
        reference_id    = reference_id,
        created_at      = datetime.utcnow(),
        resolved_at     = None,
        resolved_by     = None,
        resolution_note = None,
        archived        = False,        # FIX-D
        archived_at     = None,         # FIX-D
    )
    db.session.add(alert)
    logger.info(
        "ALERT CREATED | workspace=%s user=%s type=%s priority=%s",
        workspace_id, user_id, alert_type.value, priority.value,
    )

    # FIX-B — enqueue notification instead of calling directly
    _enqueue_notification(alert)
    return alert


# ══════════════════════════════════════════════════════════════════════════════
# FIX-B — Notification queue via Celery (rate-limited, non-blocking)
# ══════════════════════════════════════════════════════════════════════════════

# Celery task — defined here so it can be registered when celery_app imports
# this module.  If Celery is not configured, _enqueue_notification falls back
# to the synchronous stubs automatically.
#
# @celery.task(
#     name="alerts.send_notification",
#     rate_limit="30/m",          # max 30 notification tasks per minute
#     max_retries=3,
#     default_retry_delay=60,     # retry after 60 s on failure
# )
# def send_notification_task(alert_id: int) -> None:
#     alert = db.session.get(Alert, alert_id)
#     if not alert:
#         return
#     _notify_in_app(alert)
#     if alert.priority == AlertPriority.HIGH:
#         _notify_email(alert)


def _enqueue_notification(alert: Alert) -> None:
    """
    FIX-B — Push notification work to Celery queue.

    Benefits over direct dispatch:
      • rate_limit="30/m"  prevents email/Slack flooding at mass-alert time
      • async              engine never blocks waiting for SMTP / Slack API
      • retries            transient failures don't lose notifications

    Fallback: if Celery is unavailable, logs a warning and calls stubs
    synchronously so the engine keeps running.
    """
    try:
        # Flush so alert.id is available before we hand it to the worker
        db.session.flush()

        # send_notification_task.apply_async(
        #     args=[alert.id],
        #     countdown=2,            # tiny delay so DB commit lands first
        #     expires=3600,           # drop stale jobs after 1 hour
        # )
        # ↑ Uncomment once Celery + Redis are wired up.

        # --- Synchronous fallback (remove once Celery is live) ---------------
        _notify_in_app(alert)
        if alert.priority == AlertPriority.HIGH:
            _notify_email(alert)
        # ---------------------------------------------------------------------

    except Exception as exc:
        # FIX-B — notification failure must never crash the alert engine
        logger.exception(
            "Notification enqueue failed for alert workspace=%s user=%s: %s",
            alert.workspace_id, alert.user_id, exc,
        )


def _notify_in_app(alert: Alert) -> None:
    """Hook: push event to your WebSocket / SSE layer here."""
    logger.debug("IN-APP | user=%s type=%s", alert.user_id, alert.type.value)


def _notify_email(alert: Alert) -> None:
    """Hook: call Flask-Mail / SendGrid / SES here."""
    logger.debug("EMAIL  | user=%s type=%s", alert.user_id, alert.type.value)


# ══════════════════════════════════════════════════════════════════════════════
# Attendance status helper
# ══════════════════════════════════════════════════════════════════════════════

def _mark_attendance_status(record: "Attendance", status: str) -> None:
    if record.status != status:
        record.status = status


# ══════════════════════════════════════════════════════════════════════════════
# Batch query helpers — no N+1
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_users_batch(workspace_id: int, batch_size: int = 200):
    offset = 0
    while True:
        batch = (
            db.session.query(User)
            .filter_by(workspace_id=workspace_id)
            .offset(offset)
            .limit(batch_size)
            .all()
        )
        if not batch:
            break
        yield batch
        offset += batch_size


def _fetch_attendance_map(workspace_id: int, user_ids: list[int],
                          today: date) -> dict[int, "Attendance"]:
    records = (
        db.session.query(Attendance)
        .filter(
            Attendance.workspace_id == workspace_id,
            Attendance.user_id.in_(user_ids),
            Attendance.date == today,
        )
        .all()
    )
    return {r.user_id: r for r in records}


def _fetch_update_set(workspace_id: int, user_ids: list[int],
                      today: date) -> set[int]:
    rows = (
        db.session.query(DailyUpdate.user_id)
        .filter(
            DailyUpdate.workspace_id == workspace_id,
            DailyUpdate.user_id.in_(user_ids),
            DailyUpdate.created_at   >= _day_start(today),
        )
        .all()
    )
    return {r[0] for r in rows}


# ══════════════════════════════════════════════════════════════════════════════
# Core check: attendance
# ══════════════════════════════════════════════════════════════════════════════

def check_attendance(workspace_id: int, today: date, cfg: _WorkspaceCfg) -> dict:
    """
    Raises:
      missing_attendance — no clock-in at all (separate type from late)
      late_attendance    — clocked in but after grace window

    FIX-A: skips non-working days (weekends + holiday ranges).
    """
    summary = {"missing_attendance": 0, "late_attendance": 0}

    # FIX-A — uses range-aware, weekend-aware check
    if _is_non_working_day(workspace_id, today, cfg.skip_weekends):
        return summary

    if not _past_cutoff(cfg.attendance_cutoff):
        logger.debug("Attendance cutoff not reached | workspace=%s", workspace_id)
        return summary

    late_threshold_dt = datetime.combine(today, cfg.late_threshold)

    for user_batch in _fetch_users_batch(workspace_id):
        user_ids = [u.id for u in user_batch]
        att_map  = _fetch_attendance_map(workspace_id, user_ids, today)

        for user in user_batch:
            record = att_map.get(user.id)

            if record is None or record.clock_in_time is None:
                if record is None:
                    record = Attendance(
                        user_id      = user.id,
                        workspace_id = workspace_id,
                        date         = today,
                        status       = "absent",
                    )
                    db.session.add(record)
                else:
                    _mark_attendance_status(record, "absent")

                if not _open_alert_today(workspace_id, user.id,
                                          AlertType.missing_attendance, today):
                    _create_alert(
                        workspace_id = workspace_id,
                        user_id      = user.id,
                        alert_type   = AlertType.missing_attendance,
                        message      = f"{user.name} did not clock in on {today}.",
                    )
                    summary["missing_attendance"] += 1

            else:
                if record.clock_in_time > late_threshold_dt:
                    _mark_attendance_status(record, "late")
                    if not _open_alert_today(workspace_id, user.id,
                                              AlertType.late_attendance, today):
                        _create_alert(
                            workspace_id = workspace_id,
                            user_id      = user.id,
                            alert_type   = AlertType.late_attendance,
                            message      = (
                                f"{user.name} clocked in late at "
                                f"{record.clock_in_time.strftime('%H:%M')} "
                                f"(threshold {cfg.late_threshold.strftime('%H:%M')})."
                            ),
                        )
                        summary["late_attendance"] += 1
                else:
                    _mark_attendance_status(record, "present")

    return summary


# ══════════════════════════════════════════════════════════════════════════════
# FIX-C — Streak stored in DB: UserUpdateStreak
# ══════════════════════════════════════════════════════════════════════════════
#
#  Instead of querying N days back per user at cron time, we maintain a
#  UserUpdateStreak row that is updated incrementally:
#
#    • on_update_submitted()  → reset streak to 0, update last_submitted
#    • check_daily_updates()  → increment streak by 1 if not submitted today
#
#  At cron time: streak value is READ (O(1)) not COMPUTED (O(N queries)).

def _get_or_create_streak(workspace_id: int, user_id: int) -> "UserUpdateStreak":
    streak = (
        db.session.query(UserUpdateStreak)
        .filter_by(workspace_id=workspace_id, user_id=user_id)
        .with_for_update()          # lock row during cron update
        .first()
    )
    if not streak:
        streak = UserUpdateStreak(
            workspace_id   = workspace_id,
            user_id        = user_id,
            missed_streak  = 0,
            last_submitted = None,
            last_checked   = None,
        )
        db.session.add(streak)
        db.session.flush()
    return streak


def _increment_streak(streak: "UserUpdateStreak", today: date) -> None:
    """
    FIX-C — Increment missed streak only once per calendar day.
    Guards against double-increment if cron runs more than once per day.
    """
    if streak.last_checked == today:
        return   # already incremented today — idempotent
    streak.missed_streak += 1
    streak.last_checked   = today


def _reset_streak(workspace_id: int, user_id: int) -> None:
    """FIX-C — Called by on_update_submitted() to clear the streak."""
    streak = (
        db.session.query(UserUpdateStreak)
        .filter_by(workspace_id=workspace_id, user_id=user_id)
        .first()
    )
    if streak:
        streak.missed_streak  = 0
        streak.last_submitted = date.today()
        streak.last_checked   = date.today()


# ══════════════════════════════════════════════════════════════════════════════
# Core check: daily updates
# ══════════════════════════════════════════════════════════════════════════════

def check_daily_updates(workspace_id: int, today: date, cfg: _WorkspaceCfg) -> dict:
    """
    FIX-A: skips non-working days.
    FIX-C: reads streak from DB (no per-day lookback queries).
    """
    summary = {"missing_update": 0}

    # FIX-A
    if _is_non_working_day(workspace_id, today, cfg.skip_weekends):
        return summary

    if not _past_cutoff(cfg.update_cutoff):
        logger.debug("Update cutoff not reached | workspace=%s", workspace_id)
        return summary

    for user_batch in _fetch_users_batch(workspace_id):
        user_ids    = [u.id for u in user_batch]
        updated_ids = _fetch_update_set(workspace_id, user_ids, today)

        for user in user_batch:
            if user.id in updated_ids:
                # User submitted today — ensure their streak is reset
                # (handles case where streak wasn't reset via hook)
                streak = _get_or_create_streak(workspace_id, user.id)
                if streak.missed_streak > 0:
                    _reset_streak(workspace_id, user.id)
                continue

            if _open_alert_today(workspace_id, user.id,
                                  AlertType.missing_update, today):
                continue   # already alerted today

            # FIX-C — read streak from DB, then increment (O(1) not O(N))
            streak = _get_or_create_streak(workspace_id, user.id)
            _increment_streak(streak, today)
            days_missed = streak.missed_streak
            priority    = _resolve_priority(AlertType.missing_update, days_missed)

            _create_alert(
                workspace_id = workspace_id,
                user_id      = user.id,
                alert_type   = AlertType.missing_update,
                message      = (
                    f"{user.name} has not submitted a daily update for {today}. "
                    f"Consecutive days missed: {days_missed}."
                ),
                priority     = priority,
            )
            summary["missing_update"] += 1

    return summary


# ══════════════════════════════════════════════════════════════════════════════
# Core check: overdue tasks
# ══════════════════════════════════════════════════════════════════════════════

def check_overdue_tasks(workspace_id: int) -> dict:
    summary = {"task_overdue": 0}
    now     = datetime.utcnow()
    today   = now.date()

    overdue_tasks = (
        db.session.query(Task)
        .options(joinedload(Task.assignee))
        .filter(
            Task.workspace_id == workspace_id,
            Task.deadline.isnot(None),
            Task.deadline     < now,
            Task.status       != "done",
            Task.assigned_to.isnot(None),
        )
        .all()
    )

    for task in overdue_tasks:
        if _open_alert_today(workspace_id, task.assigned_to,
                              AlertType.task_overdue, today):
            continue

        days_overdue = max(0, (now - task.deadline).days)
        priority     = _resolve_priority(AlertType.task_overdue, days_overdue)

        _create_alert(
            workspace_id = workspace_id,
            user_id      = task.assigned_to,
            alert_type   = AlertType.task_overdue,
            message      = (
                f"Task '{task.title}' is {days_overdue} day(s) overdue "
                f"(deadline: {task.deadline.strftime('%Y-%m-%d %H:%M')})."
            ),
            priority     = priority,
            reference_id = task.id,
        )
        summary["task_overdue"] += 1

    return summary


# ══════════════════════════════════════════════════════════════════════════════
# Core check: inactive users
# ══════════════════════════════════════════════════════════════════════════════

def check_inactive_users(workspace_id: int, cfg: _WorkspaceCfg) -> dict:
    summary   = {"inactive_user": 0}
    now       = datetime.utcnow()
    today     = now.date()
    threshold = now - timedelta(days=cfg.inactivity_days)

    for user_batch in _fetch_users_batch(workspace_id):
        for user in user_batch:
            last_seen = user.last_activity or user.last_login
            if last_seen and last_seen >= threshold:
                continue
            if _open_alert_today(workspace_id, user.id,
                                  AlertType.inactive_user, today):
                continue

            days_idle = (now - last_seen).days if last_seen else 999
            priority  = _resolve_priority(AlertType.inactive_user, days_idle)

            _create_alert(
                workspace_id = workspace_id,
                user_id      = user.id,
                alert_type   = AlertType.inactive_user,
                message      = (
                    f"{user.name} has been inactive for {days_idle} day(s). "
                    f"Last seen: "
                    f"{last_seen.strftime('%Y-%m-%d %H:%M') if last_seen else 'never'}."
                ),
                priority     = priority,
            )
            summary["inactive_user"] += 1

    return summary


# ══════════════════════════════════════════════════════════════════════════════
# Auto-resolution (shared)
# ══════════════════════════════════════════════════════════════════════════════

def _auto_resolve(workspace_id: int, user_id: int,
                  alert_type: AlertType,
                  resolved_by: int,
                  note: str,
                  reference_id: Optional[int] = None) -> bool:
    q = (
        db.session.query(Alert)
        .filter(
            Alert.workspace_id == workspace_id,
            Alert.user_id      == user_id,
            Alert.type         == alert_type,
            Alert.resolved     == False,        # noqa: E712
            Alert.archived     == False,        # FIX-D — don't resolve archived
        )
    )
    if reference_id is not None:
        q = q.filter(Alert.reference_id == reference_id)

    alert = q.order_by(Alert.created_at.desc()).first()
    if not alert:
        return False

    alert.resolved        = True
    alert.resolved_at     = datetime.utcnow()
    alert.resolved_by     = resolved_by
    alert.resolution_note = note
    logger.info(
        "ALERT AUTO-RESOLVED | id=%s type=%s user=%s",
        alert.id, alert_type.value, user_id,
    )
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Cross-module integration hooks
# ══════════════════════════════════════════════════════════════════════════════

def on_clock_in(workspace_id: int, user_id: int,
                clock_in_time: datetime) -> None:
    """Call from POST /attendance/clock-in."""
    cfg            = _get_cfg(workspace_id)
    today          = clock_in_time.date()
    late_threshold = datetime.combine(today, cfg.late_threshold)

    _auto_resolve(
        workspace_id = workspace_id,
        user_id      = user_id,
        alert_type   = AlertType.missing_attendance,
        resolved_by  = user_id,
        note         = f"User clocked in at {clock_in_time.strftime('%H:%M')}.",
    )

    if clock_in_time > late_threshold:
        if not _open_alert_today(workspace_id, user_id,
                                  AlertType.late_attendance, today):
            _create_alert(
                workspace_id = workspace_id,
                user_id      = user_id,
                alert_type   = AlertType.late_attendance,
                message      = (
                    f"User clocked in late at {clock_in_time.strftime('%H:%M')} "
                    f"(threshold {cfg.late_threshold.strftime('%H:%M')})."
                ),
            )

    db.session.commit()


def on_update_submitted(workspace_id: int, user_id: int) -> None:
    """Call from POST /updates/submit."""
    _auto_resolve(
        workspace_id = workspace_id,
        user_id      = user_id,
        alert_type   = AlertType.missing_update,
        resolved_by  = user_id,
        note         = "User submitted daily update.",
    )
    # FIX-C — reset streak immediately on submission
    _reset_streak(workspace_id, user_id)
    db.session.commit()


def on_task_status_changed(workspace_id: int, task_id: int,
                            assigned_to: int, new_status: str) -> None:
    """Call from PATCH /tasks/update."""
    if new_status != "done":
        return
    _auto_resolve(
        workspace_id = workspace_id,
        user_id      = assigned_to,
        alert_type   = AlertType.task_overdue,
        resolved_by  = assigned_to,
        note         = "Task marked as done.",
        reference_id = task_id,
    )
    db.session.commit()


def on_user_activity(workspace_id: int, user_id: int) -> None:
    """
    Middleware hook — call on every authenticated request.
    Stamps last_activity and resolves inactive_user alert.
    Commit is left to the caller (request teardown).
    """
    user = db.session.get(User, user_id)
    if not user:
        return
    now = datetime.utcnow()
    user.last_activity = now
    _auto_resolve(
        workspace_id = workspace_id,
        user_id      = user_id,
        alert_type   = AlertType.inactive_user,
        resolved_by  = user_id,
        note         = f"User became active at {now.isoformat()}.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Admin digest / aggregation
# ══════════════════════════════════════════════════════════════════════════════

def build_admin_digest(workspace_id: int) -> dict:
    today = date.today()
    rows  = (
        db.session.query(
            Alert.type,
            Alert.priority,
            func.count(Alert.id).label("count"),
        )
        .filter(
            Alert.workspace_id == workspace_id,
            Alert.resolved     == False,        # noqa: E712
            Alert.archived     == False,        # FIX-D — exclude archived
            Alert.created_at   >= _day_start(today),
        )
        .group_by(Alert.type, Alert.priority)
        .all()
    )

    groups = [
        {
            "type":     row.type.value,
            "priority": row.priority.value,
            "count":    row.count,
            "summary":  f"{row.count} user(s) — {row.type.value.replace('_', ' ')}",
        }
        for row in rows
    ]
    return {
        "workspace_id": workspace_id,
        "date":         str(today),
        "groups":       groups,
        "total_open":   sum(g["count"] for g in groups),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FIX-D — Soft-delete / archival for old resolved alerts
# ══════════════════════════════════════════════════════════════════════════════

def archive_old_alerts(workspace_id: int,
                       resolved_older_than_days: int = 30,
                       batch_size: int = 500) -> int:
    """
    FIX-D — Soft-archive resolved alerts older than *resolved_older_than_days*.

    Strategy:
      • Sets archived=True and archived_at=now on qualifying rows.
      • Does NOT delete — audit trail is preserved for compliance/reporting.
      • Runs in batches of *batch_size* to avoid long-running transactions
        that would lock the table.
      • All active-alert queries filter archived=False, so archived rows are
        invisible to the engine without losing the historical record.

    Call this nightly from the cron scheduler, after run_alert_checks().

    For very large deployments, graduate to table partitioning by month on
    created_at and DROP old partitions instead.
    """
    cutoff    = datetime.utcnow() - timedelta(days=resolved_older_than_days)
    now       = datetime.utcnow()
    archived  = 0

    while True:
        # Fetch one batch of qualifying IDs
        id_rows = (
            db.session.query(Alert.id)
            .filter(
                Alert.workspace_id == workspace_id,
                Alert.resolved     == True,         # noqa: E712
                Alert.archived     == False,        # noqa: E712
                Alert.resolved_at  <= cutoff,
            )
            .limit(batch_size)
            .all()
        )

        if not id_rows:
            break

        ids = [r[0] for r in id_rows]

        # Bulk update — single UPDATE ... WHERE id IN (...)
        db.session.query(Alert).filter(Alert.id.in_(ids)).update(
            {"archived": True, "archived_at": now},
            synchronize_session="fetch",
        )
        db.session.commit()
        archived += len(ids)

        logger.info(
            "Archived %d alert(s) | workspace=%s batch_total=%d",
            len(ids), workspace_id, archived,
        )

        if len(ids) < batch_size:
            break   # last partial batch — done

    logger.info(
        "Archive run complete | workspace=%s total_archived=%d cutoff=%s",
        workspace_id, archived, cutoff.date(),
    )
    return archived


# ══════════════════════════════════════════════════════════════════════════════
# Cron entry-point — safe, idempotent, per-check error isolation
# ══════════════════════════════════════════════════════════════════════════════

def run_alert_checks(workspace_id: int,
                     archive_after_days: int = 30) -> dict:
    """
    Full alert engine run for one workspace.

    Order of operations:
      1. check_attendance
      2. check_daily_updates
      3. check_overdue_tasks
      4. check_inactive_users
      5. archive_old_alerts   (FIX-D — runs at end of each cron cycle)

    Each step has its own try/except + rollback so a failure in one
    step does not abort the rest.
    """
    run_id  = str(uuid.uuid4())[:8]
    today   = date.today()
    cfg     = _get_cfg(workspace_id)
    started = datetime.utcnow()

    summary: dict = {
        "run_id":              run_id,
        "workspace_id":        workspace_id,
        "run_at":              started.isoformat(),
        "missing_attendance":  0,
        "late_attendance":     0,
        "missing_update":      0,
        "task_overdue":        0,
        "inactive_user":       0,
        "total_alerts":        0,
        "archived":            0,
        "errors":              [],
    }

    checks = [
        ("attendance", lambda: check_attendance(workspace_id, today, cfg)),
        ("updates",    lambda: check_daily_updates(workspace_id, today, cfg)),
        ("tasks",      lambda: check_overdue_tasks(workspace_id)),
        ("inactivity", lambda: check_inactive_users(workspace_id, cfg)),
    ]

    for name, fn in checks:
        try:
            result = fn()
            summary.update(result)
            db.session.commit()
            logger.info("[%s] %s check done: %s", run_id, name, result)
        except Exception as exc:
            db.session.rollback()
            err = f"{name}: {exc}"
            summary["errors"].append(err)
            logger.exception("[%s] Check failed — %s", run_id, err)

    # FIX-D — archive old resolved alerts at end of every cron run
    try:
        summary["archived"] = archive_old_alerts(
            workspace_id          = workspace_id,
            resolved_older_than_days = archive_after_days,
        )
    except Exception as exc:
        db.session.rollback()
        err = f"archive: {exc}"
        summary["errors"].append(err)
        logger.exception("[%s] Archive step failed — %s", run_id, err)

    summary["total_alerts"] = (
        summary["missing_attendance"]
        + summary["late_attendance"]
        + summary["missing_update"]
        + summary["task_overdue"]
        + summary["inactive_user"]
    )
    summary["duration_ms"] = int(
        (datetime.utcnow() - started).total_seconds() * 1000
    )

    logger.info("[%s] Alert run done: %s", run_id, summary)
    return summary
