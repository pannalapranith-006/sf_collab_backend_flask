from datetime import datetime
from app.extensions import db


class MilestoneFile(db.Model):
    __tablename__ = 'milestone_files'

    id = db.Column(db.Integer, primary_key=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey('goal_milestones.id', ondelete='CASCADE'), nullable=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # File metadata
    original_name = db.Column(db.String(255), nullable=False)       # original filename the user uploaded
    stored_name   = db.Column(db.String(255), nullable=False)       # timestamped unique name on disk
    file_url      = db.Column(db.String(500), nullable=False)       # URL path served to frontend
    file_size     = db.Column(db.Integer, nullable=True)            # bytes
    file_type     = db.Column(db.String(100), nullable=True)        # MIME type e.g. application/pdf
    file_category = db.Column(db.String(50), default='document')   # 'document' | 'image' | 'other'

    # Proof flag — set to True to mark this file as official proof of completion
    is_proof = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    uploader = db.relationship('User', foreign_keys=[uploaded_by], lazy='joined')

    def to_dict(self):
        return {
            'id':            self.id,
            'milestone_id':  self.milestone_id,
            'original_name': self.original_name,
            'stored_name':   self.stored_name,
            'file_url':      self.file_url,
            'file_size':     self.file_size,
            'file_type':     self.file_type,
            'file_category': self.file_category,
            'is_proof':      self.is_proof,
            'created_at':    self.created_at.isoformat(),
            'uploaded_by': {
                'id':      self.uploader.id,
                'name':    f"{self.uploader.first_name} {self.uploader.last_name}",
                'avatar':  self.uploader.profile_picture,
            } if self.uploader else None,
        }