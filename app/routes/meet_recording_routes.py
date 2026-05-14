"""
meet_recording_routes.py — Recording + Transcription HTTP endpoints

Register in blueprints.py:
    from .routes.meet_recording_routes import meet_recording_bp
    { "blueprint": meet_recording_bp, "url_prefix": "/api/meet" }

Also add DAILY_API_KEY to your .env file.
"""

from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.meet_meeting import MeetMeeting, MeetingStatus
from app.models.meet_participant import MeetParticipant, ParticipantRole
from app.utils.helper import success_response, error_response
from app.services.meet_recording_service import (
    setup_meeting_room,
    get_participant_join_token,
    process_recording_async,
    transcribe_audio,
    upload_transcript_to_s3,
)
from app.models.meet_artifact import MeetArtifact, ArtifactType
from datetime import datetime
import logging

meet_recording_bp = Blueprint("meet_recording", __name__)


def _is_participant(meeting, user_id):
    if str(meeting.owner_user_id) == str(user_id):
        return True
    return MeetParticipant.query.filter_by(
        meeting_id=meeting.id, user_id=int(user_id)
    ).first() is not None


# ══════════════════════════════════════════════════════════════════════════════
# CREATE DAILY.CO ROOM  (call before or when starting a meeting)
# POST /api/meet/<id>/room/create
# ══════════════════════════════════════════════════════════════════════════════

@meet_recording_bp.route("/<int:meeting_id>/room/create", methods=["POST"])
@jwt_required()
def create_room(meeting_id):
    """
    Creates the Daily.co video room for this meeting.
    Only the meeting owner can do this.
    Returns the room URL so the frontend can display it.
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)

    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can create the room", 403)
    if meeting.status not in (MeetingStatus.scheduled, MeetingStatus.live):
        return error_response("Meeting must be scheduled or live to create a room", 400)

    # Check if room already exists
    meta = meeting.metadata_json or {}
    if meta.get("daily_room_name"):
        return success_response({
            "room_url":  meta.get("daily_room_url"),
            "room_name": meta.get("daily_room_name"),
            "already_existed": True,
        })

    try:
        room_info = setup_meeting_room(meeting)
        return success_response({
            "room_url":      room_info["room_url"],
            "room_name":     room_info["room_name"],
            "daily_room_id": room_info["daily_room_id"],
            "message":       "Video room created. Share room_url with participants.",
        }, status=201)
    except Exception as e:
        logging.error(f"[RecordingRoute] create_room error: {e}")
        return error_response(f"Failed to create room: {str(e)}", 500)


# ══════════════════════════════════════════════════════════════════════════════
# GET JOIN TOKEN  (each participant calls this to get their Daily.co token)
# POST /api/meet/<id>/room/join-token
# ══════════════════════════════════════════════════════════════════════════════

@meet_recording_bp.route("/<int:meeting_id>/room/join-token", methods=["POST"])
@jwt_required()
def get_join_token(meeting_id):
    """
    Returns a Daily.co meeting token for the current user.
    The frontend passes this token to Daily.co when joining the call.

    Body (optional): { "display_name": "Custom Name" }
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)

    if not meeting:
        return error_response("Meeting not found", 404)
    if not _is_participant(meeting, uid):
        return error_response("Not a participant of this meeting", 403)
    if meeting.status != MeetingStatus.live:
        return error_response("Meeting is not live yet", 400)

    meta      = meeting.metadata_json or {}
    room_name = meta.get("daily_room_name")
    if not room_name:
        return error_response("Video room not set up yet. Ask the host to start the meeting.", 400)

    # Resolve user display name
    try:
        from app.models.user import User
        u = User.query.get(int(uid))
        display_name = request.get_json(silent=True, force=True) or {}
        display_name = display_name.get("display_name") or (
            f"{u.first_name} {u.last_name}".strip() if u else f"User {uid}"
        )
    except Exception:
        display_name = f"User {uid}"

    is_owner = str(meeting.owner_user_id) == str(uid)

    try:
        token_data = get_participant_join_token(
            meeting    = meeting,
            user_id    = uid,
            user_name  = display_name,
            is_owner   = is_owner,
        )
        return success_response({
            "token":      token_data["token"],
            "room_url":   token_data["room_url"],
            "room_name":  token_data["room_name"],
            "user_id":    uid,
            "is_owner":   is_owner,
            "usage":      "Pass token to Daily.co callObject.join({ token }) on the frontend",
        })
    except Exception as e:
        logging.error(f"[RecordingRoute] get_join_token error: {e}")
        return error_response(f"Failed to generate join token: {str(e)}", 500)


# ══════════════════════════════════════════════════════════════════════════════
# TRIGGER RECORDING PROCESSING  (call after meeting ends)
# POST /api/meet/<id>/recording/process
# ══════════════════════════════════════════════════════════════════════════════

