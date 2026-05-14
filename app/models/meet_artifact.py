from datetime import datetime
from sqlalchemy import Enum as SAEnum
from app.extensions import db
import enum


class ArtifactType(enum.Enum):
    recording   = "recording"    # video file
    transcript  = "transcript"   # raw or cleaned text
    summary     = "summary"      # AI-generated summary doc
    notes       = "notes"        # live notes doc
    whiteboard  = "whiteboard"   # whiteboard export
    annotation  = "annotation"   # annotation bundle
    screenshot  = "screenshot"


class MeetArtifact(db.Model):
    """
    Represents a file produced from a meeting and saved to SF Drive.
    Every important meeting output (recording, transcript, summary) becomes
    one row here — linked back to the meeting and optionally to a milestone.
    """
    __tablename__ = "meet_artifact"

    id          = db.Column(db.Integer, primary_key=True)
    meeting_id  = db.Column(db.Integer, db.ForeignKey("meet_meeting.id"), nullable=False)

    artifact_type = db.Column(SAEnum(ArtifactType), nullable=False)

    # Where it lives in SF Drive — this is the Drive file's ID/path
    drive_file_id = db.Column(db.String(500), nullable=True)

    # What work objects it links to
    startup_id    = db.Column(db.Integer, nullable=True)
    milestone_id  = db.Column(db.Integer, nullable=True)

    # Metadata
    ai_generated  = db.Column(db.Boolean, default=False)   # True for summaries, extracted notes
    file_size_mb  = db.Column(db.Float, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    meeting     = db.relationship("MeetMeeting", back_populates="artifacts")
    created_by  = db.relationship("User", foreign_keys=[created_by_user_id])

    def to_dict(self):
        return {
            "id":                  self.id,
            "meeting_id":          self.meeting_id,
            "artifact_type":       self.artifact_type.value,
            "drive_file_id":       self.drive_file_id,
            "startup_id":          self.startup_id,
            "milestone_id":        self.milestone_id,
            "ai_generated":        self.ai_generated,
            "file_size_mb":        self.file_size_mb,
            "created_by_user_id":  self.created_by_user_id,
            "created_at":          self.created_at.isoformat(),
        }