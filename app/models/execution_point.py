from datetime import datetime
from app import db

class ExecutionPoint(db.Model):
    __tablename__ = 'execution_points'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('erp_tasks.id'), nullable=False)
    base_points = db.Column(db.Float, nullable=False)
    quality_multiplier = db.Column(db.Float, default=1.0)
    proof_multiplier = db.Column(db.Float, default=1.0)
    deadline_multiplier = db.Column(db.Float, default=1.0)
    final_points = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')    # 'pending', 'approved', 'rejected', 'held'
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)        # NEW
    approval_comment = db.Column(db.Text, nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    workspace = db.relationship('Workspace', backref='execution_points')
    user = db.relationship('User', foreign_keys=[user_id], backref='execution_points')
    task = db.relationship('ErpTask', backref='execution_points')
    approver = db.relationship('User', foreign_keys=[approved_by])
    
    __table_args__ = (
        db.UniqueConstraint('task_id', 'user_id', name='uq_execution_point_task_user'),
    )