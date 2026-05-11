"""
app/services/meet_service.py

Business logic for SF Meet: lifecycle management, schedule conflict detection,
status transitions, and event emission.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, or_

from app.extensions import db
from app.models.meet_meeting import (
    MeetMeeting,
    MeetAuditLog,
    MeetingStatus,
    MeetingType,
    VisibilityScope,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Allowed status transitions (unchanged)
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[MeetingStatus, set[MeetingStatus]] = {
    MeetingStatus.SCHEDULED:  {MeetingStatus.PREPARING, MeetingStatus.CANCELLED},
    MeetingStatus.PREPARING:  {MeetingStatus.LIVE, MeetingStatus.CANCELLED},
    MeetingStatus.LIVE:       {MeetingStatus.PAUSED, MeetingStatus.ENDED},
    MeetingStatus.PAUSED:     {MeetingStatus.LIVE, MeetingStatus.ENDED},
    MeetingStatus.ENDED:      {MeetingStatus.PROCESSING},
    MeetingStatus.PROCESSING: {MeetingStatus.INDEXED},
    MeetingStatus.INDEXED:    {MeetingStatus.ARCHIVED},
    MeetingStatus.ARCHIVED:   set(),
    MeetingStatus.CANCELLED:  set(),
}

# Statuses that block creating a new meeting in the same slot
ACTIVE_STATUSES = {
    MeetingStatus.SCHEDULED,
    MeetingStatus.PREPARING,
    MeetingStatus.LIVE,
    MeetingStatus.PAUSED,
}


# ---------------------------------------------------------------------------
# Exceptions (unchanged)
# ---------------------------------------------------------------------------

class MeetServiceError(Exception):
    """Base service exception — maps to HTTP 400."""


class MeetNotFoundError(MeetServiceError):
    """Raised when a meeting cannot be found — maps to HTTP 404."""


class MeetConflictError(MeetServiceError):
    """Raised when a schedule conflict is detected — maps to HTTP 409."""


class MeetStateError(MeetServiceError):
    """Raised when a requested status transition is invalid — maps to HTTP 422."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_404(meeting_id: int) -> MeetMeeting:
    meeting = db.session.get(MeetMeeting, meeting_id)
    if not meeting:
        raise MeetNotFoundError(f"Meeting '{meeting_id}' not found.")
    return meeting


def _assert_transition(meeting: MeetMeeting, target: MeetingStatus) -> None:
    allowed = VALID_TRANSITIONS.get(meeting.status, set())
    if target not in allowed:
        raise MeetStateError(
            f"Cannot transition from '{meeting.status.value}' to '{target.value}'. "
            f"Allowed: {[s.value for s in allowed] or 'none'}."
        )


def _audit(actor_user_id: int, meeting: MeetMeeting, action: str, meta: dict | None = None) -> None:
    log = MeetAuditLog(
        actor_user_id=actor_user_id,
        meeting_id=meeting.id,
        action=action,
        metadata_json=meta or {},
    )
    db.session.add(log)


def _emit_event(event_name: str, payload: dict) -> None:
    """
    Stub for the SF domain event bus.
    Replace with your actual event publisher (e.g. Celery task, Redis stream).
    """
    logger.info("EVENT %s: %s", event_name, payload)


# ---------------------------------------------------------------------------
# Schedule conflict check
# ---------------------------------------------------------------------------

