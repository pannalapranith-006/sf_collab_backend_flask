from app import db
from app.models.warning import Warning
from app.services.membership_audit_service import log_membership_action
from app.services.severity_service import determine_severity

def create_warning(user_id, workspace_id, type, message,
                   reference_date=None, reference_id=None, severity=None):
    if severity is None:
        severity = determine_severity(user_id, workspace_id, type)

    warning = Warning(
        user_id=user_id,
        workspace_id=workspace_id,
        type=type,
        severity=severity,
        message=message,
        reference_date=reference_date,
        reference_id=reference_id
    )
    db.session.add(warning)
    db.session.commit()

    log_membership_action(
        'warning_created',
        workspace_id=workspace_id,
        details={
            'warning_id': warning.id,
            'user_id': user_id,
            'type': type,
            'severity': severity,
            'message': message,
            'reference_date': reference_date.isoformat() if reference_date else None,
            'reference_id': reference_id
        }
    )
    return warning
from datetime import datetime, timedelta, date, time
from app.models.warning import Warning
from app import db
import logging

logger = logging.getLogger(__name__)


def create_warning(
    workspace_id: int,
    user_id: int,
    warning_type: str,
    severity: str,
    title: str,
    description: str,
    source_type: str | None = None,
    source_id: int | None = None,
) -> Warning:
    """
    Persists a warning record.

    • Idempotent: returns the existing open warning if one already exists
      for (workspace, user, type) on today's date, without creating a duplicate.
    • If a *resolved* warning exists from today it creates a fresh one,
      so re-opened issues are traceable.
    """
    # FIX: capture utcnow() once — used for both the duplicate window check
    #      and the created_at stamp so they are guaranteed the same instant.
    now         = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = today_start + timedelta(days=1)

    existing: Warning | None = Warning.query.filter_by(
        workspace_id=workspace_id,
        user_id=user_id,
        warning_type=warning_type,
        status="Open",
    ).filter(
        Warning.created_at >= today_start,
        Warning.created_at <  today_end,
    ).first()

    if existing:
        logger.debug(
            "create_warning | duplicate suppressed type=%s user=%s",
            warning_type, user_id,
        )
        return existing

    warning = Warning(
        workspace_id=workspace_id,
        user_id=user_id,
        warning_type=warning_type,
        severity=severity,
        status="Open",
        title=title,
        description=description,
        source_type=source_type,
        source_id=source_id,
        created_at=now,          # FIX: reuse the same `now` — no second utcnow() call
    )

    try:
        db.session.add(warning)
        db.session.commit()
        logger.info(
            "create_warning | created type=%s severity=%s user=%s workspace=%s",
            warning_type, severity, user_id, workspace_id,
        )
    except Exception:
        db.session.rollback()
        logger.exception(
            "create_warning | DB error type=%s user=%s", warning_type, user_id
        )
        raise

    return warning


def resolve_warning(
    workspace_id: int,
    user_id: int,
    warning_type: str,
    check_date: date | None = None,   # FIX: added `date | None` type annotation
    resolved_by: int | None = None,
    note: str | None = None,
) -> int:
    """
    Marks all open warnings of the given type for (workspace, user) on
    *check_date* (defaults to today UTC) as Resolved.

    Returns the number of rows updated.
    """
    # FIX: consistent target_start construction via datetime.combine — works
    #      the same way whether check_date is provided or defaults to today,
    #      and is explicit about what "midnight" means (UTC throughout).
    resolved_at  = datetime.utcnow()
    target_day   = check_date or resolved_at.date()
    target_start = datetime.combine(target_day, time.min)   # midnight UTC
    target_end   = target_start + timedelta(days=1)

    update_values: dict = {"status": "Resolved", "resolved_at": resolved_at}
    if resolved_by:
        update_values["resolved_by"] = resolved_by
    if note:
        update_values["resolution_note"] = note

    try:
        updated = (
            Warning.query
            .filter_by(
                workspace_id=workspace_id,
                user_id=user_id,
                warning_type=warning_type,
                status="Open",
            )
            .filter(
                Warning.created_at >= target_start,
                Warning.created_at <  target_end,
            )
            .update(update_values, synchronize_session=False)
        )
        db.session.commit()

        if updated:
            logger.info(
                "resolve_warning | resolved %d warning(s) type=%s user=%s date=%s",
                updated, warning_type, user_id, target_day,
            )
        return updated

    except Exception:
        db.session.rollback()
        logger.exception(
            "resolve_warning | DB error type=%s user=%s", warning_type, user_id
        )
        raise


def get_open_warnings(
    workspace_id: int,
    user_id: int | None = None,
    warning_type: str | None = None,
    check_date: date | None = None,   # FIX: added `date | None` type annotation
) -> list[Warning]:
    """
    Returns all open warnings for a workspace, optionally filtered by
    user, type, and/or date.
    """
    query = Warning.query.filter_by(workspace_id=workspace_id, status="Open")

    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    if warning_type is not None:
        query = query.filter_by(warning_type=warning_type)

    if check_date is not None:
        day_start = datetime.combine(check_date, time.min)  # FIX: consistent with resolve_warning
        day_end   = day_start + timedelta(days=1)
        query = query.filter(
            Warning.created_at >= day_start,
            Warning.created_at <  day_end,
        )

    return query.order_by(Warning.created_at.desc()).all()
