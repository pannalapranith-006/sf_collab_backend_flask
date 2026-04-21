from datetime import datetime
from app.extensions import db


class CollaborationRequest(db.Model):
    __tablename__ = "collaboration_requests"

    id = db.Column(db.Integer, primary_key=True)

    # 🔗 Vision Reference
    vision_id = db.Column(db.Integer, db.ForeignKey("visions.id"), nullable=False)
    vision = db.relationship("Vision", backref=db.backref("collaboration_requests", lazy=True))

    # 🔗 Users
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)   # Founder
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False) # Builder

    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_collaboration_requests")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_collaboration_requests")

    # 📌 Request Details
    role = db.Column(db.String(100), nullable=False)
    commitment = db.Column(db.String(100), nullable=True)  # e.g. "10 hrs/week"
    equity = db.Column(db.String(50), nullable=True)       # e.g. "2-5%"
    description = db.Column(db.Text, nullable=True)

    # 🔄 Status Flow
    # PENDING → ACCEPTED / DECLINED
    status = db.Column(db.String(50), default="PENDING")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "vision_id": self.vision_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "role": self.role,
            "commitment": self.commitment,
            "equity": self.equity,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "responded_at": self.responded_at.isoformat() if self.responded_at else None
        }