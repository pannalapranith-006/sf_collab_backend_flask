"""
Service + Routes: Workspace Memory
Path: app/routes/meet_workspace_memory.py

The service functions (generate_episodic_memory, run_full_memory_update etc.)
live here alongside the blueprint. The model lives separately in:
    app/models/meet_workspace_memory.py

Register in blueprints.py:
    from .routes.meet_workspace_memory import meet_memory_bp
    { "blueprint": meet_memory_bp, "url_prefix": "/api/meet" }
"""

import os
import json
import logging
import requests
import threading
from datetime import datetime

from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.meet_workspace_memory import MeetWorkspaceMemory, MemoryType
from app.utils.helper import success_response, error_response


# ══════════════════════════════════════════════════════════════════════════════
# OPENAI HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _call_openai(messages, max_tokens=800):
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        json={
            "model":       "gpt-4o-mini",
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": 0.3,
        },
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"OpenAI call failed: {resp.status_code} {resp.text}")
    return resp.json()["choices"][0]["message"]["content"].strip()


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_episodic_memory(meeting, transcript_text=None):
    """
    Generate a structured episodic memory record from a meeting.
    Returns MeetWorkspaceMemory (not yet saved to DB).
    """
    from app.models.meet_decision import MeetDecision
    from app.models.meet_action_item import MeetActionItem

    decisions    = MeetDecision.query.filter_by(meeting_id=meeting.id).all()
    action_items = MeetActionItem.query.filter_by(meeting_id=meeting.id).all()

    context_parts = [
        f"Meeting: {meeting.title}",
        f"Type: {meeting.meeting_type.value}",
        f"Date: {meeting.actual_end_at.strftime('%Y-%m-%d') if meeting.actual_end_at else 'unknown'}",
    ]
    if decisions:
        context_parts.append("Decisions: " + "; ".join(d.decision_statement for d in decisions))
    if action_items:
        context_parts.append("Action items: " + "; ".join(i.title for i in action_items))
    if transcript_text:
        context_parts.append(f"Transcript excerpt: {transcript_text[:3000]}")

    context = "\n".join(context_parts)

    prompt = f"""You are the SF platform's memory system.
A meeting just ended. Create a concise episodic memory record (max 200 words)
that captures what happened, what was decided, and what needs to happen next.
Write in past tense. Be specific and factual. No fluff.

Meeting context:
{context}

Return a JSON object with these fields:
{{
  "summary": "2-3 sentence summary of what happened",
  "key_outcomes": ["outcome 1", "outcome 2"],
  "open_items": ["item 1", "item 2"],
  "keywords": ["keyword1", "keyword2", "keyword3"]
}}

Return ONLY the JSON, no markdown, no explanation."""

    try:
        raw    = _call_openai([{"role": "user", "content": prompt}], max_tokens=500)
        parsed = json.loads(raw)
    except Exception as e:
        logging.warning(f"[Memory] AI episodic generation failed: {e}. Using fallback.")
        parsed = {
            "summary":      f"Meeting '{meeting.title}' completed with {len(decisions)} decisions and {len(action_items)} action items.",
            "key_outcomes": [d.decision_statement for d in decisions[:3]],
            "open_items":   [i.title for i in action_items[:3]],
            "keywords":     [meeting.meeting_type.value, meeting.title.lower()[:20]],
        }

    content = parsed.get("summary", "")
    if parsed.get("key_outcomes"):
        content += "\n\nKey outcomes:\n" + "\n".join(f"- {o}" for o in parsed["key_outcomes"])
    if parsed.get("open_items"):
        content += "\n\nOpen items:\n" + "\n".join(f"- {o}" for o in parsed["open_items"])

    return MeetWorkspaceMemory(
        meeting_id    = meeting.id,
        startup_id    = meeting.startup_id,
        memory_type   = MemoryType.episodic,
        title         = f"Meeting: {meeting.title}",
        content       = content,
        keywords      = parsed.get("keywords", []),
        importance    = 0.7,
        ai_generated  = True,
        metadata_json = {
            "decision_count":    len(decisions),
            "action_item_count": len(action_items),
            "meeting_type":      meeting.meeting_type.value,
            "raw_ai_response":   parsed,
        },
    )


