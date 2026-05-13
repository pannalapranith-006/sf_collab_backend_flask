"""
Model: MeetWorkspaceMemory
Path: app/models/meet_workspace_memory.py

Add to app/models/__init__.py:
    from .meet_workspace_memory import MeetWorkspaceMemory, MemoryType
"""

import enum
from datetime import datetime
from sqlalchemy import Enum as SAEnum
from app.extensions import db


class MemoryType(enum.Enum):
    episodic  = "episodic"    # what happened in a meeting
    decision  = "decision"    # a specific decision made
    workspace = "workspace"   # rolling workspace summary
    risk      = "risk"        # a risk or blocker identified


class MeetWorkspaceMemory(db.Model):
    """
    Stores AI-digestible memory records generated from meetings.
    The SF assistant reads these when answering questions about
    past meetings, decisions, and workspace state.
    """
    __tablename__ = "meet_workspace_memory"

    id           = db.Column(db.Integer, primary_key=True)
    meeting_id   = db.Column(db.Integer, db.ForeignKey("meet_meeting.id"), nullable=True)
    startup_id   = db.Column(db.Integer, nullable=True)
    workspace_id = db.Column(db.Integer, nullable=True)

    memory_type   = db.Column(SAEnum(MemoryType), nullable=False)
    title         = db.Column(db.String(500), nullable=False)
    content       = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.JSON, default=dict)

    # Retrieval helpers
    keywords  = db.Column(db.JSON, default=list)   # for keyword search
    importance= db.Column(db.Float, default=0.5)   # 0.0 to 1.0

    ai_generated = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    meeting = db.relationship("MeetMeeting", backref=db.backref("memory_records", lazy="dynamic"))

    def to_dict(self):
        return {
            "id":           self.id,
            "meeting_id":   self.meeting_id,
            "startup_id":   self.startup_id,
            "memory_type":  self.memory_type.value,
            "title":        self.title,
            "content":      self.content,
            "metadata":     self.metadata_json or {},
            "keywords":     self.keywords or [],
            "importance":   self.importance,
            "ai_generated": self.ai_generated,
            "created_at":   self.created_at.isoformat(),
        }