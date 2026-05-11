from datetime import datetime
from app.extensions import db

class DriveFolder(db.Model):
    __tablename__ = 'drive_folders'

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(255), nullable=False)
    parent_id    = db.Column(db.Integer, db.ForeignKey('drive_folders.id', ondelete='CASCADE'), nullable=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('startups.id', ondelete='CASCADE'), nullable=False)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index('ix_folder_workspace', 'workspace_id'),
        db.Index('ix_folder_parent', 'parent_id'),
    )

    parent      = db.relationship('DriveFolder', remote_side=[id], backref='subfolders')
    workspace = db.relationship('Startup', back_populates='drive_folders_list', foreign_keys=[workspace_id])
    creator     = db.relationship('User', back_populates='created_folders')
    files = db.relationship('DriveFile', back_populates='folder', cascade='all, delete-orphan', foreign_keys='DriveFile.folder_id')
    permissions = db.relationship('DriveFilePermission', back_populates='folder', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':           self.id,
            'name':         self.name,
            'parent_id':    self.parent_id,
            'workspace_id': self.workspace_id,
            'created_by':   self.created_by,
            'created_at':   self.created_at.isoformat(),
        }