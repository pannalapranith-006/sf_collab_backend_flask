from datetime import datetime
from app import db

class ErpTask(db.Model):
    __tablename__ = 'erp_tasks'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='to_do')
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    complexity = db.Column(db.String(20), nullable=True)             # 'small','medium','large','critical'
    requires_proof = db.Column(db.Boolean, default=False)
    quality_rating = db.Column(db.String(20), nullable=True)         # 'rejected','poor','accepted','good','excellent','exceptional'
    due_date = db.Column(db.Date, nullable=True)                     # deadline
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace = db.relationship('Workspace', backref='erp_tasks')
    assignee = db.relationship('User', foreign_keys=[assignee_id], backref='assigned_erp_tasks')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_erp_tasks')