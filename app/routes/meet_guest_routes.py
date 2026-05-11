"""
meet_guest_routes.py — External Guest System
Spec reference: Section 17 — External Guest Support

Guest use cases:
    customer interview, investor call, mentor session,
    vendor discussion, candidate interview

Guest controls:
    - name and email capture
    - restricted join link (token-based, expires)
    - waiting room (host must admit)
    - no Drive browsing unless explicitly shared
    - file-specific share only
    - recording disclosure notice if enabled
    - transcript disclosure if enabled

After meeting:
    - guest-facing output separated from internal output
    - clean follow-up note for guest vs full internal summary

Register in blueprints.py:
    from .routes.meet_guest_routes import meet_guest_bp
    { "blueprint": meet_guest_bp, "url_prefix": "/api/meet" }
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.meet_meeting import MeetMeeting, MeetingStatus
from app.models.meet_participant import MeetParticipant, ParticipantRole, AttendanceStatus
from app.utils.helper import success_response, error_response
from datetime import datetime, timedelta
import secrets
import logging

meet_guest_bp = Blueprint("meet_guest", __name__)


# ── Guest token store (in-memory — swap for Redis in production) ───────────────
# { token: { meeting_id, guest_email, guest_name, expires_at, admitted, used } }
_guest_tokens = {}


def _generate_guest_token():
    return secrets.token_urlsafe(32)


def _get_valid_token(token):
    entry = _guest_tokens.get(token)
    if not entry:
        return None, "Invalid or expired guest link"
    if datetime.utcnow() > entry["expires_at"]:
        _guest_tokens.pop(token, None)
        return None, "Guest link has expired"
    return entry, None


# ══════════════════════════════════════════════════════════════════════════════
# GENERATE GUEST INVITE LINK
# POST /api/meet/<id>/guests/invite
# ══════════════════════════════════════════════════════════════════════════════

@meet_guest_bp.route("/<int:meeting_id>/guests/invite", methods=["POST"])
@jwt_required()
def invite_guest(meeting_id):
    """
    Generate a restricted guest join link for an external participant.
    Spec: "restricted join link", "name and email capture"

    Body:
        {
            "guest_email":  "investor@vc.com",   # required
            "guest_name":   "John Smith",         # optional
            "expires_hours": 48,                  # optional, default 48h
            "share_files":  ["drive_file_id_1"]  # optional — specific files guest can see
        }

    Returns: { guest_link, token, expires_at }
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can invite guests", 403)

    data        = request.get_json()
    guest_email = (data.get("guest_email") or "").strip().lower()
    guest_name  = (data.get("guest_name") or "").strip() or "Guest"
    expires_hrs = min(int(data.get("expires_hours", 48)), 168)  # cap at 7 days
    share_files = data.get("share_files", [])

    if not guest_email:
        return error_response("guest_email is required", 400)

    # Check if already a participant
    existing = MeetParticipant.query.filter_by(
        meeting_id=meeting_id, guest_email=guest_email
    ).first()
    if not existing:
        # Add as guest participant
        guest_participant = MeetParticipant(
            meeting_id         = meeting_id,
            user_id            = None,
            guest_email        = guest_email,
            role               = ParticipantRole.guest,
            attendance_status  = AttendanceStatus.invited,
            invited_by_user_id = int(uid),
        )
        db.session.add(guest_participant)
        db.session.commit()

    # Generate token
    token      = _generate_guest_token()
    expires_at = datetime.utcnow() + timedelta(hours=expires_hrs)

    _guest_tokens[token] = {
        "meeting_id":  meeting_id,
        "guest_email": guest_email,
        "guest_name":  guest_name,
        "expires_at":  expires_at,
        "admitted":    False,   # waiting room — not yet admitted
        "used":        False,
        "share_files": share_files,
        "recording_disclosure_shown":   meeting.recording_enabled,
        "transcript_disclosure_shown":  meeting.transcription_enabled,
    }

    # Build the join link (frontend will use this URL)
    from app.config import Config
    frontend_url = getattr(Config, "FRONTEND_URL", "https://sfcollab.com")
    guest_link = f"{frontend_url}/meet/join?token={token}"

    # Publish guest invited event
    try:
        from app.services.meet_events import guest_invited
        guest_invited(meeting, guest_email)
    except Exception as e:
        logging.warning(f"[GuestRoute] event publish failed: {e}")

    return success_response({
        "guest_link":  guest_link,
        "token":       token,
        "guest_email": guest_email,
        "guest_name":  guest_name,
        "expires_at":  expires_at.isoformat(),
        "waiting_room": True,
        "disclosures": {
            "recording":    meeting.recording_enabled,
            "transcription": meeting.transcription_enabled,
        },
        "message": f"Share guest_link with {guest_email}. They will wait in the waiting room until admitted.",
    }, status=201)


