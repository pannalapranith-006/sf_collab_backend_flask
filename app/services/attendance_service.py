from datetime import datetime, time, date
from enum import Enum
from app.models.attendance import AttendanceLog
from app.services.warning_service import create_warning, resolve_warning
import logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Thresholds (override via app config if needed)
# ──────────────────────────────────────────────
LATE_CLOCK_IN_THRESHOLD   = time(9, 30)   # Clock-in after this → Late
EARLY_CLOCK_OUT_THRESHOLD = time(17, 0)   # Clock-out before this → Early
MIN_WORK_HOURS            = 6.0           # Fewer hours → Insufficient Hours warning


# ──────────────────────────────────────────────
# Warning type constants
# FIX: str Enum instead of a plain class — values are now immutable and
#      cannot be accidentally overwritten at runtime. Also works anywhere
#      a plain str is expected (e.g. ORM filters, JSON serialisation).
# ──────────────────────────────────────────────
class AttendanceWarningType(str, Enum):
    MISSING_CLOCK_IN   = "Missing Clock-In"
    LATE_CLOCK_IN      = "Late Clock-In"
    NO_ACTIVITY        = "No Activity Today"
    EARLY_CLOCK_OUT    = "Early Clock-Out"
    INSUFFICIENT_HOURS = "Insufficient Work Hours"


def validate_daily_attendance(
    workspace_id: int,
    user_id: int,
    check_date: date,          # FIX: added `date` type annotation (was untyped)
) -> list[str]:
    """
    Validates attendance for a given user on a given date.

    Detects:
      • Missing clock-in        – no record or clock_in_at is NULL
      • Late clock-in           – clocked in after LATE_CLOCK_IN_THRESHOLD
      • No activity day         – clocked in but never clocked out by end of day
      • Early clock-out         – clocked out before EARLY_CLOCK_OUT_THRESHOLD
      • Insufficient work hours – total logged time < MIN_WORK_HOURS

    Auto-triggers warning_service for each detected issue.
    Returns a list of warning types that were raised, for audit / testing.
    """
    issues: list[str] = []

    log: AttendanceLog | None = AttendanceLog.query.filter_by(
        workspace_id=workspace_id,
        user_id=user_id,
        date=check_date,
    ).first()

    # ── 1. Missing clock-in ───────────────────────────────────────────────
    if not log or not log.clock_in_at:
        create_warning(
            workspace_id=workspace_id,
            user_id=user_id,
            warning_type=AttendanceWarningType.MISSING_CLOCK_IN,
            severity="Warning",
            title="Missing Clock-In",
            description=f"No clock-in was recorded for {check_date}.",
            source_type="attendance",
            source_id=log.id if log else None,
        )
        issues.append(AttendanceWarningType.MISSING_CLOCK_IN)
        return issues  # Cannot run further checks without a clock-in

    clock_in_time = log.clock_in_at.time()

    # ── 2. Late clock-in ──────────────────────────────────────────────────
    if clock_in_time > LATE_CLOCK_IN_THRESHOLD:
        minutes_late = _minutes_between(LATE_CLOCK_IN_THRESHOLD, clock_in_time)
        create_warning(
            workspace_id=workspace_id,
            user_id=user_id,
            warning_type=AttendanceWarningType.LATE_CLOCK_IN,
            severity="Notice",
            title="Late Clock-In",
            description=(
                f"Clocked in at {_fmt(clock_in_time)} on {check_date} — "
                f"{minutes_late} min after the {_fmt(LATE_CLOCK_IN_THRESHOLD)} threshold."
            ),
            source_type="attendance",
            source_id=log.id,
        )
        issues.append(AttendanceWarningType.LATE_CLOCK_IN)
    else:
        resolve_warning(
            workspace_id=workspace_id,
            user_id=user_id,
            warning_type=AttendanceWarningType.LATE_CLOCK_IN,
            check_date=check_date,
        )

    # ── 3. No clock-out (end-of-day check only) ───────────────────────────
    if not log.clock_out_at:
        create_warning(
            workspace_id=workspace_id,
            user_id=user_id,
            warning_type=AttendanceWarningType.NO_ACTIVITY,
            severity="Warning",
            title="No Activity Recorded",
            description=(
                f"User clocked in at {_fmt(clock_in_time)} on {check_date} "
                f"but no clock-out or activity was recorded by end of day."
            ),
            source_type="attendance",
            source_id=log.id,
        )
        issues.append(AttendanceWarningType.NO_ACTIVITY)
        return issues  # Can't compute hours without clock-out

    # Clock-out confirmed — safe to read it now
    clock_out_time = log.clock_out_at.time()

    resolve_warning(
        workspace_id=workspace_id,
        user_id=user_id,
        warning_type=AttendanceWarningType.NO_ACTIVITY,
        check_date=check_date,
    )

    # ── 4. Early clock-out ────────────────────────────────────────────────
    if clock_out_time < EARLY_CLOCK_OUT_THRESHOLD:
        minutes_early = _minutes_between(clock_out_time, EARLY_CLOCK_OUT_THRESHOLD)
        create_warning(
            workspace_id=workspace_id,
            user_id=user_id,
            warning_type=AttendanceWarningType.EARLY_CLOCK_OUT,
            severity="Notice",
            title="Early Clock-Out",
            description=(
                f"Clocked out at {_fmt(clock_out_time)} on {check_date} — "
                f"{minutes_early} min before the {_fmt(EARLY_CLOCK_OUT_THRESHOLD)} threshold."
            ),
            source_type="attendance",
            source_id=log.id,
        )
        issues.append(AttendanceWarningType.EARLY_CLOCK_OUT)
    else:
        resolve_warning(
            workspace_id=workspace_id,
            user_id=user_id,
            warning_type=AttendanceWarningType.EARLY_CLOCK_OUT,
            check_date=check_date,
        )

    # ── 5. Insufficient work hours ────────────────────────────────────────
    worked_hours = _calc_hours(log.clock_in_at, log.clock_out_at)
    if worked_hours < MIN_WORK_HOURS:
        create_warning(
            workspace_id=workspace_id,
            user_id=user_id,
            warning_type=AttendanceWarningType.INSUFFICIENT_HOURS,
            severity="Notice",
            title="Insufficient Work Hours",
            description=(
                f"Only {worked_hours:.1f}h logged on {check_date} "
                f"(minimum required: {MIN_WORK_HOURS:.1f}h)."
            ),
            source_type="attendance",
            source_id=log.id,
        )
        issues.append(AttendanceWarningType.INSUFFICIENT_HOURS)
    else:
        resolve_warning(
            workspace_id=workspace_id,
            user_id=user_id,
            warning_type=AttendanceWarningType.INSUFFICIENT_HOURS,
            check_date=check_date,
        )

    logger.info(
        "validate_daily_attendance | workspace=%s user=%s date=%s issues=%s",
        workspace_id, user_id, check_date, issues or "none",
    )
    return issues


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _minutes_between(t_start: time, t_end: time) -> int:
    """Return absolute minute difference between two time objects."""
    base = datetime(2000, 1, 1)
    delta = datetime.combine(base, t_end) - datetime.combine(base, t_start)
    return int(abs(delta.total_seconds()) // 60)


def _calc_hours(clock_in: datetime, clock_out: datetime) -> float:
    """
    Return work duration in hours.
    Clamped to [0, 24] — guards against bad data where clock_out < clock_in.
    """
    if not clock_in or not clock_out:
        return 0.0
    hours = (clock_out - clock_in).total_seconds() / 3600
    return max(0.0, min(hours, 24.0))


def _fmt(t: time) -> str:
    return t.strftime("%H:%M")
