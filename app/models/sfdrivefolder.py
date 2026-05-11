from datetime import datetime
from app.extensions import db

class Folder(db.Model):
    __tablename__ = 'sf_folders'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False)

    workspace_id = db.Column(db.Integer, nullable=False, index=True)

    parent_id = db.Column(
        db.Integer,
        db.ForeignKey('sf_folders.id'),
        nullable=True
    )

    created_by = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    children = db.relationship('Folder')