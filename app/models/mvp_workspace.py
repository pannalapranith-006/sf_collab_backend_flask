from datetime import datetime
from app import db

class MVPWorkspace(db.Model):
    __tablename__ = "mvp_workspaces"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    owner_user_id = db.Column(db.Integer, nullable=False)

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_user_id": self.owner_user_id,
            "is_active": self.is_active,
            "created_at": self.created_at
        }