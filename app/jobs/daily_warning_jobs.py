from datetime import date, timedelta
from time import perf_counter
from app.models.membership import UserWorkspaceMembership
from app.services.attendance_service import validate_daily_attendance
import logging

logger = logging.getLogger(__name__)

# Days to skip (0 = Monday … 6 = Sunday)
SKIP_WEEKDAYS: set[int] = {5, 6}  # Saturday, Sunday


def run_daily_attendance_warnings(target_date: date | None = None) -> dict:
    """
    Scheduled job — run every day after the workday ends (e.g. 11 PM).

    For each active workspace member it calls validate_daily_attendance()
    for *target_date* (defaults to yesterday) and auto-raises warnings
    for any attendance issues found.

    Skips weekends by default (configure SKIP_WEEKDAYS to change).

    Returns a consistent summary dict for monitoring / alerting:
        {
            "date":            "2025-05-02",
            "skipped":         False,
            "elapsed_seconds": 3.21,
            "members_total":   120,
            "members_ok":      108,
            "members_issues":  12,
            "members_error":   0,
            "issues_by_type":  {"Late Clock-In": 7, "Missing Clock-In": 5},
        }

    NOTE: Must be called within a Flask app context. When using Celery or
    APScheduler, push one before calling this function:

        with app.app_context():
            run_daily_attendance_warnings()
    """
    run_date: date = target_date or (date.today() - timedelta(days=1))
    started = perf_counter()

    if run_date.weekday() in SKIP_WEEKDAYS:
        logger.info(
            "run_daily_attendance_warnings | skipping %s (weekend)", run_date
        )
        return {
            "date":            str(run_date),
            "skipped":         True,
            "reason":          "weekend",
            "elapsed_seconds": round(perf_counter() - started, 3),
            "members_total":   0,
            "members_ok":      0,
            "members_issues":  0,
            "members_error":   0,
            "issues_by_type":  {},
        }

    logger.info("run_daily_attendance_warnings | starting for date=%s", run_date)

    memberships: list[UserWorkspaceMembership] = (
        UserWorkspaceMembership.query
        .filter_by(status="active")
        .all()
    )

    summary = {
        "date":            str(run_date),
        "skipped":         False,
        "elapsed_seconds": 0.0,
        "members_total":   len(memberships),
        "members_ok":      0,
        "members_issues":  0,
        "members_error":   0,
        "issues_by_type":  {},
    }

    for membership in memberships:
        try:
            issues = validate_daily_attendance(
                workspace_id=membership.workspace_id,
                user_id=membership.user_id,
                check_date=run_date,        # FIX: was `date=run_date` — TypeError at runtime
            )

            if issues:
                summary["members_issues"] += 1
                for issue in issues:
                    summary["issues_by_type"][issue] = (
                        summary["issues_by_type"].get(issue, 0) + 1
                    )
            else:
                summary["members_ok"] += 1

        except Exception as exc:
            summary["members_error"] += 1
            logger.error(
                "run_daily_attendance_warnings | FAILED workspace=%s user=%s date=%s error=%s",
                membership.workspace_id,
                membership.user_id,
                run_date,
                exc,
                exc_info=True,
            )

    summary["elapsed_seconds"] = round(perf_counter() - started, 3)

    logger.info(
        "run_daily_attendance_warnings | done date=%s total=%d ok=%d "
        "issues=%d errors=%d elapsed=%.3fs breakdown=%s",
        run_date,
        summary["members_total"],
        summary["members_ok"],
        summary["members_issues"],
        summary["members_error"],
        summary["elapsed_seconds"],
        summary["issues_by_type"],
    )

    return summary
