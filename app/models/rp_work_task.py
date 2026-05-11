from datetime import datetime
from app.extensions import db

class WorkTask(db.Model):
    __tablename__ = 'work_tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(50), nullable=False, default='not_started')

    created_by = db.Column(db.Integer, nullable=False)
    assignee_id = db.Column(db.Integer, nullable=True)
    approver_id = db.Column(db.Integer, nullable=True)

    proof_required = db.Column(db.Boolean, default=False)
    proof_description = db.Column(db.Text, default='')
    proof_url = db.Column(db.String(512), nullable=True)

    milestone_id = db.Column(db.Integer, db.ForeignKey('work_milestones.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    milestone = db.relationship('WorkMilestone', backref='tasks')

    STATUSES = ('not_started', 'in_progress', 'submitted', 'approved', 'rejected')
    VALID_TRANSITIONS = {
        'not_started': ['in_progress'],
        'in_progress': ['submitted', 'not_started'],
        'submitted': ['approved', 'rejected'],
        'approved': [],
        'rejected': ['in_progress']
    }

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])