# ══════════════════════════════════════════════════════════════════════════════
# GUEST JOINS VIA TOKEN (no JWT needed)
# POST /api/meet/guests/join
# ══════════════════════════════════════════════════════════════════════════════

@meet_guest_bp.route("/guests/join", methods=["POST"])
def guest_join():
    """
    External guest uses their token to request to join.
    Spec: "waiting room" — guest is NOT admitted automatically.
    Host must call /guests/<token>/admit first.

    Body: { "token": str, "guest_name": str (optional override) }

    Returns meeting details visible to guest + waiting room status.
    """
    data  = request.get_json()
    token = (data.get("token") or "").strip()
    if not token:
        return error_response("token is required", 400)

    entry, err = _get_valid_token(token)
    if err:
        return error_response(err, 400)

    meeting = MeetMeeting.query.get(entry["meeting_id"])
    if not meeting:
        return error_response("Meeting not found", 404)

    # Override name if provided
    if data.get("guest_name"):
        entry["guest_name"] = data["guest_name"].strip()

    # Guest sees limited meeting info — spec: "no Drive browse unless explicitly shared"
    guest_view = {
        "meeting_id":    meeting.id,
        "title":         meeting.title,
        "meeting_type":  meeting.meeting_type.value,
        "status":        meeting.status.value,
        "host_name":     None,   # populated below
        "waiting_room":  not entry["admitted"],
        "admitted":      entry["admitted"],
        "disclosures": {
            "recording":     entry.get("recording_disclosure_shown", False),
            "transcription": entry.get("transcript_disclosure_shown", False),
            "notice": (
                "This meeting may be recorded and/or transcribed. "
                "By joining you consent to recording if enabled."
                if meeting.recording_enabled or meeting.transcription_enabled
                else None
            ),
        },
        "shared_files":  entry.get("share_files", []),
        "guest_email":   entry["guest_email"],
        "guest_name":    entry["guest_name"],
    }

    # Resolve host name
    try:
        from app.models.user import User
        host = User.query.get(meeting.owner_user_id)
        if host:
            guest_view["host_name"] = f"{host.first_name} {host.last_name}".strip()
    except Exception:
        pass

    if not entry["admitted"]:
        guest_view["message"] = "You are in the waiting room. The host will admit you shortly."
    else:
        guest_view["message"] = "You have been admitted. You can now join the meeting."
        # If admitted and Daily.co room exists, provide join info
        meta = meeting.metadata_json or {}
        if meta.get("daily_room_url"):
            guest_view["room_url"] = meta["daily_room_url"]

    return success_response(guest_view)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIT GUEST FROM WAITING ROOM (host only)
# POST /api/meet/<id>/guests/<token>/admit
# ══════════════════════════════════════════════════════════════════════════════

@meet_guest_bp.route("/<int:meeting_id>/guests/<string:token>/admit", methods=["POST"])
@jwt_required()
def admit_guest(meeting_id, token):
    """
    Host admits a guest from the waiting room.
    Spec: "waiting room" — host controls who enters.

    After admission:
    - Guest token is marked as admitted
    - Socket event fired so guest's browser auto-joins
    - Daily.co join token generated for guest
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can admit guests", 403)

    entry, err = _get_valid_token(token)
    if err:
        return error_response(err, 400)
    if entry["meeting_id"] != meeting_id:
        return error_response("Token does not belong to this meeting", 400)

    entry["admitted"] = True

    # Generate Daily.co token for the admitted guest
    daily_token = None
    try:
        meta = meeting.metadata_json or {}
        room_name = meta.get("daily_room_name")
        if room_name:
            from app.services.meet_recording_service import create_participant_token
            token_data = create_participant_token(
                room_name  = room_name,
                user_id    = f"guest_{entry['guest_email']}",
                user_name  = entry["guest_name"],
                is_owner   = False,
            )
            daily_token = token_data["token"]
    except Exception as e:
        logging.warning(f"[GuestRoute] Daily.co token for guest failed: {e}")

    # Emit socket event so guest's browser knows they're admitted
    try:
        from app.socket_events import emit_meeting_event
        emit_meeting_event(meeting_id, "meet_guest_admitted", {
            "meeting_id":  meeting_id,
            "guest_email": entry["guest_email"],
            "guest_name":  entry["guest_name"],
            "token":       token,
            "daily_token": daily_token,
            "room_url":    (meeting.metadata_json or {}).get("daily_room_url"),
        })
    except Exception as e:
        logging.warning(f"[GuestRoute] admit socket emit failed: {e}")

    # Update DB participant record
    try:
        p = MeetParticipant.query.filter_by(
            meeting_id=meeting_id, guest_email=entry["guest_email"]
        ).first()
        if p:
            p.attendance_status = AttendanceStatus.attended
            p.joined_at         = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        logging.warning(f"[GuestRoute] participant update failed: {e}")

    # Publish event
    try:
        from app.services.meet_events import publish, MeetEventType
        publish(MeetEventType.GUEST_ADMITTED, meeting_id, {
            "guest_email": entry["guest_email"],
        })
    except Exception as e:
        logging.warning(f"[GuestRoute] event publish failed: {e}")

    return success_response({
        "message":     f"{entry['guest_name']} admitted to the meeting",
        "guest_email": entry["guest_email"],
        "daily_token": daily_token,
        "room_url":    (meeting.metadata_json or {}).get("daily_room_url"),
    })


# ══════════════════════════════════════════════════════════════════════════════
# REMOVE GUEST
# DELETE /api/meet/<id>/guests/<token>
# ══════════════════════════════════════════════════════════════════════════════

@meet_guest_bp.route("/<int:meeting_id>/guests/<string:token>", methods=["DELETE"])
@jwt_required()
def remove_guest(meeting_id, token):
    """Revoke a guest's access link and remove them from the meeting."""
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can remove guests", 403)

    entry = _guest_tokens.pop(token, None)
    if not entry:
        return error_response("Token not found or already expired", 404)

    # Remove from DB
    try:
        p = MeetParticipant.query.filter_by(
            meeting_id=meeting_id, guest_email=entry["guest_email"]
        ).first()
        if p:
            db.session.delete(p)
            db.session.commit()
    except Exception as e:
        logging.warning(f"[GuestRoute] guest removal DB error: {e}")

    return success_response({
        "message":     f"Guest {entry['guest_email']} removed",
        "guest_email": entry["guest_email"],
    })


