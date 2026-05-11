from datetime import datetime, timezone
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from app.extensions import db


class DriveFolder(db.Model):
    __tablename__ = 'drive_folders'

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(255), nullable=False)
    parent_id    = db.Column(db.Integer, ForeignKey('drive_folders.id', ondelete='CASCADE'), nullable=True)
    workspace_id = db.Column(db.Integer, ForeignKey('startups.id', ondelete='CASCADE'), nullable=False)
    created_by   = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # FIX: removed back_populates='drive_folders_list' — Startup has no such property
    # FIX: removed back_populates='created_folders' — User has no such property
    # FIX: removed back_populates='folder' — DriveFile uses parent_folder_id (no FK to drive_folders)
    # Using viewonly foreign_keys references instead to avoid mapper errors
    parent      = relationship('DriveFolder', remote_side=[id], backref='subfolders')
    startup     = relationship('Startup',  foreign_keys=[workspace_id])
    creator     = relationship('User',     foreign_keys=[created_by])
    files       = relationship('DriveFile', foreign_keys='DriveFile.parent_folder_id',
                               primaryjoin='DriveFolder.id == DriveFile.parent_folder_id',
                               cascade='all, delete-orphan')
    permissions = relationship('DriveFilePermission', back_populates='folder',
                               cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':           self.id,
            'name':         self.name,
            'parent_id':    self.parent_id,
            'workspace_id': self.workspace_id,
            'created_by':   self.created_by,
            'created_at':   self.created_at.isoformat(),
        }