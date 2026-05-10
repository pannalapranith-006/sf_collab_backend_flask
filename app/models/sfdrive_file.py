from datetime import datetime
from app.extensions import db

class SFFile(db.Model):
    __tablename__ = 'sf_files'

    id = db.Column(db.Integer, primary_key=True)

    workspace_id = db.Column(db.Integer, nullable=False, index=True)

    uploaded_by = db.Column(db.Integer, nullable=False)

    file_name = db.Column(db.String(255), nullable=False)

    file_path = db.Column(db.String(255), nullable=False)

    folder_id = db.Column(
        db.Integer,
        db.ForeignKey('sf_folders.id'),
        nullable=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    folder = db.relationship('Folder', backref='files')
    tags = db.relationship('Tag', backref='file', lazy=True)