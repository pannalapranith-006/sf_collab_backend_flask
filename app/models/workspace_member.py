from datetime import datetime
from sqlalchemy import Enum
from app.extensions import db


class WorkspaceMember(db.Model):
    __tablename__ = "workspace_members"

    #  Primary Key
    id = db.Column(db.Integer, primary_key=True)

    #  Foreign Keys
    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    #  Role (admin / member)
    role = db.Column(
        Enum("admin", "member", name="workspace_role_enum"),
        default="member",
        nullable=False
    )

    #  Status (active / invited / suspended)
    status = db.Column(
        Enum("active", "invited", "suspended", name="workspace_status_enum"),
        default="active",
        nullable=False
    )

    #  Joined time
    joined_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    #  Prevent duplicate membership
    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id",
            "user_id",
            name="unique_workspace_user"
        ),
    )

    #  Relationships (IMPORTANT)
    user = db.relationship(
        "User",
        backref="workspace_memberships"
    )

    workspace = db.relationship(
        "Workspace",
        backref="members"
    )

    #  Convert to JSON (useful for APIs)
    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "role": self.role,
            "status": self.status,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None
        }


