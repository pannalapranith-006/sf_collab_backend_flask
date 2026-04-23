from datetime import datetime

from app.extensions import db


class ErpDocument(db.Model):
    __tablename__ = 'erp_documents'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    file_path = db.Column(db.String(500), nullable=False)
    folder = db.Column(db.String(255), nullable=False, default='general')
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(120))
    file_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    workspace = db.relationship('Workspace', backref=db.backref('erp_documents', lazy='dynamic', cascade='all, delete-orphan'))
    uploader = db.relationship('User', backref=db.backref('uploaded_erp_documents', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'uploaded_by': self.uploaded_by,
            'file_path': self.file_path,
            'folder': self.folder,
            'original_filename': self.original_filename,
            'stored_filename': self.stored_filename,
            'content_type': self.content_type,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'uploader': {
                'id': self.uploader.id,
                'name': f'{self.uploader.first_name} {self.uploader.last_name}'.strip(),
                'email': self.uploader.email,
            } if self.uploader else None,
        }
