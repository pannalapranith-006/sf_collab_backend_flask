import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    String, Text, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.extensions import db


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MeetingType(str, enum.Enum):
    STARTUP_TEAM       = "startup_team"
    VISION_REVIEW      = "vision_review"
    MILESTONE_REVIEW   = "milestone_review"
    MENTOR_SESSION     = "mentor_session"
    CUSTOMER_CALL      = "customer_call"
    INVESTOR_CALL      = "investor_call"
    INTERNAL_ORG       = "internal_org"
    DISPUTE_REVIEW     = "dispute_review"


class MeetingStatus(str, enum.Enum):
    SCHEDULED   = "scheduled"
    PREPARING   = "preparing"
    LIVE        = "live"
    PAUSED      = "paused"
    ENDED       = "ended"
    PROCESSING  = "processing"
    INDEXED     = "indexed"
    ARCHIVED    = "archived"
    CANCELLED   = "cancelled"


class VisibilityScope(str, enum.Enum):
    PRIVATE              = "private"
    INVITED_ONLY         = "invited_only"
    STARTUP_MEMBERS      = "startup_members"
    ORGANIZATION_MEMBERS = "organization_members"
    MENTOR_VISIBLE       = "mentor_visible"
    ADVISOR_VISIBLE      = "advisor_visible"
    FINANCE_ONLY         = "finance_only"
    LEGAL_ONLY           = "legal_only"
    EXTERNAL_GUEST       = "external_guest"


class OwnerScopeType(str, enum.Enum):
    USER         = "user"
    STARTUP      = "startup"
    ORGANIZATION = "organization"
    VISION       = "vision"


class ParticipantRole(str, enum.Enum):
    HOST       = "host"
    MODERATOR  = "moderator"
    ATTENDEE   = "attendee"
    GUEST      = "guest"
    OBSERVER   = "observer"


class AttendanceStatus(str, enum.Enum):
    INVITED   = "invited"
    ACCEPTED  = "accepted"
    DECLINED  = "declined"
    JOINED    = "joined"
    NO_SHOW   = "no_show"


class ArtifactType(str, enum.Enum):
    RECORDING        = "recording"
    TRANSCRIPT       = "transcript"
    SUMMARY          = "summary"
    NOTES            = "notes"
    WHITEBOARD       = "whiteboard"
    ANNOTATION       = "annotation_export"
    SCREENSHOT       = "screenshot"
    DECK_COPY        = "deck_copy"
    DECISION_EXPORT  = "decision_export"
    ACTION_EXPORT    = "action_item_export"


class ActionItemStatus(str, enum.Enum):
    OPEN        = "open"
    IN_PROGRESS = "in_progress"
    DONE        = "done"
    CANCELLED   = "cancelled"


class DecisionStatus(str, enum.Enum):
    OPEN      = "open"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"


class AnnotationType(str, enum.Enum):
    FREEHAND      = "freehand"
    HIGHLIGHT     = "highlight"
    ARROW         = "arrow"
    BOX           = "box"
    STICKY_NOTE   = "sticky_note"
    TEXT_COMMENT  = "text_comment"
    PIN           = "pin"


# ---------------------------------------------------------------------------
# Core meeting table
# ---------------------------------------------------------------------------

