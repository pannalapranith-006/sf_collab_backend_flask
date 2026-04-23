from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from slugify import slugify  # pip install python-slugify

db = SQLAlchemy()

class Workspace(db.Model):
    _tablename_ = "workspaces"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship back to User
    owner = relationship("User", back_populates="workspaces")

    def _init_(self, name, owner_user_id):
        self.name = name
        self.slug = slugify(name)  # generate URL-safe slug automatically
        self.owner_user_id = owner_user_id