def check_schedule_conflict(
    owner_user_id: int,
    start: datetime,
    end: datetime,
    exclude_meeting_id: Optional[int] = None,
) -> bool:
    """
    Returns True if the owner already has an active meeting overlapping [start, end).
    An overlap exists when:  existing.start < new.end  AND  existing.end > new.start
    """
    query = db.session.query(MeetMeeting).filter(
        MeetMeeting.owner_user_id == owner_user_id,
        MeetMeeting.status.in_(ACTIVE_STATUSES),
        MeetMeeting.scheduled_start_at < end,
        MeetMeeting.scheduled_end_at   > start,
    )
    if exclude_meeting_id is not None:
        query = query.filter(MeetMeeting.id != exclude_meeting_id)

    return db.session.query(query.exists()).scalar()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class MeetService:

    # ------------------------------------------------------------------ #
    # Create                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_meeting(actor_user_id: int, data: dict) -> MeetMeeting:
        """
        Create a new meeting.
        `data` is the cleaned dict from validate_create_meeting_request().
        """
        start = data["scheduled_start_at"]
        end   = data["scheduled_end_at"]

        if check_schedule_conflict(data["owner_user_id"], start, end):
            raise MeetConflictError(
                "The meeting owner already has an active meeting during this time slot."
            )

        meeting = MeetMeeting(
            title                  = data["title"],
            meeting_type           = data["meeting_type"],
            owner_user_id          = data["owner_user_id"],
            owner_scope_type       = data["owner_scope_type"],
            owner_scope_id         = data["owner_scope_id"],
            workspace_id           = data.get("workspace_id"),
            startup_id             = data.get("startup_id"),
            organization_id        = data.get("organization_id"),
            vision_id              = data.get("vision_id"),
            scheduled_start_at     = start,
            scheduled_end_at       = end,
            timezone               = data.get("timezone", "UTC"),
            status                 = MeetingStatus.SCHEDULED,
            visibility_scope       = data["visibility_scope"],
            recording_enabled      = data.get("recording_enabled", False),
            transcription_enabled  = data.get("transcription_enabled", False),
            live_notes_enabled     = data.get("live_notes_enabled", True),
            annotation_enabled     = data.get("annotation_enabled", False),
            waiting_room_enabled   = data.get("waiting_room_enabled", False),
            linked_milestone_ids   = data.get("linked_milestone_ids", []),
            linked_task_ids        = data.get("linked_task_ids", []),
            linked_crm_entity_ids  = data.get("linked_crm_entity_ids", []),
            agenda_doc_id          = data.get("agenda_doc_id"),
            external_guest_policy  = data.get("external_guest_policy"),
            metadata_json          = data.get("metadata_json", {}),
        )

        db.session.add(meeting)
        db.session.flush()   # generates meeting.id before audit
        _audit(actor_user_id, meeting, "meeting_created")
        db.session.commit()

        _emit_event("MeetingScheduled", {"meeting_id": meeting.id})
        logger.info("Meeting created: %s by user %s", meeting.id, actor_user_id)
        return meeting

    # ------------------------------------------------------------------ #
    # Read                                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_meeting(meeting_id: int) -> MeetMeeting:
        return _get_or_404(meeting_id)

    @staticmethod
    def list_meetings(
        startup_id:      Optional[int] = None,
        organization_id: Optional[int] = None,
        owner_user_id:   Optional[int] = None,
        status:          Optional[str] = None,
        limit:           int = 50,
        offset:          int = 0,
    ) -> list[MeetMeeting]:
        query = db.session.query(MeetMeeting)

        if startup_id is not None:
            query = query.filter(MeetMeeting.startup_id == startup_id)
        if organization_id is not None:
            query = query.filter(MeetMeeting.organization_id == organization_id)
        if owner_user_id is not None:
            query = query.filter(MeetMeeting.owner_user_id == owner_user_id)
        if status:
            try:
                query = query.filter(MeetMeeting.status == MeetingStatus(status))
            except ValueError:
                raise MeetServiceError(f"Invalid status filter: '{status}'.")

        return (
            query
            .order_by(MeetMeeting.scheduled_start_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    # ------------------------------------------------------------------ #
    # Update                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def update_meeting(actor_user_id: int, meeting_id: int, data: dict) -> MeetMeeting:
        """
        Partial update. `data` is the cleaned dict from validate_update_meeting_request().
        Cancelled/archived meetings cannot be updated.
        """
        meeting = _get_or_404(meeting_id)

        if meeting.status in {MeetingStatus.CANCELLED, MeetingStatus.ARCHIVED}:
            raise MeetStateError(
                f"Cannot update a meeting with status '{meeting.status.value}'."
            )

        # If rescheduling, re-check conflicts
        if "scheduled_start_at" in data:
            if check_schedule_conflict(
                meeting.owner_user_id,
                data["scheduled_start_at"],
                data["scheduled_end_at"],
                exclude_meeting_id=meeting.id,
            ):
                raise MeetConflictError(
                    "The updated time slot conflicts with another active meeting."
                )

        for field, value in data.items():
            setattr(meeting, field, value)

        meeting.updated_at = datetime.now(tz=timezone.utc)
        _audit(actor_user_id, meeting, "meeting_updated", {"fields": list(data.keys())})
        db.session.commit()

        _emit_event("MeetingUpdated", {"meeting_id": meeting.id, "fields": list(data.keys())})
        return meeting

    # ------------------------------------------------------------------ #
    # Cancel                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def cancel_meeting(actor_user_id: int, meeting_id: int, reason: Optional[str] = None) -> MeetMeeting:
        meeting = _get_or_404(meeting_id)
        _assert_transition(meeting, MeetingStatus.CANCELLED)

        meeting.status     = MeetingStatus.CANCELLED
        meeting.updated_at = datetime.now(tz=timezone.utc)
        _audit(actor_user_id, meeting, "meeting_cancelled", {"reason": reason})
        db.session.commit()

        _emit_event("MeetingCancelled", {"meeting_id": meeting.id, "reason": reason})
        logger.info("Meeting cancelled: %s by user %s", meeting.id, actor_user_id)
        return meeting

    # ------------------------------------------------------------------ #
    # Lifecycle transitions                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def transition_status(
        actor_user_id: int,
        meeting_id:    int,
        target_status: MeetingStatus,
    ) -> MeetMeeting:
        """Generic status transition with guard checks."""
        meeting = _get_or_404(meeting_id)
        _assert_transition(meeting, target_status)

        now = datetime.now(tz=timezone.utc)
        meeting.status = target_status

        if target_status == MeetingStatus.LIVE:
            meeting.actual_start_at = now
        elif target_status == MeetingStatus.ENDED:
            meeting.actual_end_at = now

        meeting.updated_at = now
        _audit(actor_user_id, meeting, f"status_changed_to_{target_status.value}")
        db.session.commit()

        event_map = {
            MeetingStatus.LIVE:    "MeetingStarted",
            MeetingStatus.ENDED:   "MeetingEnded",
            MeetingStatus.INDEXED: "MeetingIndexed",
        }
        if target_status in event_map:
            _emit_event(event_map[target_status], {"meeting_id": meeting.id})

        return meeting