from datetime import datetime
from sqlalchemy import Enum as SAEnum
from app.extensions import db
import enum


class DecisionStatus(enum.Enum):
    open     = "open"       # decision made but not yet acted on
    actioned = "actioned"   # someone is executing on it
    closed   = "closed"     # resolved / no longer relevant
    reversed = "reversed"   # decision was later overturned


class MeetDecision(db.Model):
    """
    A structured decision captured during or after a meeting.
    Decisions are the most important output of any meeting —
    they become part of the workspace's long-term memory.
    """
    __tablename__ = "meet_decision"

    id         = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meet_meeting.id"), nullable=False)

    # The decision itself
    decision_statement = db.Column(db.Text, nullable=False)
    rationale          = db.Column(db.Text, nullable=True)   # why was this decided?

    # Who owns executing this decision (JSON list of user IDs)
    owner_ids_json = db.Column(db.JSON, default=list)   # e.g. [3, 7]

    # What work objects does this affect?
    linked_milestone_ids = db.Column(db.JSON, default=list)
    linked_doc_ids       = db.Column(db.JSON, default=list)

    # When in the meeting was this said? (seconds from meeting start, for transcript linking)
    source_timestamp = db.Column(db.Integer, nullable=True)

    status     = db.Column(SAEnum(DecisionStatus), default=DecisionStatus.open)
    ai_extracted = db.Column(db.Boolean, default=False)   # True if AI pulled this out automatically

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    meeting = db.relationship("MeetMeeting", backref=db.backref("decisions", lazy="dynamic"))

    def to_dict(self):
        return {
            "id":                    self.id,
            "meeting_id":            self.meeting_id,
            "decision_statement":    self.decision_statement,
            "rationale":             self.rationale,
            "owner_ids":             self.owner_ids_json or [],
            "linked_milestone_ids":  self.linked_milestone_ids or [],
            "linked_doc_ids":        self.linked_doc_ids or [],
            "source_timestamp":      self.source_timestamp,
            "status":                self.status.value,
            "ai_extracted":          self.ai_extracted,
            "created_at":            self.created_at.isoformat(),
        }