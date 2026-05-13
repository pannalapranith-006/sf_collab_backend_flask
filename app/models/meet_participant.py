from datetime import datetime
from sqlalchemy import Enum as SAEnum
from app.extensions import db
import enum


class ParticipantRole(enum.Enum):
    host      = "host"
    moderator = "moderator"
    member    = "member"
    guest     = "guest"     # external person — no workspace access


class AttendanceStatus(enum.Enum):
    invited  = "invited"
    accepted = "accepted"
    declined = "declined"
    attended = "attended"
    no_show  = "no_show"


class MeetParticipant(db.Model):
    __tablename__ = "meet_participant"

    id          = db.Column(db.Integer, primary_key=True)
    meeting_id  = db.Column(db.Integer, db.ForeignKey("meet_meeting.id"), nullable=False)

    # If it's a platform user, fill user_id.
    # If it's an external guest, fill guest_email instead.
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    guest_email = db.Column(db.String(255), nullable=True)   # external guests only

    role              = db.Column(SAEnum(ParticipantRole), default=ParticipantRole.member)
    attendance_status = db.Column(SAEnum(AttendanceStatus), default=AttendanceStatus.invited)

    joined_at          = db.Column(db.DateTime, nullable=True)   # set when they join the live room
    left_at            = db.Column(db.DateTime, nullable=True)   # set when they leave
    invited_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ──────────────────────────────────────────────────────────
    meeting     = db.relationship("MeetMeeting", back_populates="participants")
    user        = db.relationship("User", foreign_keys=[user_id],          backref="meeting_participations")
    invited_by  = db.relationship("User", foreign_keys=[invited_by_user_id])

    def to_dict(self):
        return {
            "id":                self.id,
            "meeting_id":        self.meeting_id,
            "user_id":           self.user_id,
            "guest_email":       self.guest_email,
            "role":              self.role.value,
            "attendance_status": self.attendance_status.value,
            "joined_at":         self.joined_at.isoformat() if self.joined_at else None,
            "left_at":           self.left_at.isoformat()   if self.left_at   else None,
        }