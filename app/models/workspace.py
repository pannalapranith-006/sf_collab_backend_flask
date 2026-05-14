from datetime import datetime
from sqlalchemy.orm import relationship
from slugify import slugify

from app import db


class Workspace(db.Model):

    __tablename__ = "workspaces"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False)

    slug = db.Column(db.String(255), unique=True, nullable=False)

    owner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    owner = relationship(
        "User",
        back_populates="workspaces"
    )

    def __init__(self, name, owner_user_id):

        self.name = name
        self.slug = slugify(name)
        self.owner_user_id = owner_user_id