# ══════════════════════════════════════════════════════════════════════════════
# LIST GUESTS IN WAITING ROOM
# GET /api/meet/<id>/guests/waiting
# ══════════════════════════════════════════════════════════════════════════════

@meet_guest_bp.route("/<int:meeting_id>/guests/waiting", methods=["GET"])
@jwt_required()
def list_waiting_guests(meeting_id):
    """
    List all guests currently in the waiting room (not yet admitted).
    Host polls this to see who is waiting.
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can view the waiting room", 403)

    now = datetime.utcnow()
    waiting = [
        {
            "token":       token,
            "guest_email": entry["guest_email"],
            "guest_name":  entry["guest_name"],
            "expires_at":  entry["expires_at"].isoformat(),
            "admitted":    entry["admitted"],
        }
        for token, entry in _guest_tokens.items()
        if entry["meeting_id"] == meeting_id
        and not entry["admitted"]
        and entry["expires_at"] > now
    ]

    return success_response({
        "meeting_id":   meeting_id,
        "waiting_count": len(waiting),
        "waiting":       waiting,
    })


# ══════════════════════════════════════════════════════════════════════════════
# GENERATE GUEST-FACING FOLLOW-UP NOTE
# POST /api/meet/<id>/guests/follow-up
# ══════════════════════════════════════════════════════════════════════════════

@meet_guest_bp.route("/<int:meeting_id>/guests/follow-up", methods=["POST"])
@jwt_required()
def generate_guest_follow_up(meeting_id):
    """
    Generate a clean, guest-facing follow-up note separate from
    the internal meeting summary.
    Spec: "internal summary for startup team vs clean follow-up note for guest"

    Body:
        {
            "guest_email":    "investor@vc.com",
            "custom_message": "Optional personal note from host",
            "include_action_items": true
        }
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can generate guest follow-ups", 403)

    data              = request.get_json()
    guest_email       = data.get("guest_email", "")
    custom_message    = data.get("custom_message", "")
    include_actions   = data.get("include_action_items", True)

    # Get action items assigned to or relevant to guest
    from app.models.meet_action_item import MeetActionItem
    action_items = MeetActionItem.query.filter_by(meeting_id=meeting_id).all()

    # Build clean guest note
    lines = [
        f"Thank you for joining: {meeting.title}",
        f"Date: {meeting.actual_end_at.strftime('%B %d, %Y') if meeting.actual_end_at else 'Recent'}",
        "",
    ]

    if custom_message:
        lines += [custom_message, ""]

    if include_actions and action_items:
        lines.append("Follow-up items:")
        for item in action_items:
            due = f" — due {item.due_at.strftime('%b %d')}" if item.due_at else ""
            lines.append(f"  • {item.title}{due}")
        lines.append("")

    lines.append("We will be in touch. Please feel free to reach out with any questions.")

    follow_up_note = "\n".join(lines)

    return success_response({
        "guest_email":     guest_email,
        "follow_up_note":  follow_up_note,
        "meeting_id":      meeting_id,
        "note":            "This is a guest-facing note. Use your email service to send it.",
        "internal_summary_doc": meeting.summary_doc_id,
    })