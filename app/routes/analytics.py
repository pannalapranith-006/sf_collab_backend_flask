# routes/analytics.py
# SFCollab ERP — Analytics API routes
# HTTP layer only: Blueprint, JWT, request parsing, response formatting

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from models.analytics import AnalyticsSnapshot
from services.analytics_service import AnalyticsService
from utils.auth import admin_required, get_jwt_claims
from utils.csv_utils import to_csv_response
from utils.date_utils import period_to_dates, resolve_dates

from extensions import db
from models.user import User

logger = logging.getLogger(__name__)

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers (request-scoped — live here, not in services)
# ─────────────────────────────────────────────────────────────────────────────

def _scoped_user_ids(workspace_id: int) -> list[int]:
    """
    Returns active user IDs for the workspace, filtered by optional params:
        ?department=Engineering&role=member&team_id=5
    Returns empty list if no filter params (caller treats as "all users").
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
# Endpoints
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
        workspace_id, _, _ = get_jwt_claims()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    start, end   = resolve_dates()
    user_ids     = _scoped_user_ids(workspace_id)
    inc_trends   = request.args.get("trends", "1") != "0"

    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end,
        user_ids=user_ids or None,
        include_trends=inc_trends,
    )

    if request.args.get("export") == "csv":
        return to_csv_response(data, f"workspace_{workspace_id}_analytics.csv")

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
        workspace_id, role, caller_id = get_jwt_claims()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if role != "admin" and caller_id != user_id:
        return jsonify({"error": "Access denied"}), 403

    start, end = resolve_dates()
    data = AnalyticsService.user_analytics(user_id, workspace_id, start, end)

    if "error" in data:
        return jsonify(data), data.pop("_code", 400)

    if request.args.get("export") == "csv":
        return to_csv_response(data, f"user_{user_id}_analytics.csv")

    return jsonify(data), 200


@analytics_bp.get("/trends")
@jwt_required()
@admin_required
def trends_endpoint():
    """
    GET /analytics/trends

    Period-over-period comparison + sparkline. Admin only.
    """
    try:
        workspace_id, _, _ = get_jwt_claims()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    start, end = resolve_dates()
    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end, include_trends=True,
    )
    return jsonify({
        "workspace_id": workspace_id,
        "trends":       data.get("trends", {}),
    }), 200


@analytics_bp.get("/anomalies")
@jwt_required()
@admin_required
def anomalies_endpoint():
    """
    GET /analytics/anomalies

    Detect anomalies and write them to the alerts table. Admin only.
    """
    try:
        workspace_id, _, _ = get_jwt_claims()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    start, end = resolve_dates()
    user_ids   = _scoped_user_ids(workspace_id)
    data = AnalyticsService.workspace_analytics(
        workspace_id, start, end,
        user_ids=user_ids or None,
        include_trends=True,
    )
    return jsonify({
        "workspace_id": workspace_id,
        "anomalies":    data.get("anomalies", []),
        "trends":       data.get("trends",    {}),
    }), 200


@analytics_bp.get("/snapshot/<int:workspace_id>")
@jwt_required()
@admin_required
def snapshot_endpoint(workspace_id: int):
    """
    GET /analytics/snapshot/<workspace_id>?period=daily

    Latest cached snapshot. Falls back to live computation if none exists.
    """
    period     = request.args.get("period", "daily")
    start, end = period_to_dates(period)

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
                    logger.info(
                        "Analytics snapshot saved",
                        extra={
                            "workspace_id":        wid,
                            "period":              period,
                            "attendance_rate":     snap.attendance_rate,
                            "task_completion_rate": snap.task_completion_rate,
                            "update_consistency":  snap.update_consistency,
                        },
                    )
                except Exception as exc:
                    logger.exception(
                        "Analytics snapshot failed",
                        extra={"workspace_id": wid, "period": period, "error": str(exc)},
                    )