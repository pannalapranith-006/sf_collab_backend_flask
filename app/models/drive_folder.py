from datetime import datetime, timezone
from sqlalchemy import ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.extensions import db

class DriveFolder(db.Model):
    __tablename__ = 'drive_folders'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(255), nullable=False)
    parent_id   = db.Column(db.Integer, ForeignKey('drive_folders.id', ondelete='CASCADE'), nullable=True)
    workspace_id = db.Column(db.Integer, ForeignKey('startups.id',      ondelete='CASCADE'), nullable=False)
    created_by  = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    parent      = relationship('DriveFolder', remote_side=[id], backref='subfolders')
    startup     = relationship('Startup',     back_populates='drive_folders_list')
    creator     = relationship('User',        back_populates='created_folders')
    files       = relationship('DriveFile',   back_populates='folder', cascade='all, delete-orphan')
    permissions = relationship('DriveFilePermission', back_populates='folder', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':           self.id,
            'name':         self.name,
            'parent_id':    self.parent_id,
            'workspace_id': self.workspace_id,
            'created_by':   self.created_by,
            'created_at':   self.created_at.isoformat(),
        }
