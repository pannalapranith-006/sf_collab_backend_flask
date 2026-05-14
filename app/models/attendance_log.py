from datetime import datetime, date
from app import db

class AttendanceLog(db.Model):
    __tablename__ = 'attendance_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    log_date = db.Column(db.Date, default=date.today)
    clock_in = db.Column(db.DateTime, nullable=True)
    clock_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=True)   # 'present', 'late', 'absent'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='attendance_logs')
    workspace = db.relationship('Workspace', backref='attendance_logs')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'workspace_id', 'log_date', name='uq_user_workspace_date'),
    )