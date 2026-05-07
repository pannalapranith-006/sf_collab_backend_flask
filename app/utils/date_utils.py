# utils/date_utils.py
# SFCollab ERP — Date / period helpers
# No Flask, no DB, no auth — pure date arithmetic

from __future__ import annotations

from datetime import date, timedelta

from flask import request


def period_to_dates(period: str) -> tuple[date, date]:
    """
    Translate a named period into (start, end) date pair.

    Supported values:
        "daily"   → today → today
        "weekly"  → this Monday → today
        "monthly" → 1st of month → today  (default)
    """
    today = date.today()
    if period == "daily":
        return today, today
    if period == "weekly":
        return today - timedelta(days=today.weekday()), today
    return today.replace(day=1), today


def resolve_dates() -> tuple[date, date]:
    """
    Resolve the request's date range from query params.

    Priority:
        1. Explicit start_date + end_date  → custom range
        2. ?period=daily|weekly|monthly    → named window
        3. Fallback                         → current month
    """
    raw_start = request.args.get("start_date")
    raw_end   = request.args.get("end_date")

    if raw_start and raw_end:
        try:
            return (
                date.fromisoformat(raw_start),
                date.fromisoformat(raw_end),
            )
        except ValueError:
            pass  # fall through to period-based resolution

    period = request.args.get("period", "monthly")
    return period_to_dates(period)


def previous_period(start: date, end: date) -> tuple[date, date]:
    """Mirror the current window backwards by the exact same number of days."""
    delta   = (end - start) + timedelta(days=1)
    p_end   = start - timedelta(days=1)
    p_start = p_end - delta + timedelta(days=1)
    return p_start, p_end