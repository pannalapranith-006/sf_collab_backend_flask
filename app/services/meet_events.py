"""
meet_events.py — SF Meet Domain Event System
Spec reference: Section 22 — Event Model

Publishes domain events internally so other SF services can react:
    Drive service, task service, milestone service,
    notification engine, AI memory updater, workspace summary updater,
    analytics pipeline

Events published:
    MeetingScheduled, MeetingUpdated, MeetingStarted, MeetingEnded,
    ParticipantJoined, ParticipantLeft, RecordingSaved, TranscriptReady,
    SummaryGenerated, AnnotationCreated, NotesSaved,
    MeetingArtifactSavedToDrive, DecisionExtractedFromMeeting,
    ActionItemsCreatedFromMeeting, FollowUpMeetingSuggested,
    MeetingPermissionsChanged

Architecture:
    Events are published synchronously to all registered handlers.
    Each handler runs in a try/except so one failing handler
    does not block the others.
    For production, swap the in-process bus with Celery/Redis/RQ.
"""

import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ── Event definitions ──────────────────────────────────────────────────────────

@dataclass
class MeetEvent:
    """Base class for all SF Meet domain events."""
    event_type:  str
    meeting_id:  int
    occurred_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    payload:     Dict[str, Any] = field(default_factory=dict)


# ── Event type constants ───────────────────────────────────────────────────────

class MeetEventType:
    MEETING_SCHEDULED             = "MeetingScheduled"
    MEETING_UPDATED               = "MeetingUpdated"
    MEETING_STARTED               = "MeetingStarted"
    MEETING_ENDED                 = "MeetingEnded"
    MEETING_CANCELLED             = "MeetingCancelled"
    MEETING_ARCHIVED              = "MeetingArchived"
    PARTICIPANT_JOINED            = "ParticipantJoined"
    PARTICIPANT_LEFT              = "ParticipantLeft"
    RECORDING_SAVED               = "RecordingSaved"
    TRANSCRIPT_READY              = "TranscriptReady"
    SUMMARY_GENERATED             = "SummaryGenerated"
    ANNOTATION_CREATED            = "AnnotationCreated"
    NOTES_SAVED                   = "NotesSaved"
    ARTIFACT_SAVED_TO_DRIVE       = "MeetingArtifactSavedToDrive"
    DECISION_EXTRACTED            = "DecisionExtractedFromMeeting"
    ACTION_ITEMS_CREATED          = "ActionItemsCreatedFromMeeting"
    FOLLOW_UP_MEETING_SUGGESTED   = "FollowUpMeetingSuggested"
    MEETING_PERMISSIONS_CHANGED   = "MeetingPermissionsChanged"
    MILESTONE_LINKED              = "MeetingMilestoneLinked"
    WORKSPACE_MEMORY_UPDATED      = "WorkspaceMemoryUpdated"
    GUEST_INVITED                 = "GuestInvited"
    GUEST_ADMITTED                = "GuestAdmitted"


# ── Event Bus ─────────────────────────────────────────────────────────────────

