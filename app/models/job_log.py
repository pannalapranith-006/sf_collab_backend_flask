from datetime import datetime
from app import db

class JobLog(db.Model):
    __tablename__ = 'job_logs'

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(100), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    status = db.Column(db.String(20), default='started')   # started, completed, failed
    details = db.Column(db.JSON, default={})
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    workspace = db.relationship('Workspace', backref='job_logs')