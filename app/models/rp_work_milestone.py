from datetime import datetime
from app.extensions import db

class WorkMilestone(db.Model):
    __tablename__ = 'work_milestones'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(50), nullable=False, default='active')
    target_date = db.Column(db.Date, nullable=True)
    completion_criteria = db.Column(db.Text, default='')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)