"""
meet_milestone_routes.py — Meeting ↔ Milestone Integration
Spec reference: Section 7.3 — Milestone Integration

Meetings can be attached to milestones.
Outputs from milestone-linked meetings can:
  - update milestone notes
  - attach files as proof or dependencies
  - create new tasks
  - mark blockers
  - create risk notes

Register in blueprints.py:
    from .routes.meet_milestone_routes import meet_milestone_bp
    { "blueprint": meet_milestone_bp, "url_prefix": "/api/meet" }
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.meet_meeting import MeetMeeting, MeetingStatus
from app.models.meet_participant import MeetParticipant
from app.models.meet_decision import MeetDecision
from app.models.meet_action_item import MeetActionItem
from app.models.meet_artifact import MeetArtifact, ArtifactType
from app.utils.helper import success_response, error_response
from datetime import datetime
import logging

meet_milestone_bp = Blueprint("meet_milestone", __name__)


def _can_access(meeting, user_id):
    if str(meeting.owner_user_id) == str(user_id):
        return True
    return MeetParticipant.query.filter_by(
        meeting_id=meeting.id, user_id=int(user_id)
    ).first() is not None


# ══════════════════════════════════════════════════════════════════════════════
# LINK MEETING TO MILESTONE(S)
# POST /api/meet/<id>/milestones/link
# ══════════════════════════════════════════════════════════════════════════════

@meet_milestone_bp.route("/<int:meeting_id>/milestones/link", methods=["POST"])
@jwt_required()
def link_milestones(meeting_id):
    """
    Link one or more milestones to a meeting.
    Replaces the existing linked_milestone_ids list or appends to it.

    Body:
        {
            "milestone_ids": [1, 4, 7],   # required — list of milestone IDs
            "mode": "append" | "replace"  # optional, default "append"
        }
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if not _can_access(meeting, uid):
        return error_response("Access denied", 403)

    data         = request.get_json()
    milestone_ids = data.get("milestone_ids", [])
    mode          = data.get("mode", "append")

    if not milestone_ids or not isinstance(milestone_ids, list):
        return error_response("milestone_ids must be a non-empty list", 400)

    existing = meeting.linked_milestone_ids or []

    if mode == "replace":
        meeting.linked_milestone_ids = milestone_ids
    else:
        # Append, deduplicating
        combined = list(set(existing + milestone_ids))
        meeting.linked_milestone_ids = combined

    db.session.commit()

    # Publish event for each newly linked milestone
    from app.services.meet_events import milestone_linked
    for mid in milestone_ids:
        try:
            milestone_linked(meeting, mid)
        except Exception as e:
            logging.warning(f"[MilestoneRoute] event publish failed: {e}")

    return success_response({
        "meeting_id":          meeting_id,
        "linked_milestone_ids": meeting.linked_milestone_ids,
        "message":             f"{len(milestone_ids)} milestone(s) linked",
    })


# ══════════════════════════════════════════════════════════════════════════════
# UNLINK MILESTONE
# DELETE /api/meet/<id>/milestones/<milestone_id>
# ══════════════════════════════════════════════════════════════════════════════

@meet_milestone_bp.route("/<int:meeting_id>/milestones/<int:milestone_id>", methods=["DELETE"])
@jwt_required()
def unlink_milestone(meeting_id, milestone_id):
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can unlink milestones", 403)

    existing = meeting.linked_milestone_ids or []
    if milestone_id not in existing:
        return error_response("Milestone is not linked to this meeting", 404)

    meeting.linked_milestone_ids = [m for m in existing if m != milestone_id]
    db.session.commit()

    return success_response({
        "meeting_id":           meeting_id,
        "linked_milestone_ids": meeting.linked_milestone_ids,
        "message":              f"Milestone {milestone_id} unlinked",
    })


# ══════════════════════════════════════════════════════════════════════════════
# UPDATE MILESTONE NOTES FROM MEETING
# POST /api/meet/<id>/milestones/<milestone_id>/update-notes
# ══════════════════════════════════════════════════════════════════════════════

