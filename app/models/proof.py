from datetime import datetime
from app import db

class Proof(db.Model):
    __tablename__ = 'proofs'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('erp_tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    task = db.relationship('ErpTask', backref='proofs')
    user = db.relationship('User', foreign_keys=[user_id], backref='proofs_uploaded')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='proofs_reviewed')