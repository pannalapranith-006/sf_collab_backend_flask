from datetime import datetime
from app.extensions import db

class JobStatus(db.Model):
    __tablename__ = 'job_status'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_name = db.Column(db.String(100), nullable=False)
    run_id = db.Column(db.String(64), nullable=False, unique=True)  # idempotency key
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, default='')
    payload = db.Column(db.JSON, default={})    # extra context (e.g., date range)
    run_count = db.Column(db.Integer, default=0) # number of attempts
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def mark_started(self):
        self.status = 'running'
        self.started_at = datetime.utcnow()
        if self.run_count is None:
            self.run_count = 0
        self.run_count += 1

    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = datetime.utcnow()

    def mark_failed(self, error_msg):
        self.status = 'failed'
        self.error_message = error_msg
        self.completed_at = datetime.utcnow()