@meet_milestone_bp.route("/<int:meeting_id>/milestones/<int:milestone_id>/update-notes", methods=["POST"])
@jwt_required()
def update_milestone_notes(meeting_id, milestone_id):
    """
    Push meeting outputs to milestone notes.
    Spec: "Outputs from a milestone-linked meeting should be able to
           update milestone notes."

    This endpoint:
      1. Collects decisions, action items, and summary from the meeting
      2. Formats them as structured notes
      3. Calls your milestone service/API to append those notes
      4. Links any proof artifacts to the milestone

    Body (optional):
        {
            "include_decisions":    true,
            "include_action_items": true,
            "include_summary":      true,
            "custom_note":          "Additional context..."
        }
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if not _can_access(meeting, uid):
        return error_response("Access denied", 403)

    # Verify this milestone is actually linked
    linked = meeting.linked_milestone_ids or []
    if milestone_id not in linked:
        return error_response(
            f"Milestone {milestone_id} is not linked to this meeting. "
            f"Link it first via POST /milestones/link", 400
        )

    data                = request.get_json() or {}
    include_decisions   = data.get("include_decisions", True)
    include_action_items= data.get("include_action_items", True)
    include_summary     = data.get("include_summary", True)
    custom_note         = data.get("custom_note", "")

    # ── Build the note content ─────────────────────────────────────────────────
    note_sections = []
    note_sections.append(f"## Meeting: {meeting.title}")
    note_sections.append(f"**Date:** {meeting.actual_end_at.strftime('%Y-%m-%d') if meeting.actual_end_at else 'In progress'}")
    note_sections.append(f"**Type:** {meeting.meeting_type.value.replace('_', ' ').title()}")

    if custom_note:
        note_sections.append(f"\n{custom_note}")

    decisions_data    = []
    action_items_data = []

    if include_decisions:
        decisions = MeetDecision.query.filter_by(meeting_id=meeting_id).all()
        if decisions:
            note_sections.append("\n### Decisions Made")
            for d in decisions:
                note_sections.append(f"- {d.decision_statement}")
                decisions_data.append(d.to_dict())

    if include_action_items:
        action_items = MeetActionItem.query.filter_by(
            meeting_id=meeting_id,
            linked_milestone_id=milestone_id
        ).all()
        # Also include unlinked action items from this meeting
        all_items = MeetActionItem.query.filter_by(meeting_id=meeting_id).all()
        if all_items:
            note_sections.append("\n### Action Items")
            for item in all_items:
                due = f" (due {item.due_at.strftime('%Y-%m-%d')})" if item.due_at else ""
                note_sections.append(f"- [{item.priority.value.upper()}] {item.title}{due}")
                action_items_data.append(item.to_dict())

    if include_summary and meeting.summary_doc_id:
        note_sections.append(f"\n### Summary")
        note_sections.append(f"Full summary: {meeting.summary_doc_id}")

    full_note = "\n".join(note_sections)

    # ── Link proof artifacts to milestone ─────────────────────────────────────
    artifacts_linked = []
    artifacts = MeetArtifact.query.filter_by(meeting_id=meeting_id).all()
    for artifact in artifacts:
        if not artifact.milestone_id:
            artifact.milestone_id = milestone_id
            artifacts_linked.append(artifact.to_dict())

    db.session.commit()

    # ── Call your milestone service here ──────────────────────────────────────
    # When you build the GoalMilestone update service, call it here:
    #
    #   from app.services.milestone_service import MilestoneService
    #   MilestoneService.append_note(milestone_id, full_note, author_user_id=uid)
    #   MilestoneService.attach_files(milestone_id, [a["drive_file_id"] for a in artifacts_linked])
    #
    # For now we return the formatted note so the frontend/other service can use it.

    return success_response({
        "meeting_id":      meeting_id,
        "milestone_id":    milestone_id,
        "note_content":    full_note,
        "decisions":       decisions_data,
        "action_items":    action_items_data,
        "artifacts_linked": artifacts_linked,
        "message":         "Milestone notes prepared. Pass note_content to your milestone update service.",
    })


# ══════════════════════════════════════════════════════════════════════════════
# ATTACH PROOF FILE TO MILESTONE
# POST /api/meet/<id>/milestones/<milestone_id>/proof
# ══════════════════════════════════════════════════════════════════════════════

@meet_milestone_bp.route("/<int:meeting_id>/milestones/<int:milestone_id>/proof", methods=["POST"])
@jwt_required()
def attach_proof_to_milestone(meeting_id, milestone_id):
    """
    Attach a meeting artifact as proof for a milestone.
    Spec: "attach files as proof or dependencies"

    Body: { "artifact_id": int }
    OR  : { "drive_file_id": str, "artifact_type": str }
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if not _can_access(meeting, uid):
        return error_response("Access denied", 403)

    linked = meeting.linked_milestone_ids or []
    if milestone_id not in linked:
        return error_response(f"Milestone {milestone_id} is not linked to this meeting", 400)

    data        = request.get_json()
    artifact_id = data.get("artifact_id")

    if artifact_id:
        artifact = MeetArtifact.query.filter_by(
            id=artifact_id, meeting_id=meeting_id
        ).first()
        if not artifact:
            return error_response("Artifact not found in this meeting", 404)
        artifact.milestone_id = milestone_id
        db.session.commit()
        return success_response({
            "artifact":     artifact.to_dict(),
            "milestone_id": milestone_id,
            "message":      "Artifact attached as milestone proof",
        })

    # Create new artifact from drive_file_id
    drive_file_id = (data.get("drive_file_id") or "").strip()
    if not drive_file_id:
        return error_response("Provide either artifact_id or drive_file_id", 400)

    try:
        art_type = ArtifactType(data.get("artifact_type", "notes"))
    except ValueError:
        art_type = ArtifactType.notes

    artifact = MeetArtifact(
        meeting_id         = meeting_id,
        artifact_type      = art_type,
        drive_file_id      = drive_file_id,
        startup_id         = meeting.startup_id,
        milestone_id       = milestone_id,
        ai_generated       = False,
        created_by_user_id = int(uid),
    )
    db.session.add(artifact)
    db.session.commit()

    return success_response({
        "artifact":     artifact.to_dict(),
        "milestone_id": milestone_id,
        "message":      "File attached as milestone proof",
    }, status=201)


