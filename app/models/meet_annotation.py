from datetime import datetime
from sqlalchemy import Enum as SAEnum
from app.extensions import db
import enum


class AnnotationType(enum.Enum):
    freehand     = "freehand"     # drawn lines
    highlight    = "highlight"    # highlighted text/area
    arrow        = "arrow"
    box          = "box"
    sticky_note  = "sticky_note"
    text_comment = "text_comment"
    pin          = "pin"          # pin to a specific area


class MeetAnnotation(db.Model):
    """
    An annotation made on a shared file, screen snapshot, whiteboard, or slide
    during a meeting. The actual annotation data (coordinates, color, text) is
    stored in payload_json so it is flexible for any annotation tool.
    """
    __tablename__ = "meet_annotation"

    id         = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey("meet_meeting.id"), nullable=False)

    # Which artifact (file/screenshot) this annotation is on
    target_artifact_id = db.Column(db.Integer, db.ForeignKey("meet_artifact.id"), nullable=True)

    annotation_type = db.Column(SAEnum(AnnotationType), nullable=False)

    # All the spatial/content data: { x, y, width, height, color, text, page, etc. }
    payload_json = db.Column(db.JSON, default=dict)

    # When in the meeting (seconds from start)
    source_timestamp = db.Column(db.Integer, nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    meeting    = db.relationship("MeetMeeting",  backref=db.backref("annotations", lazy="dynamic"))
    artifact   = db.relationship("MeetArtifact", backref=db.backref("annotations", lazy="dynamic"))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])

    def to_dict(self):
        return {
            "id":                   self.id,
            "meeting_id":           self.meeting_id,
            "target_artifact_id":   self.target_artifact_id,
            "annotation_type":      self.annotation_type.value,
            "payload":              self.payload_json or {},
            "source_timestamp":     self.source_timestamp,
            "created_by_user_id":   self.created_by_user_id,
            "created_at":           self.created_at.isoformat(),
        }