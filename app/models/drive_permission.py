from datetime import datetime
from app.extensions import db

class DriveFilePermission(db.Model):
    __tablename__ = 'drive_file_permissions'

    id        = db.Column(db.Integer, primary_key=True)
    file_id   = db.Column(db.Integer, db.ForeignKey('drive_files.file_id',  ondelete='CASCADE'), nullable=True)
    folder_id = db.Column(db.Integer, db.ForeignKey('drive_folders.id',    ondelete='CASCADE'), nullable=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id',            ondelete='CASCADE'), nullable=False)

    role       = db.Column(db.String(20), default='viewer')  # viewer, editor, owner

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint('file_id IS NOT NULL OR folder_id IS NOT NULL', name='ck_permission_target'),
        db.CheckConstraint("role IN ('viewer', 'editor', 'owner')", name='ck_permission_role'),
        db.Index('idx_permission_user', 'user_id'),
        db.Index('idx_permission_file', 'file_id'),
        db.Index('idx_permission_folder', 'folder_id'),
    )

    file   = db.relationship('DriveFile',   back_populates='permissions')
    folder = db.relationship('DriveFolder', back_populates='permissions')
    user   = db.relationship('User',        back_populates='drive_permissions_list')

    def to_dict(self):
        return {
            'id':         self.id,
            'role':       self.role,
            'user_id':    self.user_id,
            'file_id':    self.file_id,
            'folder_id':  self.folder_id,
        }