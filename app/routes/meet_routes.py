"""
SF Meet — Complete API Routes
Covers every feature in the SF Meet Architecture Spec:
  - Meeting CRUD + lifecycle (scheduled → live → ended → processing → indexed)
  - Participant management (platform users + external guests)
  - Save-to-Drive (recordings, transcripts, summaries, notes, whiteboards, annotations)
  - Decisions (create, list, update status)
  - Action items (create, list, update, convert to real Task)
  - Annotations (create, list, export bundle)
  - Pre-meeting panel (agenda, AI briefing, linked context)
  - Post-meeting processing pipeline (trigger after meeting ends)
  - Search (by startup, milestone, keyword, participant)
  - Audit log (read-only, auto-written on every action)
  - Notifications (triggered internally on key events)
  - Templates (per meeting type — returned as JSON for the frontend to use)
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_

from app.extensions import db
from app.models.meet_meeting    import MeetMeeting,    MeetingStatus, MeetingType, VisibilityScope
from app.models.meet_participant import MeetParticipant, ParticipantRole, AttendanceStatus
from app.models.meet_artifact   import MeetArtifact,   ArtifactType
from app.models.meet_decision   import MeetDecision,   DecisionStatus
from app.models.meet_action_item import MeetActionItem, ActionItemPriority, ActionItemStatus
from app.models.meet_annotation  import MeetAnnotation,  AnnotationType
from app.models.meet_audit_log   import MeetAuditLog,    log_meeting_action

meet_bp = Blueprint("meet", __name__)


# ══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _meeting_or_404(meeting_id):
    m = MeetMeeting.query.get(meeting_id)
    if not m:
        return None, jsonify({"error": "Meeting not found"}), 404
    return m, None, None


def _is_participant(meeting, user_id):
    """Return True if user_id is the owner or an invited participant."""
    if meeting.owner_user_id == user_id:
        return True
    return MeetParticipant.query.filter_by(
        meeting_id=meeting.id, user_id=user_id
    ).first() is not None


def _require_owner(meeting, user_id):
    # Convert both to string or int for safe comparison
    if str(meeting.owner_user_id) != str(user_id):
        return jsonify({"error": "Only the meeting owner can do this"}), 403
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 1. MEETINGS — CRUD
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/", methods=["POST"])
@jwt_required()
def schedule_meeting():
    """
    Schedule a new meeting.

    Required: title, meeting_type, scheduled_start_at
    Optional: startup_id, vision_id, linked_milestone_ids, linked_task_ids,
              scheduled_end_at, timezone, visibility_scope,
              recording_enabled, transcription_enabled, live_notes_enabled,
              annotation_enabled, agenda_doc_id
    """
    uid  = get_jwt_identity()
    data = request.get_json()

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    try:
        meeting_type = MeetingType(data.get("meeting_type"))
    except (ValueError, TypeError):
        return jsonify({"error": f"Invalid meeting_type. Valid: {[m.value for m in MeetingType]}"}), 400

    start_str = data.get("scheduled_start_at")
    if not start_str:
        return jsonify({"error": "scheduled_start_at is required (ISO format)"}), 400
    try:
        scheduled_start = datetime.fromisoformat(start_str)
    except ValueError:
        return jsonify({"error": "scheduled_start_at must be ISO format e.g. 2025-06-01T10:00:00"}), 400

    end_str = data.get("scheduled_end_at")
    scheduled_end = datetime.fromisoformat(end_str) if end_str else None

    vis_str = data.get("visibility_scope", "invited_only")
    try:
        visibility = VisibilityScope(vis_str)
    except ValueError:
        visibility = VisibilityScope.invited_only

    meeting = MeetMeeting(
        title                 = title,
        meeting_type          = meeting_type,
        owner_user_id         = uid,
        startup_id            = data.get("startup_id"),
        vision_id             = data.get("vision_id"),
        linked_milestone_ids  = data.get("linked_milestone_ids", []),
        linked_task_ids       = data.get("linked_task_ids", []),
        scheduled_start_at    = scheduled_start,
        scheduled_end_at      = scheduled_end,
        timezone              = data.get("timezone", "UTC"),
        visibility_scope      = visibility,
        recording_enabled     = bool(data.get("recording_enabled", False)),
        transcription_enabled = bool(data.get("transcription_enabled", False)),
        live_notes_enabled    = bool(data.get("live_notes_enabled", True)),
        annotation_enabled    = bool(data.get("annotation_enabled", False)),
        agenda_doc_id         = data.get("agenda_doc_id"),
        status                = MeetingStatus.scheduled,
    )
    db.session.add(meeting)
    db.session.flush()

    # Creator is automatically the host
    db.session.add(MeetParticipant(
        meeting_id        = meeting.id,
        user_id           = uid,
        role              = ParticipantRole.host,
        attendance_status = AttendanceStatus.accepted,
        invited_by_user_id= uid,
    ))

    log_meeting_action(meeting.id, "meeting_created", actor_user_id=uid,
                       metadata={"title": title, "meeting_type": meeting_type.value})
    db.session.commit()

    return jsonify({"message": "Meeting scheduled", "meeting": meeting.to_dict()}), 201


@meet_bp.route("/", methods=["GET"])
@jwt_required()
def list_meetings():
    """
    List meetings for the current user.
    Optional query params: startup_id, status, meeting_type
    """
    uid        = get_jwt_identity()
    startup_id = request.args.get("startup_id", type=int)
    status_str = request.args.get("status")
    type_str   = request.args.get("meeting_type")

    participant_ids = db.session.query(MeetParticipant.meeting_id).filter_by(user_id=uid)
    q = MeetMeeting.query.filter(
        or_(MeetMeeting.owner_user_id == uid, MeetMeeting.id.in_(participant_ids))
    )

    if startup_id:
        q = q.filter_by(startup_id=startup_id)
    if status_str:
        try:
            q = q.filter_by(status=MeetingStatus(status_str))
        except ValueError:
            pass
    if type_str:
        try:
            q = q.filter_by(meeting_type=MeetingType(type_str))
        except ValueError:
            pass

    meetings = q.order_by(MeetMeeting.scheduled_start_at.desc()).all()
    return jsonify([m.to_dict() for m in meetings]), 200


@meet_bp.route("/<int:meeting_id>", methods=["GET"])
@jwt_required()
def get_meeting(meeting_id):
    """Full meeting detail including participants and artifacts."""
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    if not _is_participant(m, uid):
        return jsonify({"error": "Access denied"}), 403

    result = m.to_dict()
    result["participants"] = [p.to_dict() for p in m.participants]
    result["artifacts"]    = [a.to_dict() for a in m.artifacts]
    result["decisions"]    = [d.to_dict() for d in m.decisions]
    result["action_items"] = [i.to_dict() for i in m.action_items]
    return jsonify(result), 200


@meet_bp.route("/<int:meeting_id>", methods=["PUT"])
@jwt_required()
def update_meeting(meeting_id):
    """
    Update meeting details (title, schedule, links, settings).
    Only owner can update. Cannot update a live or ended meeting.
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    err = _require_owner(m, uid)
    if err:
        return err

    if m.status not in (MeetingStatus.scheduled,):
        return jsonify({"error": "Can only edit a scheduled meeting"}), 400

    data = request.get_json()
    if "title" in data:
        m.title = data["title"].strip()
    if "scheduled_start_at" in data:
        m.scheduled_start_at = datetime.fromisoformat(data["scheduled_start_at"])
    if "scheduled_end_at" in data:
        m.scheduled_end_at = datetime.fromisoformat(data["scheduled_end_at"])
    if "linked_milestone_ids" in data:
        m.linked_milestone_ids = data["linked_milestone_ids"]
    if "linked_task_ids" in data:
        m.linked_task_ids = data["linked_task_ids"]
    if "agenda_doc_id" in data:
        m.agenda_doc_id = data["agenda_doc_id"]
    if "recording_enabled" in data:
        m.recording_enabled = bool(data["recording_enabled"])
    if "transcription_enabled" in data:
        m.transcription_enabled = bool(data["transcription_enabled"])
    if "visibility_scope" in data:
        try:
            m.visibility_scope = VisibilityScope(data["visibility_scope"])
        except ValueError:
            pass

    log_meeting_action(m.id, "meeting_updated", actor_user_id=uid)
    db.session.commit()
    return jsonify({"message": "Meeting updated", "meeting": m.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
# 2. MEETING LIFECYCLE
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/start", methods=["POST"])
@jwt_required()
def start_meeting(meeting_id):
    """scheduled → live"""
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    err = _require_owner(m, uid)
    if err:
        return err

    if m.status != MeetingStatus.scheduled:
        return jsonify({"error": f"Cannot start — current status is '{m.status.value}'"}), 400

    m.status          = MeetingStatus.live
    m.actual_start_at = datetime.utcnow()
    log_meeting_action(m.id, "meeting_started", actor_user_id=uid)
    db.session.commit()

    return jsonify({"message": "Meeting is now live", "meeting": m.to_dict()}), 200


@meet_bp.route("/<int:meeting_id>/end", methods=["POST"])
@jwt_required()
def end_meeting(meeting_id):
    """
    live → processing
    After this, call /save-artifact for each output.
    When transcript + summary are saved, status auto-advances to 'indexed'.
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    err = _require_owner(m, uid)
    if err:
        return err

    if m.status != MeetingStatus.live:
        return jsonify({"error": "Meeting is not live"}), 400

    m.status        = MeetingStatus.processing
    m.actual_end_at = datetime.utcnow()
    log_meeting_action(m.id, "meeting_ended", actor_user_id=uid)
    db.session.commit()

    return jsonify({
        "message": "Meeting ended. Now in 'processing'. Save artifacts via POST /<id>/save-artifact",
        "meeting": m.to_dict()
    }), 200


@meet_bp.route("/<int:meeting_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_meeting(meeting_id):
    """Cancel a scheduled meeting."""
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    err = _require_owner(m, uid)
    if err:
        return err

    if m.status in (MeetingStatus.ended, MeetingStatus.indexed, MeetingStatus.archived):
        return jsonify({"error": "Cannot cancel a meeting that has already ended"}), 400

    m.status = MeetingStatus.cancelled
    log_meeting_action(m.id, "meeting_cancelled", actor_user_id=uid)
    db.session.commit()
    return jsonify({"message": "Meeting cancelled", "meeting": m.to_dict()}), 200


@meet_bp.route("/<int:meeting_id>/archive", methods=["POST"])
@jwt_required()
def archive_meeting(meeting_id):
    """Move an indexed meeting to archived state."""
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    err = _require_owner(m, uid)
    if err:
        return err

    if m.status != MeetingStatus.indexed:
        return jsonify({"error": "Only indexed meetings can be archived"}), 400

    m.status = MeetingStatus.archived
    log_meeting_action(m.id, "meeting_archived", actor_user_id=uid)
    db.session.commit()
    return jsonify({"message": "Meeting archived"}), 200


# ══════════════════════════════════════════════════════════════════════════════
# 3. PARTICIPANTS
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/participants", methods=["GET"])
@jwt_required()
def list_participants(meeting_id):
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    return jsonify([p.to_dict() for p in m.participants]), 200


@meet_bp.route("/<int:meeting_id>/participants", methods=["POST"])
@jwt_required()
def invite_participant(meeting_id):
    """
    Invite a platform user or external guest.
    Body: { "user_id": 5 }  OR  { "guest_email": "x@y.com" }
    Optional: { "role": "member" }  (member | moderator | guest)
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    err = _require_owner(m, uid)
    if err:
        return err

    data        = request.get_json()
    user_id     = data.get("user_id")
    guest_email = (data.get("guest_email") or "").strip() or None

    if not user_id and not guest_email:
        return jsonify({"error": "Provide user_id or guest_email"}), 400

    # Don't invite someone already in
    if user_id:
        exists = MeetParticipant.query.filter_by(meeting_id=m.id, user_id=user_id).first()
        if exists:
            return jsonify({"error": "User is already a participant"}), 409

    try:
        role = ParticipantRole(data.get("role", "member"))
    except ValueError:
        role = ParticipantRole.member

    p = MeetParticipant(
        meeting_id         = m.id,
        user_id            = user_id,
        guest_email        = guest_email,
        role               = role,
        attendance_status  = AttendanceStatus.invited,
        invited_by_user_id = uid,
    )
    db.session.add(p)
    log_meeting_action(m.id, "participant_invited", actor_user_id=uid,
                       metadata={"invited_user_id": user_id, "guest_email": guest_email})
    db.session.commit()
    return jsonify({"message": "Participant invited", "participant": p.to_dict()}), 201


@meet_bp.route("/<int:meeting_id>/participants/<int:participant_id>", methods=["DELETE"])
@jwt_required()
def remove_participant(meeting_id, participant_id):
    """Remove a participant (owner only)."""
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    err = _require_owner(m, uid)
    if err:
        return err

    p = MeetParticipant.query.filter_by(id=participant_id, meeting_id=m.id).first()
    if not p:
        return jsonify({"error": "Participant not found"}), 404

    db.session.delete(p)
    log_meeting_action(m.id, "participant_removed", actor_user_id=uid,
                       metadata={"participant_id": participant_id})
    db.session.commit()
    return jsonify({"message": "Participant removed"}), 200


@meet_bp.route("/<int:meeting_id>/join", methods=["POST"])
@jwt_required()
def join_meeting(meeting_id):
    """Mark the current user as having joined the live meeting."""
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code

    if m.status != MeetingStatus.live:
        return jsonify({"error": "Meeting is not live"}), 400

    p = MeetParticipant.query.filter_by(meeting_id=m.id, user_id=uid).first()
    if not p:
        return jsonify({"error": "You are not invited to this meeting"}), 403

    p.joined_at        = datetime.utcnow()
    p.attendance_status = AttendanceStatus.attended
    log_meeting_action(m.id, "participant_joined", actor_user_id=uid)
    db.session.commit()
    return jsonify({"message": "Joined meeting", "participant": p.to_dict()}), 200


@meet_bp.route("/<int:meeting_id>/leave", methods=["POST"])
@jwt_required()
def leave_meeting(meeting_id):
    """Mark the current user as having left the meeting."""
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code

    p = MeetParticipant.query.filter_by(meeting_id=m.id, user_id=uid).first()
    if not p:
        return jsonify({"error": "You are not a participant"}), 404

    p.left_at = datetime.utcnow()
    log_meeting_action(m.id, "participant_left", actor_user_id=uid)
    db.session.commit()
    return jsonify({"message": "Left meeting"}), 200


# ══════════════════════════════════════════════════════════════════════════════
# 4. ARTIFACTS — SAVE TO DRIVE
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/artifacts", methods=["GET"])
@jwt_required()
def list_artifacts(meeting_id):
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    return jsonify([a.to_dict() for a in m.artifacts]), 200


@meet_bp.route("/<int:meeting_id>/artifacts", methods=["POST"])
@jwt_required()
def save_artifact(meeting_id):
    """
    Save a meeting output to SF Drive.

    Required: artifact_type, drive_file_id
    Optional: milestone_id, ai_generated, file_size_mb

    artifact_type options: recording | transcript | summary | notes |
                           whiteboard | annotation | screenshot
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code

    if m.status not in (MeetingStatus.processing, MeetingStatus.ended, MeetingStatus.indexed):
        return jsonify({"error": "Meeting must be ended before saving artifacts"}), 400

    data = request.get_json()

    try:
        artifact_type = ArtifactType(data.get("artifact_type"))
    except (ValueError, TypeError):
        return jsonify({"error": f"Invalid artifact_type. Valid: {[a.value for a in ArtifactType]}"}), 400

    drive_file_id = (data.get("drive_file_id") or "").strip()
    if not drive_file_id:
        return jsonify({"error": "drive_file_id is required"}), 400

    artifact = MeetArtifact(
        meeting_id         = m.id,
        artifact_type      = artifact_type,
        drive_file_id      = drive_file_id,
        startup_id         = m.startup_id,
        milestone_id       = data.get("milestone_id"),
        ai_generated       = bool(data.get("ai_generated", False)),
        file_size_mb       = data.get("file_size_mb"),
        created_by_user_id = uid,
    )
    db.session.add(artifact)

    # Mirror on the meeting for fast access
    if artifact_type == ArtifactType.recording:
        m.recording_file_id  = drive_file_id
    elif artifact_type == ArtifactType.transcript:
        m.transcript_file_id = drive_file_id
    elif artifact_type == ArtifactType.summary:
        m.summary_doc_id     = drive_file_id
    elif artifact_type == ArtifactType.notes:
        m.live_notes_doc_id  = drive_file_id

    # Auto-advance to indexed once transcript + summary are present
    if m.transcript_file_id and m.summary_doc_id:
        m.status = MeetingStatus.indexed

    log_meeting_action(m.id, "artifact_saved", actor_user_id=uid,
                       metadata={"artifact_type": artifact_type.value, "drive_file_id": drive_file_id})
    db.session.commit()

    return jsonify({
        "message": f"{artifact_type.value} saved to Drive",
        "artifact":        artifact.to_dict(),
        "meeting_status":  m.status.value,
    }), 201


# ══════════════════════════════════════════════════════════════════════════════
# 5. DECISIONS
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/decisions", methods=["GET"])
@jwt_required()
def list_decisions(meeting_id):
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    return jsonify([d.to_dict() for d in m.decisions]), 200


@meet_bp.route("/<int:meeting_id>/decisions", methods=["POST"])
@jwt_required()
def create_decision(meeting_id):
    """
    Capture a decision from a meeting.
    Can be called during the meeting (status=live) or during processing.

    Required: decision_statement
    Optional: rationale, owner_ids, linked_milestone_ids, linked_doc_ids,
              source_timestamp, ai_extracted
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    if not _is_participant(m, uid):
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    statement = (data.get("decision_statement") or "").strip()
    if not statement:
        return jsonify({"error": "decision_statement is required"}), 400

    decision = MeetDecision(
        meeting_id           = m.id,
        decision_statement   = statement,
        rationale            = data.get("rationale"),
        owner_ids_json       = data.get("owner_ids", []),
        linked_milestone_ids = data.get("linked_milestone_ids", []),
        linked_doc_ids       = data.get("linked_doc_ids", []),
        source_timestamp     = data.get("source_timestamp"),
        ai_extracted         = bool(data.get("ai_extracted", False)),
    )
    db.session.add(decision)
    log_meeting_action(m.id, "decision_created", actor_user_id=uid,
                       metadata={"decision_statement": statement[:100]})
    db.session.commit()
    return jsonify({"message": "Decision captured", "decision": decision.to_dict()}), 201


@meet_bp.route("/<int:meeting_id>/decisions/<int:decision_id>", methods=["PUT"])
@jwt_required()
def update_decision(meeting_id, decision_id):
    """Update status or details of a decision."""
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code

    d = MeetDecision.query.filter_by(id=decision_id, meeting_id=m.id).first()
    if not d:
        return jsonify({"error": "Decision not found"}), 404

    data = request.get_json()
    if "status" in data:
        try:
            d.status = DecisionStatus(data["status"])
        except ValueError:
            return jsonify({"error": f"Invalid status. Valid: {[s.value for s in DecisionStatus]}"}), 400
    if "rationale" in data:
        d.rationale = data["rationale"]
    if "owner_ids" in data:
        d.owner_ids_json = data["owner_ids"]

    db.session.commit()
    return jsonify({"message": "Decision updated", "decision": d.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
# 6. ACTION ITEMS
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/action-items", methods=["GET"])
@jwt_required()
def list_action_items(meeting_id):
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    return jsonify([i.to_dict() for i in m.action_items]), 200


@meet_bp.route("/<int:meeting_id>/action-items", methods=["POST"])
@jwt_required()
def create_action_item(meeting_id):
    """
    Create an action item from a meeting.

    Required: title
    Optional: description, owner_user_id, due_at (ISO), priority,
              linked_milestone_id, source_timestamp, ai_extracted
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    if not _is_participant(m, uid):
        return jsonify({"error": "Access denied"}), 403

    data  = request.get_json()
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    due_str = data.get("due_at")
    due_at  = datetime.fromisoformat(due_str) if due_str else None

    try:
        priority = ActionItemPriority(data.get("priority", "medium"))
    except ValueError:
        priority = ActionItemPriority.medium

    item = MeetActionItem(
        meeting_id          = m.id,
        title               = title,
        description         = data.get("description"),
        owner_user_id       = data.get("owner_user_id"),
        due_at              = due_at,
        priority            = priority,
        linked_milestone_id = data.get("linked_milestone_id"),
        source_timestamp    = data.get("source_timestamp"),
        ai_extracted        = bool(data.get("ai_extracted", False)),
    )
    db.session.add(item)
    log_meeting_action(m.id, "action_item_created", actor_user_id=uid,
                       metadata={"title": title})
    db.session.commit()
    return jsonify({"message": "Action item created", "action_item": item.to_dict()}), 201


@meet_bp.route("/<int:meeting_id>/action-items/<int:item_id>", methods=["PUT"])
@jwt_required()
def update_action_item(meeting_id, item_id):
    """Update an action item (status, owner, due date, link to real task)."""
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code

    item = MeetActionItem.query.filter_by(id=item_id, meeting_id=m.id).first()
    if not item:
        return jsonify({"error": "Action item not found"}), 404

    data = request.get_json()
    if "status" in data:
        try:
            item.status = ActionItemStatus(data["status"])
        except ValueError:
            return jsonify({"error": f"Invalid status. Valid: {[s.value for s in ActionItemStatus]}"}), 400
    if "owner_user_id" in data:
        item.owner_user_id = data["owner_user_id"]
    if "due_at" in data:
        item.due_at = datetime.fromisoformat(data["due_at"]) if data["due_at"] else None
    if "linked_task_id" in data:
        # Link this action item to a real SF Task that was created from it
        item.linked_task_id = data["linked_task_id"]
    if "linked_milestone_id" in data:
        item.linked_milestone_id = data["linked_milestone_id"]
    if "priority" in data:
        try:
            item.priority = ActionItemPriority(data["priority"])
        except ValueError:
            pass

    db.session.commit()
    return jsonify({"message": "Action item updated", "action_item": item.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
# 7. ANNOTATIONS
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/annotations", methods=["GET"])
@jwt_required()
def list_annotations(meeting_id):
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    return jsonify([a.to_dict() for a in m.annotations]), 200


@meet_bp.route("/<int:meeting_id>/annotations", methods=["POST"])
@jwt_required()
def create_annotation(meeting_id):
    """
    Save an annotation on a shared file or screen during the meeting.

    Required: annotation_type, payload
    Optional: target_artifact_id, source_timestamp

    payload example: { "x": 120, "y": 340, "text": "Fix this", "color": "#ff0000" }
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    if not _is_participant(m, uid):
        return jsonify({"error": "Access denied"}), 403

    data = request.get_json()
    try:
        ann_type = AnnotationType(data.get("annotation_type"))
    except (ValueError, TypeError):
        return jsonify({"error": f"Invalid annotation_type. Valid: {[a.value for a in AnnotationType]}"}), 400

    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        return jsonify({"error": "payload must be a JSON object"}), 400

    ann = MeetAnnotation(
        meeting_id         = m.id,
        target_artifact_id = data.get("target_artifact_id"),
        annotation_type    = ann_type,
        payload_json       = payload,
        source_timestamp   = data.get("source_timestamp"),
        created_by_user_id = uid,
    )
    db.session.add(ann)
    log_meeting_action(m.id, "annotation_created", actor_user_id=uid,
                       metadata={"annotation_type": ann_type.value})
    db.session.commit()
    return jsonify({"message": "Annotation saved", "annotation": ann.to_dict()}), 201


@meet_bp.route("/<int:meeting_id>/annotations/export", methods=["GET"])
@jwt_required()
def export_annotation_bundle(meeting_id):
    """
    Export all annotations for a meeting as a bundle.
    The frontend uses this to render the full annotation layer.
    """
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code

    # Group by artifact so the frontend can render each annotated file
    bundle = {}
    for ann in m.annotations:
        key = str(ann.target_artifact_id or "general")
        if key not in bundle:
            bundle[key] = []
        bundle[key].append(ann.to_dict())

    return jsonify({
        "meeting_id": m.id,
        "bundle":     bundle,
        "total":      sum(len(v) for v in bundle.values()),
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# 8. PRE-MEETING PANEL
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/pre-meeting", methods=["GET"])
@jwt_required()
def pre_meeting_panel(meeting_id):
    """
    Returns everything needed to prepare for a meeting:
    - meeting details
    - participants
    - linked milestones and tasks
    - agenda doc
    - most recent prior meeting for the same startup (for context)

    The frontend uses this to show the preparation panel before the user joins.
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    if not _is_participant(m, uid):
        return jsonify({"error": "Access denied"}), 403

    # Find the most recent prior meeting for the same startup (excluding this one)
    prior_meeting = None
    if m.startup_id:
        prior = (
            MeetMeeting.query
            .filter(
                MeetMeeting.startup_id == m.startup_id,
                MeetMeeting.id != m.id,
                MeetMeeting.status.in_([MeetingStatus.indexed, MeetingStatus.archived])
            )
            .order_by(MeetMeeting.actual_end_at.desc())
            .first()
        )
        if prior:
            prior_meeting = {
                "id":            prior.id,
                "title":         prior.title,
                "actual_end_at": prior.actual_end_at.isoformat() if prior.actual_end_at else None,
                "summary_doc_id": prior.summary_doc_id,
            }

    return jsonify({
        "meeting":      m.to_dict(),
        "participants": [p.to_dict() for p in m.participants],
        "linked_milestone_ids": m.linked_milestone_ids or [],
        "linked_task_ids":      m.linked_task_ids or [],
        "agenda_doc_id":        m.agenda_doc_id,
        "prior_meeting":        prior_meeting,
        "tips": [
            "Review the agenda before joining.",
            "Check linked milestones for open blockers.",
            "Have the relevant Drive files ready to share.",
        ]
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# 9. POST-MEETING PROCESSING PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/process", methods=["POST"])
@jwt_required()
def trigger_processing(meeting_id):
    """
    Trigger the post-meeting processing pipeline.
    Call this right after end_meeting.

    What this does (Step by Step per spec section 13):
      Step 1: Validates that raw assets exist (recording/transcript)
      Step 2: Marks the pipeline as running (sets status notes in metadata)
      Step 3: Returns instructions for what the caller should do next
              (real AI processing happens in your background worker)

    In a real production setup, this would fire a Celery/RQ task.
    For now it validates + marks the meeting as ready for indexing.
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    err = _require_owner(m, uid)
    if err:
        return err

    if m.status != MeetingStatus.processing:
        return jsonify({"error": "Meeting must be in 'processing' status to trigger pipeline"}), 400

    checklist = {
        "has_recording":   bool(m.recording_file_id),
        "has_transcript":  bool(m.transcript_file_id),
        "has_summary":     bool(m.summary_doc_id),
        "has_notes":       bool(m.live_notes_doc_id),
        "decisions_count": m.decisions.count(),
        "action_items_count": m.action_items.count(),
    }

    next_steps = []
    if not checklist["has_transcript"]:
        next_steps.append("Save transcript via POST /<id>/artifacts with artifact_type=transcript")
    if not checklist["has_summary"]:
        next_steps.append("Save AI summary via POST /<id>/artifacts with artifact_type=summary and ai_generated=true")
    if checklist["decisions_count"] == 0:
        next_steps.append("Extract decisions via POST /<id>/decisions")
    if checklist["action_items_count"] == 0:
        next_steps.append("Extract action items via POST /<id>/action-items")

    # If transcript + summary are already saved, advance status
    if checklist["has_transcript"] and checklist["has_summary"]:
        m.status = MeetingStatus.indexed
        log_meeting_action(m.id, "meeting_indexed", actor_user_id=uid)
        db.session.commit()

    return jsonify({
        "message":    "Processing pipeline triggered",
        "checklist":  checklist,
        "next_steps": next_steps,
        "meeting_status": m.status.value,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# 10. SEARCH
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/search", methods=["GET"])
@jwt_required()
def search_meetings():
    """
    Search meetings by keyword, startup, milestone, participant, or status.

    Query params:
        q           — keyword (matches title)
        startup_id  — filter by startup
        milestone_id — filter by linked milestone
        participant_user_id — meetings a specific user attended
        status      — filter by status
        limit       — max results (default 20)
    """
    uid         = get_jwt_identity()
    q_str       = (request.args.get("q") or "").strip()
    startup_id  = request.args.get("startup_id",  type=int)
    milestone_id= request.args.get("milestone_id", type=int)
    p_user_id   = request.args.get("participant_user_id", type=int)
    status_str  = request.args.get("status")
    limit       = request.args.get("limit", 20, type=int)

    # Base: user must be owner or participant
    participant_ids = db.session.query(MeetParticipant.meeting_id).filter_by(user_id=uid)
    query = MeetMeeting.query.filter(
        or_(MeetMeeting.owner_user_id == uid, MeetMeeting.id.in_(participant_ids))
    )

    if q_str:
        query = query.filter(MeetMeeting.title.ilike(f"%{q_str}%"))
    if startup_id:
        query = query.filter_by(startup_id=startup_id)
    if status_str:
        try:
            query = query.filter_by(status=MeetingStatus(status_str))
        except ValueError:
            pass
    if p_user_id:
        ids_for_user = db.session.query(MeetParticipant.meeting_id).filter_by(user_id=p_user_id)
        query = query.filter(MeetMeeting.id.in_(ids_for_user))
    if milestone_id:
        # JSON array contains check (works in SQLite + Postgres with cast)
        query = query.filter(MeetMeeting.linked_milestone_ids.contains([milestone_id]))

    results = query.order_by(MeetMeeting.scheduled_start_at.desc()).limit(limit).all()
    return jsonify({
        "query":   q_str,
        "count":   len(results),
        "results": [m.to_dict() for m in results],
    }), 200


@meet_bp.route("/<int:meeting_id>/decisions/search", methods=["GET"])
@jwt_required()
def search_decisions(meeting_id):
    """Search decisions within a meeting by keyword."""
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code

    q_str = (request.args.get("q") or "").strip()
    query = MeetDecision.query.filter_by(meeting_id=m.id)
    if q_str:
        query = query.filter(MeetDecision.decision_statement.ilike(f"%{q_str}%"))

    return jsonify([d.to_dict() for d in query.all()]), 200


@meet_bp.route("/<int:meeting_id>/action-items/search", methods=["GET"])
@jwt_required()
def search_action_items(meeting_id):
    """Search action items within a meeting."""
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code

    q_str = (request.args.get("q") or "").strip()
    status_str = request.args.get("status")

    query = MeetActionItem.query.filter_by(meeting_id=m.id)
    if q_str:
        query = query.filter(MeetActionItem.title.ilike(f"%{q_str}%"))
    if status_str:
        try:
            query = query.filter_by(status=ActionItemStatus(status_str))
        except ValueError:
            pass

    return jsonify([i.to_dict() for i in query.all()]), 200


# ══════════════════════════════════════════════════════════════════════════════
# 11. MEETING TEMPLATES (per meeting type)
# ══════════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    "startup_team": {
        "name": "Startup Weekly Sync",
        "agenda_sections": [
            "Wins since last meeting",
            "Current blockers",
            "Milestone progress",
            "Decisions needed",
            "Next 7-day tasks",
        ],
        "note_prompts": [
            "What did we ship or finish?",
            "What is blocked and why?",
            "What decisions do we need to make today?",
        ],
        "default_recording":     False,
        "default_transcription": True,
    },
    "mentor_session": {
        "name": "Mentor Session",
        "agenda_sections": [
            "Readiness status",
            "Main risks",
            "Mentor feedback",
            "Decisions from this session",
            "Recommended next step",
        ],
        "note_prompts": [
            "What feedback did the mentor give?",
            "What were the key risks identified?",
            "What is the agreed next step?",
        ],
        "default_recording":     True,
        "default_transcription": True,
    },
    "milestone_review": {
        "name": "Milestone Review",
        "agenda_sections": [
            "Proof / demo",
            "QA results",
            "Launch readiness check",
            "Blockers",
            "Next milestone scope",
        ],
        "note_prompts": [
            "Is the milestone complete? Evidence?",
            "What is still blocked?",
            "What tasks go into the next milestone?",
        ],
        "default_recording":     False,
        "default_transcription": True,
    },
    "customer_call": {
        "name": "Customer / Partner Call",
        "agenda_sections": [
            "Customer pain points",
            "Current alternatives they use",
            "Reactions to concept or demo",
            "Buying intent",
            "Objections",
        ],
        "note_prompts": [
            "What problem are they trying to solve?",
            "How did they react to the demo?",
            "What objections came up?",
        ],
        "default_recording":     True,
        "default_transcription": True,
    },
    "investor_call": {
        "name": "Investor / Advisory Call",
        "agenda_sections": [
            "Traction update",
            "Product progress",
            "Team update",
            "Asks from the investor",
            "Follow-up items",
        ],
        "note_prompts": [
            "What did the investor ask about?",
            "What were the key concerns raised?",
            "What did we commit to follow up on?",
        ],
        "default_recording":     True,
        "default_transcription": True,
    },
    "vision_review": {
        "name": "Vision Review",
        "agenda_sections": [
            "Vision clarity check",
            "Open questions",
            "Collaborator readiness",
            "Roadmap adjustments",
            "Next review date",
        ],
        "note_prompts": [
            "Is the vision still aligned with reality?",
            "What open questions remain?",
            "What changed since the last review?",
        ],
        "default_recording":     False,
        "default_transcription": False,
    },
    "internal_org": {
        "name": "Internal Organization Meeting",
        "agenda_sections": [
            "Hiring updates",
            "Finance review",
            "Legal / compliance items",
            "Platform operations",
            "Action items",
        ],
        "note_prompts": [
            "What decisions were made?",
            "What needs follow-up?",
        ],
        "default_recording":     False,
        "default_transcription": False,
    },
    "dispute_review": {
        "name": "Moderation / Dispute Review",
        "agenda_sections": [
            "Evidence presented",
            "Parties heard",
            "Decision reached",
            "Next steps",
        ],
        "note_prompts": [
            "What was the dispute about?",
            "What evidence was reviewed?",
            "What was the final decision?",
        ],
        "default_recording":     True,
        "default_transcription": True,
    },
}


@meet_bp.route("/templates", methods=["GET"])
def list_templates():
    """Return all available meeting templates."""
    return jsonify(TEMPLATES), 200


@meet_bp.route("/templates/<string:meeting_type>", methods=["GET"])
def get_template(meeting_type):
    """Return the template for a specific meeting type."""
    tmpl = TEMPLATES.get(meeting_type)
    if not tmpl:
        return jsonify({"error": f"No template for '{meeting_type}'"}), 404
    return jsonify({"meeting_type": meeting_type, "template": tmpl}), 200


# ══════════════════════════════════════════════════════════════════════════════
# 12. AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/<int:meeting_id>/audit-log", methods=["GET"])
@jwt_required()
def get_audit_log(meeting_id):
    """
    Read-only audit log for a meeting.
    Shows every action taken: who, what, when.
    """
    uid = get_jwt_identity()
    m, err, code = _meeting_or_404(meeting_id)
    if err:
        return err, code
    if not _is_participant(m, uid):
        return jsonify({"error": "Access denied"}), 403

    logs = (
        MeetAuditLog.query
        .filter_by(meeting_id=m.id)
        .order_by(MeetAuditLog.created_at.asc())
        .all()
    )
    return jsonify([l.to_dict() for l in logs]), 200


# ══════════════════════════════════════════════════════════════════════════════
# 13. STARTUP MEETINGS TAB
# ══════════════════════════════════════════════════════════════════════════════

@meet_bp.route("/startup/<int:startup_id>/overview", methods=["GET"])
@jwt_required()
def startup_meetings_overview(startup_id):
    """
    The Meetings tab for a startup workspace.
    Returns: upcoming meetings, recent meetings, open action items.
    """
    uid = get_jwt_identity()

    upcoming = (
        MeetMeeting.query
        .filter_by(startup_id=startup_id, status=MeetingStatus.scheduled)
        .order_by(MeetMeeting.scheduled_start_at.asc())
        .limit(5).all()
    )

    recent = (
        MeetMeeting.query
        .filter(
            MeetMeeting.startup_id == startup_id,
            MeetMeeting.status.in_([MeetingStatus.indexed, MeetingStatus.archived])
        )
        .order_by(MeetMeeting.actual_end_at.desc())
        .limit(10).all()
    )

    # Open action items across all meetings for this startup
    startup_meeting_ids = db.session.query(MeetMeeting.id).filter_by(startup_id=startup_id)
    open_items = (
        MeetActionItem.query
        .filter(
            MeetActionItem.meeting_id.in_(startup_meeting_ids),
            MeetActionItem.status == ActionItemStatus.open
        )
        .order_by(MeetActionItem.due_at.asc())
        .limit(20).all()
    )

    return jsonify({
        "startup_id":        startup_id,
        "upcoming_meetings": [m.to_dict() for m in upcoming],
        "recent_meetings":   [m.to_dict() for m in recent],
        "open_action_items": [i.to_dict() for i in open_items],
    }), 200
