from datetime import datetime, timezone
from sqlalchemy import ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.extensions import db


class DriveFilePermission(db.Model):
    __tablename__ = 'drive_file_permissions'

    id        = db.Column(db.Integer, primary_key=True)
    # FIX: original used ForeignKey('drive_files.file_id') but DriveFile PK is 'id'
    file_id   = db.Column(db.Integer, ForeignKey('drive_files.id', ondelete='CASCADE'), nullable=True)
    folder_id = db.Column(db.Integer, ForeignKey('drive_folders.id', ondelete='CASCADE'), nullable=True)
    user_id   = db.Column(db.Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    role = db.Column(db.String(20), default='viewer')

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint('file_id IS NOT NULL OR folder_id IS NOT NULL', name='ck_permission_target'),
        CheckConstraint("role IN ('viewer', 'editor', 'owner')", name='ck_permission_role'),
        Index('idx_permission_user', 'user_id'),
    )

    # Relationships
    file   = relationship('DriveFile',   back_populates='permissions', foreign_keys=[file_id])
    folder = relationship('DriveFolder', back_populates='permissions')
    user   = relationship('User', foreign_keys=[user_id])  # FIX: User has no drive_permissions_list

    def to_dict(self):
        return {
            'id':      self.id,
            'role':    self.role,
            'user_id': self.user_id,
        }