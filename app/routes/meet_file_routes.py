from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.meet_meeting import MeetMeeting
from app.models.meet_participant import MeetParticipant
from app.models.meet_artifact import MeetArtifact, ArtifactType
from app.utils.helper import success_response, error_response
from datetime import datetime

meet_files_bp = Blueprint("meet_files", __name__)


def _can_access(meeting, user_id):
    if str(meeting.owner_user_id) == str(user_id):
        return True
    return MeetParticipant.query.filter_by(
        meeting_id=meeting.id, user_id=int(user_id)
    ).first() is not None


# GET /api/meet/<id>/files
@meet_files_bp.route("/<int:meeting_id>/files", methods=["GET"])
@jwt_required()
def list_meeting_files(meeting_id):
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if not _can_access(meeting, uid):
        return error_response("Access denied", 403)
    artifacts = MeetArtifact.query.filter_by(meeting_id=meeting_id).all()
    return success_response({"files": [a.to_dict() for a in artifacts]})


# POST /api/meet/<id>/files/attach
@meet_files_bp.route("/<int:meeting_id>/files/attach", methods=["POST"])
@jwt_required()
def attach_file(meeting_id):
    """
    Attach a Drive file to a meeting.
    Body: { drive_file_id, artifact_type, file_name?, file_size_mb? }
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if not _can_access(meeting, uid):
        return error_response("Access denied", 403)

    data          = request.get_json()
    drive_file_id = (data.get("drive_file_id") or "").strip()
    if not drive_file_id:
        return error_response("drive_file_id is required", 400)

    try:
        art_type = ArtifactType(data.get("artifact_type", "notes"))
    except ValueError:
        art_type = ArtifactType.notes

    artifact = MeetArtifact(
        meeting_id         = meeting_id,
        artifact_type      = art_type,
        drive_file_id      = drive_file_id,
        startup_id         = meeting.startup_id,
        milestone_id       = data.get("milestone_id"),
        ai_generated       = False,
        file_size_mb       = data.get("file_size_mb"),
        created_by_user_id = int(uid),
    )
    db.session.add(artifact)
    db.session.commit()

    return success_response(
        {"file": artifact.to_dict()},
        "File attached to meeting",
        201
    )


# DELETE /api/meet/<id>/files/<artifact_id>
@meet_files_bp.route("/<int:meeting_id>/files/<int:artifact_id>", methods=["DELETE"])
@jwt_required()
def detach_file(meeting_id, artifact_id):
    uid      = get_jwt_identity()
    meeting  = MeetMeeting.query.get(meeting_id)
    artifact = MeetArtifact.query.filter_by(
        id=artifact_id, meeting_id=meeting_id
    ).first()

    if not meeting or not artifact:
        return error_response("Not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can remove files", 403)

    db.session.delete(artifact)
    db.session.commit()
    return success_response(message="File detached from meeting")


# POST /api/meet/<id>/files/<artifact_id>/open
@meet_files_bp.route("/<int:meeting_id>/files/<int:artifact_id>/open", methods=["POST"])
@jwt_required()
def open_file(meeting_id, artifact_id):
    """
    Record that a participant opened a file during the meeting.
    Returns the drive_file_id so the frontend can fetch it from Drive.
    If Drive is not yet built, the frontend uses drive_file_id directly.
    """
    uid      = get_jwt_identity()
    meeting  = MeetMeeting.query.get(meeting_id)
    artifact = MeetArtifact.query.filter_by(
        id=artifact_id, meeting_id=meeting_id
    ).first()

    if not meeting or not artifact:
        return error_response("Not found", 404)
    if not _can_access(meeting, uid):
        return error_response("Access denied", 403)

    # Emit real-time event so other participants know someone opened this file
    try:
        from app.socket_events import emit_meeting_event
        emit_meeting_event(meeting_id, "meet_file_opened", {
            "meeting_id":    meeting_id,
            "artifact_id":   artifact_id,
            "drive_file_id": artifact.drive_file_id,
            "artifact_type": artifact.artifact_type.value,
            "opened_by":     uid,
            "ts":            datetime.utcnow().isoformat(),
        })
    except Exception:
        pass

    return success_response({
        "artifact":      artifact.to_dict(),
        "drive_file_id": artifact.drive_file_id,
        "message":       "Fetch this file from SF Drive using the drive_file_id"
    })


# POST /api/meet/<id>/files/<artifact_id>/milestone
@meet_files_bp.route("/<int:meeting_id>/files/<int:artifact_id>/milestone", methods=["POST"])
@jwt_required()
def link_to_milestone(meeting_id, artifact_id):
    """
    Link an artifact to a milestone.
    Body: { milestone_id }
    """
    uid      = get_jwt_identity()
    meeting  = MeetMeeting.query.get(meeting_id)
    artifact = MeetArtifact.query.filter_by(
        id=artifact_id, meeting_id=meeting_id
    ).first()

    if not meeting or not artifact:
        return error_response("Not found", 404)
    if not _can_access(meeting, uid):
        return error_response("Access denied", 403)

    data = request.get_json()
    milestone_id = data.get("milestone_id")
    if not milestone_id:
        return error_response("milestone_id is required", 400)

    artifact.milestone_id = milestone_id
    db.session.commit()

    return success_response(
        {"artifact": artifact.to_dict()},
        "File linked to milestone"
    )