from datetime import datetime
from app.extensions import db


class MeetAuditLog(db.Model):
    """
    Immutable audit log of every significant action taken in a meeting.
    Never update or delete rows here — only insert.

    Examples of actions logged:
        meeting_created, meeting_started, meeting_ended, meeting_cancelled,
        participant_invited, participant_joined, participant_left,
        recording_started, recording_stopped,
        artifact_saved, decision_created, action_item_created,
        annotation_created, notes_saved, status_changed
    """
    __tablename__ = "meet_audit_log"

    id             = db.Column(db.Integer, primary_key=True)
    meeting_id     = db.Column(db.Integer, db.ForeignKey("meet_meeting.id"), nullable=False)
    actor_user_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # None = system action

    action         = db.Column(db.String(100), nullable=False)   # e.g. "meeting_started"
    metadata_json  = db.Column(db.JSON, default=dict)            # any extra context

    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    meeting = db.relationship("MeetMeeting", backref=db.backref("audit_logs", lazy="dynamic"))
    actor   = db.relationship("User", foreign_keys=[actor_user_id])

    def to_dict(self):
        return {
            "id":            self.id,
            "meeting_id":    self.meeting_id,
            "actor_user_id": self.actor_user_id,
            "action":        self.action,
            "metadata":      self.metadata_json or {},
            "created_at":    self.created_at.isoformat(),
        }


# ── Convenience function ───────────────────────────────────────────────────────

def log_meeting_action(meeting_id, action, actor_user_id=None, metadata=None):
    """
    Call this anywhere to write an audit log entry.

    Usage:
        log_meeting_action(meeting.id, "meeting_started", actor_user_id=current_user_id)
        log_meeting_action(meeting.id, "artifact_saved",  metadata={"artifact_type": "recording"})
    """
    entry = MeetAuditLog(
        meeting_id    = meeting_id,
        actor_user_id = actor_user_id,
        action        = action,
        metadata_json = metadata or {},
    )
    db.session.add(entry)
    # NOTE: caller is responsible for db.session.commit()