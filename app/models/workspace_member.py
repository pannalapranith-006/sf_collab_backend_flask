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


    __tablename__ = 'workspace_members'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(Enum('admin', 'member', name='workspace_role_enum'), nullable=False, default='member')
    status = db.Column(Enum('active', 'invited', 'suspended', name='workspace_status_enum'), nullable=False, default='active')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_members_workspace_user'),
    )

    user = db.relationship('User', backref=db.backref('workspace_memberships', lazy='dynamic'))
    workspace = db.relationship('Workspace', backref=db.backref('members', lazy='dynamic', cascade='all, delete-orphan'))

    def _enum_to_value(self, value):
        return value.value if hasattr(value, 'value') else value

    def to_dict(self, include_user=False):
        data = {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'user_id': self.user_id,
            'role': self._enum_to_value(self.role),
            'status': self._enum_to_value(self.status),
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_user and self.user:
            data['user'] = {
                'id': self.user.id,
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
                'email': self.user.email,
                'profile_picture': self.user.profile_picture,
            }

        return data