def generate_decision_memories(meeting):
    """
    Generate individual memory records for each significant decision.
    Returns list of MeetWorkspaceMemory (not yet saved).
    """
    from app.models.meet_decision import MeetDecision
    decisions = MeetDecision.query.filter_by(meeting_id=meeting.id).all()
    records   = []

    for decision in decisions:
        record = MeetWorkspaceMemory(
            meeting_id    = meeting.id,
            startup_id    = meeting.startup_id,
            memory_type   = MemoryType.decision,
            title         = f"Decision: {decision.decision_statement[:80]}",
            content       = (
                f"Decision made in '{meeting.title}' on "
                f"{meeting.actual_end_at.strftime('%Y-%m-%d') if meeting.actual_end_at else 'unknown'}:\n\n"
                f"{decision.decision_statement}"
                + (f"\n\nRationale: {decision.rationale}" if decision.rationale else "")
            ),
            keywords      = [meeting.meeting_type.value, "decision"],
            importance    = 0.9,
            ai_generated  = False,
            metadata_json = {
                "decision_id":       decision.id,
                "linked_milestones": decision.linked_milestone_ids or [],
                "owner_ids":         decision.owner_ids_json or [],
            },
        )
        records.append(record)

    return records


def update_workspace_summary(startup_id):
    """
    Generate or update the rolling workspace summary for a startup.
    Upserts — one summary record per startup.
    """
    recent_memories = (
        MeetWorkspaceMemory.query
        .filter_by(startup_id=startup_id)
        .filter(MeetWorkspaceMemory.memory_type.in_([
            MemoryType.episodic, MemoryType.decision
        ]))
        .order_by(MeetWorkspaceMemory.created_at.desc())
        .limit(10)
        .all()
    )

    if not recent_memories:
        return None

    context = "\n\n".join(
        f"[{m.memory_type.value.upper()}] {m.title}:\n{m.content[:500]}"
        for m in recent_memories
    )

    prompt = f"""You are the SF workspace intelligence system.
Based on recent meeting memory records for a startup, write a concise
workspace summary (max 150 words) that captures the current state,
key decisions made, and what the team is working on right now.

Recent memories:
{context}

Return ONLY the summary text, no headers, no JSON."""

    try:
        summary_text = _call_openai([{"role": "user", "content": prompt}], max_tokens=300)
    except Exception as e:
        logging.warning(f"[Memory] Workspace summary AI call failed: {e}")
        summary_text = f"Workspace has {len(recent_memories)} recent meeting records."

    existing = (
        MeetWorkspaceMemory.query
        .filter_by(startup_id=startup_id, memory_type=MemoryType.workspace)
        .first()
    )

    if existing:
        existing.content    = summary_text
        existing.updated_at = datetime.utcnow()
        db.session.commit()
        return existing

    record = MeetWorkspaceMemory(
        startup_id   = startup_id,
        memory_type  = MemoryType.workspace,
        title        = f"Workspace Summary — Startup {startup_id}",
        content      = summary_text,
        keywords     = ["workspace", "summary"],
        importance   = 1.0,
        ai_generated = True,
    )
    db.session.add(record)
    db.session.commit()
    return record


def run_full_memory_update(meeting, transcript_text=None):
    """
    Run the complete post-meeting memory update pipeline:
      1. Generate episodic memory
      2. Generate decision memories
      3. Update workspace summary
      4. Publish workspace memory event
    """
    saved = []

    try:
        episodic = generate_episodic_memory(meeting, transcript_text)
        db.session.add(episodic)
        db.session.flush()
        saved.append(episodic)
        logging.info(f"[Memory] Episodic memory created for meeting {meeting.id}")

        decision_records = generate_decision_memories(meeting)
        for r in decision_records:
            db.session.add(r)
        saved.extend(decision_records)
        logging.info(f"[Memory] {len(decision_records)} decision memories created")

        db.session.commit()

        if meeting.startup_id:
            summary_record = update_workspace_summary(meeting.startup_id)
            if summary_record:
                saved.append(summary_record)
                logging.info(f"[Memory] Workspace summary updated for startup {meeting.startup_id}")

        try:
            from app.services.meet_events import workspace_memory_updated
            workspace_memory_updated(meeting, memory_type="episodic", summary=episodic.content)
        except Exception as e:
            logging.warning(f"[Memory] event publish failed: {e}")

    except Exception as e:
        logging.error(f"[Memory] Full memory update failed for meeting {meeting.id}: {e}")
        db.session.rollback()

    return saved