@meet_recording_bp.route("/<int:meeting_id>/recording/process", methods=["POST"])
@jwt_required()
def trigger_recording_processing(meeting_id):
    """
    Triggers the post-meeting recording pipeline in a background thread:
      - Downloads recording from Daily.co
      - Transcribes with OpenAI Whisper
      - Uploads transcript to S3
      - Updates meeting with recording_file_id + transcript_file_id
      - Advances meeting status to indexed

    Call this right after POST /api/meet/<id>/end.
    Returns immediately — processing happens in background.
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)

    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can trigger processing", 403)
    if meeting.status != MeetingStatus.processing:
        return error_response(
            f"Meeting must be in 'processing' status. Current: {meeting.status.value}", 400
        )

    meta = meeting.metadata_json or {}
    if not meta.get("daily_room_name"):
        return error_response(
            "No Daily.co room found for this meeting. Recording may not have been enabled.", 400
        )

    # Fire and forget — runs in background thread
    process_recording_async(
        app        = current_app._get_current_object(),
        meeting_id = meeting.id,
    )

    return success_response({
        "message":    "Recording processing started in background.",
        "meeting_id": meeting_id,
        "note":       "Poll GET /api/meet/<id> to check when recording_file_id and transcript_file_id are populated.",
    })


# ══════════════════════════════════════════════════════════════════════════════
# GET RECORDING STATUS
# GET /api/meet/<id>/recording/status
# ══════════════════════════════════════════════════════════════════════════════

@meet_recording_bp.route("/<int:meeting_id>/recording/status", methods=["GET"])
@jwt_required()
def get_recording_status(meeting_id):
    """
    Poll this after triggering processing to check if recording and
    transcript are ready.
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)

    if not meeting:
        return error_response("Meeting not found", 404)
    if not _is_participant(meeting, uid):
        return error_response("Access denied", 403)

    return success_response({
        "meeting_id":          meeting_id,
        "meeting_status":      meeting.status.value,
        "recording_ready":     bool(meeting.recording_file_id),
        "recording_file_id":   meeting.recording_file_id,
        "transcript_ready":    bool(meeting.transcript_file_id),
        "transcript_file_id":  meeting.transcript_file_id,
        "summary_ready":       bool(meeting.summary_doc_id),
    })


# ══════════════════════════════════════════════════════════════════════════════
# MANUAL TRANSCRIPT UPLOAD  (fallback if Whisper fails or you have your own)
# POST /api/meet/<id>/recording/transcript
# ══════════════════════════════════════════════════════════════════════════════

@meet_recording_bp.route("/<int:meeting_id>/recording/transcript", methods=["POST"])
@jwt_required()
def upload_transcript(meeting_id):
    """
    Manually upload or re-upload a transcript.
    Use this if automatic Whisper transcription failed or you have
    a transcript from another source.

    Body:
        { "transcript_text": "Full transcript text here..." }
    OR
        { "transcript_file_id": "s3:key/to/existing/file" }
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)

    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can upload transcripts", 403)

    data = request.get_json()
    transcript_text    = data.get("transcript_text", "").strip()
    transcript_file_id = data.get("transcript_file_id", "").strip()

    if not transcript_text and not transcript_file_id:
        return error_response("Provide either transcript_text or transcript_file_id", 400)

    # If raw text provided, upload to S3
    if transcript_text and not transcript_file_id:
        try:
            transcript_file_id = upload_transcript_to_s3(meeting.id, {
                "text":     transcript_text,
                "segments": [],
                "language": "en",
                "duration": 0,
                "source":   "manual_upload",
            })
        except Exception as e:
            logging.error(f"[RecordingRoute] manual transcript S3 upload failed: {e}")
            # Fall back to storing text directly in metadata
            meta = meeting.metadata_json or {}
            meta["transcript_text_fallback"] = transcript_text[:50000]  # cap at 50k chars
            meeting.metadata_json = meta
            transcript_file_id = f"local:meeting_{meeting.id}_manual_transcript"

    meeting.transcript_file_id = transcript_file_id

    # Save as artifact
    existing = MeetArtifact.query.filter_by(
        meeting_id=meeting.id, artifact_type=ArtifactType.transcript
    ).first()
    if existing:
        existing.drive_file_id = transcript_file_id
    else:
        db.session.add(MeetArtifact(
            meeting_id         = meeting.id,
            artifact_type      = ArtifactType.transcript,
            drive_file_id      = transcript_file_id,
            startup_id         = meeting.startup_id,
            ai_generated       = False,
            created_by_user_id = int(uid),
        ))

    # Auto-advance to indexed if recording also exists
    if meeting.recording_file_id and meeting.transcript_file_id:
        meeting.status = MeetingStatus.indexed

    db.session.commit()

    return success_response({
        "transcript_file_id": transcript_file_id,
        "meeting_status":     meeting.status.value,
        "message":            "Transcript saved successfully",
    })