"""
app/routes/meet_routes.py

Blueprint for SF Meet scheduling API endpoints.

Register in blueprints.py:
    from app.routes.meet_routes import meet_bp
    app.register_blueprint(meet_bp)
"""

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models.meet_meeting import MeetingStatus
from app.services.meet_service import (
    MeetConflictError,
    MeetNotFoundError,
    MeetServiceError,
    MeetStateError,
    MeetService,
)
from app.utils.meet_validators import (
    validate_create_meeting_request,
    validate_update_meeting_request,
)

logger = logging.getLogger(__name__)

meet_bp = Blueprint("meet", __name__, url_prefix="/meetings")


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def success_response(data=None, status=200):
    """Wrap data with a 'success' flag."""
    if data is None:
        data = {}
    return jsonify({"success": True, **data}), status


def _err(message: str, status: int, **extra):
    body = {"success": False, "error": message, **extra}
    return jsonify(body), status


def _handle_service_error(exc: Exception):
    if isinstance(exc, MeetNotFoundError):
        return _err(str(exc), 404)
    if isinstance(exc, MeetConflictError):
        return _err(str(exc), 409)
    if isinstance(exc, MeetStateError):
        return _err(str(exc), 422)
    if isinstance(exc, MeetServiceError):
        return _err(str(exc), 400)
    raise exc  # unexpected — let Flask's error handler catch it


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@meet_bp.route("/create", methods=["POST"])
@jwt_required()
def create_meeting():
    """
    POST /meetings/create
    Body: JSON matching validate_create_meeting_request schema.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return _err("Request body must be valid JSON.", 400)

    try:
        clean = validate_create_meeting_request(payload)
        meeting = MeetService.create_meeting(
            actor_user_id=get_jwt_identity(),
            data=clean,
        )
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _handle_service_error(exc)

    return success_response({"meeting": meeting.to_dict()}, 201)


@meet_bp.route("/update/<int:meeting_id>", methods=["PATCH"])
@jwt_required()
def update_meeting(meeting_id: int):
    """
    PATCH /meetings/update/<meeting_id>
    Body: partial JSON — only fields you want to update.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return _err("Request body must be valid JSON.", 400)

    try:
        clean = validate_update_meeting_request(payload)
        meeting = MeetService.update_meeting(
            actor_user_id=get_jwt_identity(),
            meeting_id=meeting_id,
            data=clean,
        )
    except ValueError as exc:
        return _err(str(exc), 400)
    except Exception as exc:
        return _handle_service_error(exc)

    return success_response({"meeting": meeting.to_dict()})


@meet_bp.route("/cancel/<int:meeting_id>", methods=["POST"])
@jwt_required()
def cancel_meeting(meeting_id: int):
    """
    POST /meetings/cancel/<meeting_id>
    Optional body: { "reason": "..." }
    """
    payload = request.get_json(silent=True) or {}
    reason  = payload.get("reason")

    try:
        meeting = MeetService.cancel_meeting(
            actor_user_id=get_jwt_identity(),
            meeting_id=meeting_id,
            reason=reason,
        )
    except Exception as exc:
        return _handle_service_error(exc)

    return success_response({"meeting": meeting.to_dict()})


@meet_bp.route("/<int:meeting_id>", methods=["GET"])
@jwt_required()
def get_meeting(meeting_id: int):
    """GET /meetings/<meeting_id>"""
    try:
        meeting = MeetService.get_meeting(meeting_id)
    except Exception as exc:
        return _handle_service_error(exc)

    return success_response({"meeting": meeting.to_dict()})


@meet_bp.route("/", methods=["GET"])
@jwt_required()
def list_meetings():
    """
    GET /meetings/
    Query params: startup_id, organization_id, owner_user_id, status, limit, offset
    """
    try:
        limit  = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _err("limit and offset must be integers.", 400)

    try:
        meetings = MeetService.list_meetings(
            startup_id=      request.args.get("startup_id"),
            organization_id= request.args.get("organization_id"),
            owner_user_id=   request.args.get("owner_user_id"),
            status=          request.args.get("status"),
            limit=           min(limit, 200),
            offset=          offset,
        )
    except Exception as exc:
        return _handle_service_error(exc)

    return success_response({"meetings": [m.to_dict() for m in meetings]})


@meet_bp.route("/<int:meeting_id>/status", methods=["POST"])
@jwt_required()
def transition_status(meeting_id: int):
    """
    POST /meetings/<meeting_id>/status
    Body: { "status": "<target_status>" }
    Drives the meeting through its lifecycle states.
    """
    payload = request.get_json(silent=True) or {}
    raw_status = payload.get("status")
    if not raw_status:
        return _err("'status' field is required.", 400)

    try:
        target = MeetingStatus(raw_status)
    except ValueError:
        valid = [s.value for s in MeetingStatus]
        return _err(f"Invalid status '{raw_status}'. Must be one of: {valid}.", 400)

    try:
        meeting = MeetService.transition_status(
            actor_user_id=get_jwt_identity(),
            meeting_id=meeting_id,
            target_status=target,
        )
    except Exception as exc:
        return _handle_service_error(exc)

    return success_response({"meeting": meeting.to_dict()})