class MeetEventBus:
    """
    Simple synchronous in-process event bus.
    Handlers are registered per event_type.
    All handlers for an event run when publish() is called.
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logging.debug(f"[EventBus] Registered handler {handler.__name__} for {event_type}")

    def publish(self, event: MeetEvent):
        """
        Publish an event to all registered handlers.
        Each handler is called in a try/except so failures are isolated.
        """
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            logging.debug(f"[EventBus] No handlers for {event.event_type}")
            return

        logging.info(f"[EventBus] Publishing {event.event_type} for meeting {event.meeting_id}")
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logging.error(
                    f"[EventBus] Handler {handler.__name__} failed for "
                    f"{event.event_type}: {e}", exc_info=True
                )

    def publish_many(self, events: List[MeetEvent]):
        for event in events:
            self.publish(event)


# Module-level singleton bus
event_bus = MeetEventBus()


# ── Convenience publisher functions ───────────────────────────────────────────
# Call these from routes and services instead of building events manually.

def publish(event_type: str, meeting_id: int, payload: dict = None):
    event_bus.publish(MeetEvent(
        event_type = event_type,
        meeting_id = meeting_id,
        payload    = payload or {},
    ))


def meeting_scheduled(meeting):
    publish(MeetEventType.MEETING_SCHEDULED, meeting.id, {
        "title":        meeting.title,
        "meeting_type": meeting.meeting_type.value,
        "owner_id":     meeting.owner_user_id,
        "startup_id":   meeting.startup_id,
        "scheduled_at": meeting.scheduled_start_at.isoformat() if meeting.scheduled_start_at else None,
    })


def meeting_started(meeting):
    publish(MeetEventType.MEETING_STARTED, meeting.id, {
        "actual_start_at": meeting.actual_start_at.isoformat() if meeting.actual_start_at else None,
        "startup_id":      meeting.startup_id,
    })


def meeting_ended(meeting):
    publish(MeetEventType.MEETING_ENDED, meeting.id, {
        "actual_end_at":  meeting.actual_end_at.isoformat() if meeting.actual_end_at else None,
        "startup_id":     meeting.startup_id,
        "duration_secs":  (
            (meeting.actual_end_at - meeting.actual_start_at).total_seconds()
            if meeting.actual_end_at and meeting.actual_start_at else None
        ),
    })


def transcript_ready(meeting, transcript_file_id):
    publish(MeetEventType.TRANSCRIPT_READY, meeting.id, {
        "transcript_file_id": transcript_file_id,
        "startup_id":         meeting.startup_id,
    })


def recording_saved(meeting, recording_file_id):
    publish(MeetEventType.RECORDING_SAVED, meeting.id, {
        "recording_file_id": recording_file_id,
        "startup_id":        meeting.startup_id,
    })


def summary_generated(meeting, summary_doc_id):
    publish(MeetEventType.SUMMARY_GENERATED, meeting.id, {
        "summary_doc_id": summary_doc_id,
        "startup_id":     meeting.startup_id,
    })


def decision_extracted(meeting, decision):
    publish(MeetEventType.DECISION_EXTRACTED, meeting.id, {
        "decision_id":        decision.id,
        "decision_statement": decision.decision_statement,
        "linked_milestones":  decision.linked_milestone_ids or [],
    })


def action_items_created(meeting, action_items):
    publish(MeetEventType.ACTION_ITEMS_CREATED, meeting.id, {
        "action_item_ids":    [i.id for i in action_items],
        "count":              len(action_items),
        "linked_milestones":  list({i.linked_milestone_id for i in action_items if i.linked_milestone_id}),
    })


def artifact_saved_to_drive(meeting, artifact):
    publish(MeetEventType.ARTIFACT_SAVED_TO_DRIVE, meeting.id, {
        "artifact_id":    artifact.id,
        "artifact_type":  artifact.artifact_type.value,
        "drive_file_id":  artifact.drive_file_id,
        "milestone_id":   artifact.milestone_id,
        "startup_id":     meeting.startup_id,
    })


def milestone_linked(meeting, milestone_id):
    publish(MeetEventType.MILESTONE_LINKED, meeting.id, {
        "milestone_id": milestone_id,
        "startup_id":   meeting.startup_id,
    })


def workspace_memory_updated(meeting, memory_type, summary):
    publish(MeetEventType.WORKSPACE_MEMORY_UPDATED, meeting.id, {
        "memory_type": memory_type,
        "startup_id":  meeting.startup_id,
        "summary":     summary[:500] if summary else None,
    })


def guest_invited(meeting, guest_email):
    publish(MeetEventType.GUEST_INVITED, meeting.id, {
        "guest_email": guest_email,
        "meeting_type": meeting.meeting_type.value,
    })


# ── Event Handlers (consumers) ────────────────────────────────────────────────
# Register handlers at app startup. Each handler reacts to one event type.

def _on_meeting_ended_notify_participants(event: MeetEvent):
    """Send in-app notification when a meeting ends."""
    try:
        from app.models.meet_participant import MeetParticipant
        from app.socket_events import emit_meeting_event
        participants = MeetParticipant.query.filter_by(
            meeting_id=event.meeting_id
        ).all()
        for p in participants:
            if p.user_id:
                emit_meeting_event(event.meeting_id, "meet_status_changed", {
                    "meeting_id": event.meeting_id,
                    "status":     "ended",
                })
                break  # emit_meeting_event broadcasts to room, one call is enough
    except Exception as e:
        logging.warning(f"[EventBus] _on_meeting_ended_notify error: {e}")


def _on_transcript_ready_update_milestone(event: MeetEvent):
    """When transcript is ready, update linked milestone notes."""
    try:
        from app.models.meet_meeting import MeetMeeting
        meeting = MeetMeeting.query.get(event.meeting_id)
        if not meeting or not meeting.linked_milestone_ids:
            return
        # Hook into your milestone service here
        # MilestoneService.append_note(milestone_id, f"Meeting transcript ready: {meeting.title}")
        logging.info(f"[EventBus] Transcript ready — milestone update hook fired for meeting {event.meeting_id}")
    except Exception as e:
        logging.warning(f"[EventBus] _on_transcript_ready_update_milestone error: {e}")


def _on_action_items_created_emit_socket(event: MeetEvent):
    """Emit socket event when action items are created from a meeting."""
    try:
        from app.socket_events import emit_meeting_event
        emit_meeting_event(event.meeting_id, "meet_action_items_ready", {
            "meeting_id":      event.meeting_id,
            "count":           event.payload.get("count", 0),
            "action_item_ids": event.payload.get("action_item_ids", []),
        })
    except Exception as e:
        logging.warning(f"[EventBus] _on_action_items_created_emit_socket error: {e}")


def register_all_handlers():
    """
    Call once at app startup to wire all event handlers.
    Add to create_app() in __init__.py after socketio.init_app(app).
    """
    event_bus.subscribe(MeetEventType.MEETING_ENDED,      _on_meeting_ended_notify_participants)
    event_bus.subscribe(MeetEventType.TRANSCRIPT_READY,   _on_transcript_ready_update_milestone)
    event_bus.subscribe(MeetEventType.ACTION_ITEMS_CREATED, _on_action_items_created_emit_socket)
    logging.info("[EventBus] SF Meet event handlers registered")