# ══════════════════════════════════════════════════════════════════════════════
# CREATE BLOCKER FROM MEETING
# POST /api/meet/<id>/milestones/<milestone_id>/blocker
# ══════════════════════════════════════════════════════════════════════════════

@meet_milestone_bp.route("/<int:meeting_id>/milestones/<int:milestone_id>/blocker", methods=["POST"])
@jwt_required()
def mark_blocker(meeting_id, milestone_id):
    """
    Mark a blocker identified during the meeting against a milestone.
    Spec: "mark blockers"

    Body:
        {
            "blocker_description": str,
            "owner_user_id":       int (optional),
            "severity":            "low" | "medium" | "high"
        }

    Creates a MeetDecision record tagged as a blocker and
    a MeetActionItem to resolve it.
    """
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if not _can_access(meeting, uid):
        return error_response("Access denied", 403)

    data        = request.get_json()
    description = (data.get("blocker_description") or "").strip()
    if not description:
        return error_response("blocker_description is required", 400)

    severity       = data.get("severity", "medium")
    owner_user_id  = data.get("owner_user_id")

    # Record as a decision with BLOCKER label
    decision = MeetDecision(
        meeting_id         = meeting_id,
        decision_statement = f"[BLOCKER] {description}",
        rationale          = f"Severity: {severity}. Identified against milestone {milestone_id}.",
        owner_ids_json     = [owner_user_id] if owner_user_id else [],
        linked_milestone_ids = [milestone_id],
        ai_extracted       = False,
    )
    db.session.add(decision)

    # Also create an action item to resolve it
    from app.models.meet_action_item import ActionItemPriority
    priority_map = {"low": ActionItemPriority.low, "medium": ActionItemPriority.medium,
                    "high": ActionItemPriority.high, "urgent": ActionItemPriority.urgent}
    action_item = MeetActionItem(
        meeting_id          = meeting_id,
        title               = f"Resolve blocker: {description[:100]}",
        description         = description,
        owner_user_id       = owner_user_id,
        priority            = priority_map.get(severity, ActionItemPriority.medium),
        linked_milestone_id = milestone_id,
        ai_extracted        = False,
    )
    db.session.add(action_item)
    db.session.commit()

    return success_response({
        "decision":    decision.to_dict(),
        "action_item": action_item.to_dict(),
        "message":     "Blocker recorded and action item created",
    }, status=201)


# ══════════════════════════════════════════════════════════════════════════════
# GET ALL MEETING OUTPUTS FOR A MILESTONE
# GET /api/meet/milestones/<milestone_id>/outputs
# ══════════════════════════════════════════════════════════════════════════════

@meet_milestone_bp.route("/milestones/<int:milestone_id>/outputs", methods=["GET"])
@jwt_required()
def get_milestone_meeting_outputs(milestone_id):
    """
    Get all meetings, decisions, action items, and artifacts
    linked to a specific milestone.
    Spec: "outputs from a milestone-linked meeting"
    """
    # Find all meetings linked to this milestone
    meetings = MeetMeeting.query.filter(
        MeetMeeting.linked_milestone_ids.contains([milestone_id])
    ).all()

    meeting_ids = [m.id for m in meetings]

    # Decisions linked to this milestone
    decisions = MeetDecision.query.filter(
        MeetDecision.meeting_id.in_(meeting_ids),
        MeetDecision.linked_milestone_ids.contains([milestone_id])
    ).all() if meeting_ids else []

    # Action items linked to this milestone
    action_items = MeetActionItem.query.filter(
        MeetActionItem.linked_milestone_id == milestone_id
    ).all()

    # Artifacts (proof files) linked to this milestone
    artifacts = MeetArtifact.query.filter_by(
        milestone_id=milestone_id
    ).all()

    return success_response({
        "milestone_id":  milestone_id,
        "meetings":      [m.to_dict() for m in meetings],
        "decisions":     [d.to_dict() for d in decisions],
        "action_items":  [i.to_dict() for i in action_items],
        "artifacts":     [a.to_dict() for a in artifacts],
        "summary": {
            "meeting_count":     len(meetings),
            "decision_count":    len(decisions),
            "action_item_count": len(action_items),
            "artifact_count":    len(artifacts),
        }
    })