def run_memory_update_async(app, meeting_id, transcript_text=None):
    """Run memory update in a background thread."""
    from app.models.meet_meeting import MeetMeeting

    def _run():
        with app.app_context():
            try:
                meeting = MeetMeeting.query.get(meeting_id)
                if meeting:
                    run_full_memory_update(meeting, transcript_text)
            except Exception as e:
                logging.error(f"[Memory] Async update error for meeting {meeting_id}: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    logging.info(f"[Memory] Background memory update started for meeting {meeting_id}")


# ══════════════════════════════════════════════════════════════════════════════
# HTTP ROUTES
# ══════════════════════════════════════════════════════════════════════════════

meet_memory_bp = Blueprint("meet_memory", __name__)


@meet_memory_bp.route("/<int:meeting_id>/memory/update", methods=["POST"])
@jwt_required()
def trigger_memory_update(meeting_id):
    """Trigger workspace memory update in background. Call after transcript ready."""
    uid = get_jwt_identity()
    from app.models.meet_meeting import MeetMeeting, MeetingStatus
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    if str(meeting.owner_user_id) != str(uid):
        return error_response("Only the meeting owner can trigger memory update", 403)
    if meeting.status not in (MeetingStatus.processing, MeetingStatus.indexed):
        return error_response("Meeting must be ended before updating memory", 400)

    run_memory_update_async(
        app        = current_app._get_current_object(),
        meeting_id = meeting.id,
    )
    return success_response({
        "message":    "Memory update started in background",
        "meeting_id": meeting_id,
    })


@meet_memory_bp.route("/<int:meeting_id>/memory", methods=["GET"])
@jwt_required()
def get_meeting_memories(meeting_id):
    """Get all memory records generated from a meeting."""
    from app.models.meet_meeting import MeetMeeting
    from app.models.meet_participant import MeetParticipant
    uid     = get_jwt_identity()
    meeting = MeetMeeting.query.get(meeting_id)
    if not meeting:
        return error_response("Meeting not found", 404)
    is_participant = (
        str(meeting.owner_user_id) == str(uid) or
        MeetParticipant.query.filter_by(meeting_id=meeting_id, user_id=int(uid)).first()
    )
    if not is_participant:
        return error_response("Access denied", 403)
    memories = MeetWorkspaceMemory.query.filter_by(meeting_id=meeting_id).all()
    return success_response({"memories": [m.to_dict() for m in memories]})


@meet_memory_bp.route("/workspace/<int:startup_id>/memory", methods=["GET"])
@jwt_required()
def get_workspace_memory(startup_id):
    """Get all memory records for a startup. The SF assistant reads this."""
    memory_type = request.args.get("type")
    limit       = request.args.get("limit", 20, type=int)

    query = MeetWorkspaceMemory.query.filter_by(startup_id=startup_id)
    if memory_type:
        try:
            query = query.filter_by(memory_type=MemoryType(memory_type))
        except ValueError:
            pass

    memories = query.order_by(
        MeetWorkspaceMemory.importance.desc(),
        MeetWorkspaceMemory.created_at.desc()
    ).limit(limit).all()

    workspace_summary = MeetWorkspaceMemory.query.filter_by(
        startup_id=startup_id, memory_type=MemoryType.workspace
    ).first()

    return success_response({
        "startup_id":        startup_id,
        "workspace_summary": workspace_summary.to_dict() if workspace_summary else None,
        "memories":          [m.to_dict() for m in memories],
        "count":             len(memories),
    })


@meet_memory_bp.route("/workspace/<int:startup_id>/memory/refresh", methods=["POST"])
@jwt_required()
def refresh_workspace_summary(startup_id):
    """Manually regenerate the workspace summary."""
    try:
        record = update_workspace_summary(startup_id)
        if not record:
            return error_response("No meeting memories found for this workspace", 404)
        return success_response({
            "message": "Workspace summary refreshed",
            "summary": record.to_dict(),
        })
    except Exception as e:
        logging.error(f"[Memory] refresh_workspace_summary error: {e}")
        return error_response(f"Failed to refresh summary: {str(e)}", 500)