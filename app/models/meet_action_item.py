from datetime import datetime
from sqlalchemy import Enum as SAEnum
from app.extensions import db
import enum


class ActionItemPriority(enum.Enum):
    low    = "low"
    medium = "medium"
    high   = "high"
    urgent = "urgent"


class ActionItemStatus(enum.Enum):
    open        = "open"
    in_progress = "in_progress"
    done        = "done"
    cancelled   = "cancelled"


class MeetActionItem(db.Model):
    """
    A task / action created from a meeting conversation.
    These flow directly into the SF task system — each action item can
    optionally be linked to an existing task once it's created there.
    """
    __tablename__ = "meet_action_item"

    id         = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meet_meeting.id"), nullable=False)

    title       = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Who is responsible
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Deadline
    due_at = db.Column(db.DateTime, nullable=True)

    priority = db.Column(SAEnum(ActionItemPriority), default=ActionItemPriority.medium)
    status   = db.Column(SAEnum(ActionItemStatus),   default=ActionItemStatus.open)

    # Links to other SF objects
    linked_milestone_id = db.Column(db.Integer, nullable=True)
    linked_task_id      = db.Column(db.Integer, nullable=True)  # set once a real Task is created

    # Where in the meeting this came from (seconds from start)
    source_timestamp = db.Column(db.Integer, nullable=True)

    ai_extracted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    meeting = db.relationship("MeetMeeting", backref=db.backref("action_items", lazy="dynamic"))
    owner   = db.relationship("User", foreign_keys=[owner_user_id], backref="meeting_action_items")

    def to_dict(self):
        return {
            "id":                   self.id,
            "meeting_id":           self.meeting_id,
            "title":                self.title,
            "description":          self.description,
            "owner_user_id":        self.owner_user_id,
            "due_at":               self.due_at.isoformat() if self.due_at else None,
            "priority":             self.priority.value,
            "status":               self.status.value,
            "linked_milestone_id":  self.linked_milestone_id,
            "linked_task_id":       self.linked_task_id,
            "source_timestamp":     self.source_timestamp,
            "ai_extracted":         self.ai_extracted,
            "created_at":           self.created_at.isoformat(),
        }