class MeetMeeting(db.Model):
    __tablename__ = "meet_meeting"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    title        = Column(String(255), nullable=False)
    meeting_type = Column(Enum(MeetingType), nullable=False)

    # Ownership
    owner_user_id    = Column(UUID(as_uuid=True), nullable=False, index=True)
    owner_scope_type = Column(Enum(OwnerScopeType), nullable=False)
    owner_scope_id   = Column(UUID(as_uuid=True), nullable=False)

    # Workspace links
    workspace_id    = Column(UUID(as_uuid=True), nullable=True, index=True)
    startup_id      = Column(UUID(as_uuid=True), nullable=True, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    vision_id       = Column(UUID(as_uuid=True), nullable=True)

    # Linked entity ID arrays stored as JSON
    linked_milestone_ids   = Column(JSON, nullable=False, default=list)
    linked_task_ids        = Column(JSON, nullable=False, default=list)
    linked_crm_entity_ids  = Column(JSON, nullable=False, default=list)

    # Schedule
    scheduled_start_at = Column(DateTime(timezone=True), nullable=False)
    scheduled_end_at   = Column(DateTime(timezone=True), nullable=False)
    actual_start_at    = Column(DateTime(timezone=True), nullable=True)
    actual_end_at      = Column(DateTime(timezone=True), nullable=True)
    timezone           = Column(String(64), nullable=False, default="UTC")

    # State
    status           = Column(Enum(MeetingStatus), nullable=False, default=MeetingStatus.SCHEDULED)
    visibility_scope = Column(Enum(VisibilityScope), nullable=False, default=VisibilityScope.INVITED_ONLY)

    # Feature flags
    recording_enabled     = Column(Boolean, nullable=False, default=False)
    transcription_enabled = Column(Boolean, nullable=False, default=False)
    live_notes_enabled    = Column(Boolean, nullable=False, default=True)
    annotation_enabled    = Column(Boolean, nullable=False, default=False)
    waiting_room_enabled  = Column(Boolean, nullable=False, default=False)

    # Optional linked docs / files
    agenda_doc_id      = Column(UUID(as_uuid=True), nullable=True)
    live_notes_doc_id  = Column(UUID(as_uuid=True), nullable=True)
    summary_doc_id     = Column(UUID(as_uuid=True), nullable=True)
    transcript_file_id = Column(UUID(as_uuid=True), nullable=True)
    recording_file_id  = Column(UUID(as_uuid=True), nullable=True)
    whiteboard_file_id = Column(UUID(as_uuid=True), nullable=True)
    followup_meeting_id = Column(UUID(as_uuid=True), nullable=True)

    # Guest policy
    external_guest_policy = Column(String(64), nullable=True)

    # Extensible metadata
    metadata_json = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    participants = relationship("MeetParticipant", back_populates="meeting", cascade="all, delete-orphan")
    artifacts    = relationship("MeetArtifact",    back_populates="meeting", cascade="all, delete-orphan")
    decisions    = relationship("MeetDecision",    back_populates="meeting", cascade="all, delete-orphan")
    action_items = relationship("MeetActionItem",  back_populates="meeting", cascade="all, delete-orphan")
    annotations  = relationship("MeetAnnotation",  back_populates="meeting", cascade="all, delete-orphan")
    audit_logs   = relationship("MeetAuditLog",    back_populates="meeting", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_meet_meeting_startup_status", "startup_id", "status"),
        Index("ix_meet_meeting_owner_scope",    "owner_scope_type", "owner_scope_id"),
        Index("ix_meet_meeting_scheduled",      "scheduled_start_at"),
    )

    def __repr__(self):
        return f"<MeetMeeting id={self.id} title={self.title!r} status={self.status}>"

    def to_dict(self):
        return {
            "id":                    str(self.id),
            "title":                 self.title,
            "meeting_type":          self.meeting_type.value,
            "owner_user_id":         str(self.owner_user_id),
            "owner_scope_type":      self.owner_scope_type.value,
            "owner_scope_id":        str(self.owner_scope_id),
            "workspace_id":          str(self.workspace_id) if self.workspace_id else None,
            "startup_id":            str(self.startup_id) if self.startup_id else None,
            "organization_id":       str(self.organization_id) if self.organization_id else None,
            "vision_id":             str(self.vision_id) if self.vision_id else None,
            "linked_milestone_ids":  self.linked_milestone_ids,
            "linked_task_ids":       self.linked_task_ids,
            "linked_crm_entity_ids": self.linked_crm_entity_ids,
            "scheduled_start_at":    self.scheduled_start_at.isoformat() if self.scheduled_start_at else None,
            "scheduled_end_at":      self.scheduled_end_at.isoformat() if self.scheduled_end_at else None,
            "actual_start_at":       self.actual_start_at.isoformat() if self.actual_start_at else None,
            "actual_end_at":         self.actual_end_at.isoformat() if self.actual_end_at else None,
            "timezone":              self.timezone,
            "status":                self.status.value,
            "visibility_scope":      self.visibility_scope.value,
            "recording_enabled":     self.recording_enabled,
            "transcription_enabled": self.transcription_enabled,
            "live_notes_enabled":    self.live_notes_enabled,
            "annotation_enabled":    self.annotation_enabled,
            "waiting_room_enabled":  self.waiting_room_enabled,
            "agenda_doc_id":         str(self.agenda_doc_id) if self.agenda_doc_id else None,
            "live_notes_doc_id":     str(self.live_notes_doc_id) if self.live_notes_doc_id else None,
            "summary_doc_id":        str(self.summary_doc_id) if self.summary_doc_id else None,
            "transcript_file_id":    str(self.transcript_file_id) if self.transcript_file_id else None,
            "recording_file_id":     str(self.recording_file_id) if self.recording_file_id else None,
            "whiteboard_file_id":    str(self.whiteboard_file_id) if self.whiteboard_file_id else None,
            "followup_meeting_id":   str(self.followup_meeting_id) if self.followup_meeting_id else None,
            "external_guest_policy": self.external_guest_policy,
            "metadata_json":         self.metadata_json,
            "created_at":            self.created_at.isoformat(),
            "updated_at":            self.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------

class MeetParticipant(db.Model):
    __tablename__ = "meet_participant"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id        = Column(UUID(as_uuid=True), ForeignKey("meet_meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id           = Column(UUID(as_uuid=True), nullable=True, index=True)  # null for external guests
    guest_email       = Column(String(255), nullable=True)
    role_in_meeting   = Column(Enum(ParticipantRole), nullable=False, default=ParticipantRole.ATTENDEE)
    attendance_status = Column(Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.INVITED)
    joined_at         = Column(DateTime(timezone=True), nullable=True)
    left_at           = Column(DateTime(timezone=True), nullable=True)
    invited_by_user_id = Column(UUID(as_uuid=True), nullable=True)

    meeting = relationship("MeetMeeting", back_populates="participants")

    def __repr__(self):
        return f"<MeetParticipant meeting={self.meeting_id} user={self.user_id or self.guest_email}>"


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

class MeetArtifact(db.Model):
    __tablename__ = "meet_artifact"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id            = Column(UUID(as_uuid=True), ForeignKey("meet_meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type         = Column(Enum(ArtifactType), nullable=False)
    drive_file_id         = Column(UUID(as_uuid=True), nullable=True)
    source_timestamp_range = Column(JSON, nullable=True)   # {"start": seconds, "end": seconds}
    created_by_user_id    = Column(UUID(as_uuid=True), nullable=True)
    ai_generated          = Column(Boolean, nullable=False, default=False)
    created_at            = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    meeting = relationship("MeetMeeting", back_populates="artifacts")


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

class MeetDecision(db.Model):
    __tablename__ = "meet_decision"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id            = Column(UUID(as_uuid=True), ForeignKey("meet_meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    decision_statement    = Column(Text, nullable=False)
    rationale             = Column(Text, nullable=True)
    owner_ids_json        = Column(JSON, nullable=False, default=list)
    linked_milestone_ids_json = Column(JSON, nullable=False, default=list)
    linked_doc_ids_json   = Column(JSON, nullable=False, default=list)
    source_timestamp      = Column(String(32), nullable=True)   # e.g. "00:14:32"
    status                = Column(Enum(DecisionStatus), nullable=False, default=DecisionStatus.OPEN)
    created_at            = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    meeting = relationship("MeetMeeting", back_populates="decisions")


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------

class MeetActionItem(db.Model):
    __tablename__ = "meet_action_item"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id         = Column(UUID(as_uuid=True), ForeignKey("meet_meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    title              = Column(String(255), nullable=False)
    description        = Column(Text, nullable=True)
    owner_user_id      = Column(UUID(as_uuid=True), nullable=True)
    due_at             = Column(DateTime(timezone=True), nullable=True)
    priority           = Column(String(16), nullable=False, default="medium")   # low / medium / high
    linked_milestone_id = Column(UUID(as_uuid=True), nullable=True)
    linked_task_id     = Column(UUID(as_uuid=True), nullable=True)
    source_timestamp   = Column(String(32), nullable=True)
    status             = Column(Enum(ActionItemStatus), nullable=False, default=ActionItemStatus.OPEN)
    created_at         = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    meeting = relationship("MeetMeeting", back_populates="action_items")


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------

class MeetAnnotation(db.Model):
    __tablename__ = "meet_annotation"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id         = Column(UUID(as_uuid=True), ForeignKey("meet_meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    target_artifact_id = Column(UUID(as_uuid=True), nullable=True)
    annotation_type    = Column(Enum(AnnotationType), nullable=False)
    payload_json       = Column(JSON, nullable=False, default=dict)
    created_by_user_id = Column(UUID(as_uuid=True), nullable=False)
    created_at         = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    meeting = relationship("MeetMeeting", back_populates="annotations")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class MeetAuditLog(db.Model):
    __tablename__ = "meet_audit_log"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    meeting_id    = Column(UUID(as_uuid=True), ForeignKey("meet_meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    action        = Column(String(64), nullable=False)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at    = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    meeting = relationship("MeetMeeting", back_populates="audit_logs")
