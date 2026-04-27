from datetime import datetime
from sqlalchemy import Enum as SAEnum
from app.extensions import db
import enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class MeetingType(enum.Enum):
    startup_team       = "startup_team"
    vision_review      = "vision_review"
    milestone_review   = "milestone_review"
    mentor_session     = "mentor_session"
    customer_call      = "customer_call"
    investor_call      = "investor_call"
    internal_org       = "internal_org"
    dispute_review     = "dispute_review"


class MeetingStatus(enum.Enum):
    scheduled  = "scheduled"
    live       = "live"
    ended      = "ended"
    processing = "processing"
    indexed    = "indexed"
    archived   = "archived"
    cancelled  = "cancelled"


class VisibilityScope(enum.Enum):
    private             = "private"
    invited_only        = "invited_only"
    startup_members     = "startup_members"
    organization        = "organization"
    mentor_visible      = "mentor_visible"
    advisor_visible     = "advisor_visible"


# ── Main Meeting Table ─────────────────────────────────────────────────────────

class MeetMeeting(db.Model):
    __tablename__ = "meet_meeting"

    id = db.Column(db.Integer, primary_key=True)

    # Core identity
    title        = db.Column(db.String(255), nullable=False)
    meeting_type = db.Column(SAEnum(MeetingType), nullable=False)
    status       = db.Column(SAEnum(MeetingStatus), default=MeetingStatus.scheduled, nullable=False)

    # Who owns it and what it belongs to
    owner_user_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    workspace_id    = db.Column(db.Integer, nullable=True)   # link to workspace when you have that table
    startup_id      = db.Column(db.Integer, db.ForeignKey("startups.id"), nullable=True)
    organization_id = db.Column(db.Integer, nullable=True)
    vision_id       = db.Column(db.Integer, nullable=True)

    # Linked work objects (stored as JSON arrays of IDs)
    linked_milestone_ids = db.Column(db.JSON, default=list)   # e.g. [1, 4, 7]
    linked_task_ids      = db.Column(db.JSON, default=list)

    # Scheduling
    scheduled_start_at = db.Column(db.DateTime, nullable=False)
    scheduled_end_at   = db.Column(db.DateTime, nullable=True)
    actual_start_at    = db.Column(db.DateTime, nullable=True)   # set when meeting goes live
    actual_end_at      = db.Column(db.DateTime, nullable=True)   # set when meeting ends
    timezone           = db.Column(db.String(50), default="UTC")

    # Permissions & features
    visibility_scope      = db.Column(SAEnum(VisibilityScope), default=VisibilityScope.invited_only)
    recording_enabled     = db.Column(db.Boolean, default=False)
    transcription_enabled = db.Column(db.Boolean, default=False)
    live_notes_enabled    = db.Column(db.Boolean, default=True)
    annotation_enabled    = db.Column(db.Boolean, default=False)

    # Output doc / file IDs (populated after the meeting ends)
    agenda_doc_id      = db.Column(db.String(255), nullable=True)
    live_notes_doc_id  = db.Column(db.String(255), nullable=True)
    summary_doc_id     = db.Column(db.String(255), nullable=True)
    transcript_file_id = db.Column(db.String(255), nullable=True)
    recording_file_id  = db.Column(db.String(255), nullable=True)

    # Metadata
    metadata_json = db.Column(db.JSON, default=dict)  # any extra data you want to attach
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    owner        = db.relationship("User", foreign_keys=[owner_user_id], backref="meetings_owned")
    participants = db.relationship("MeetParticipant", back_populates="meeting", cascade="all, delete-orphan")
    artifacts    = db.relationship("MeetArtifact",    back_populates="meeting", cascade="all, delete-orphan")

    # ── Helper methods ─────────────────────────────────────────────────────────

    def to_dict(self):
        return {
            "id":                    self.id,
            "title":                 self.title,
            "meeting_type":          self.meeting_type.value,
            "status":                self.status.value,
            "owner_user_id":         self.owner_user_id,
            "startup_id":            self.startup_id,
            "vision_id":             self.vision_id,
            "linked_milestone_ids":  self.linked_milestone_ids or [],
            "linked_task_ids":       self.linked_task_ids or [],
            "scheduled_start_at":    self.scheduled_start_at.isoformat() if self.scheduled_start_at else None,
            "scheduled_end_at":      self.scheduled_end_at.isoformat()   if self.scheduled_end_at   else None,
            "actual_start_at":       self.actual_start_at.isoformat()    if self.actual_start_at    else None,
            "actual_end_at":         self.actual_end_at.isoformat()      if self.actual_end_at      else None,
            "timezone":              self.timezone,
            "visibility_scope":      self.visibility_scope.value,
            "recording_enabled":     self.recording_enabled,
            "transcription_enabled": self.transcription_enabled,
            "live_notes_enabled":    self.live_notes_enabled,
            "annotation_enabled":    self.annotation_enabled,
            "summary_doc_id":        self.summary_doc_id,
            "transcript_file_id":    self.transcript_file_id,
            "recording_file_id":     self.recording_file_id,
            "created_at":            self.created_at.isoformat(),
        }