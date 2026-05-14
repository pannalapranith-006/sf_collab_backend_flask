from datetime import datetime
from app import db

class MVPMembership(db.Model):
    __tablename__ = "mvp_memberships"

    id = db.Column(db.Integer, primary_key=True)

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("mvp_workspaces.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id = db.Column(db.Integer, nullable=False)

    role = db.Column(db.String(50), default="member")  # admin / member
    status = db.Column(db.String(50), default="active")

    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("workspace_id", "user_id", name="unique_mvp_membership"),
    )