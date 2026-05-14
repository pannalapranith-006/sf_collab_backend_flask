from datetime import datetime, date
from app import db

class ConsistencyPoint(db.Model):
    __tablename__ = 'consistency_points'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    log_date = db.Column(db.Date, default=date.today, nullable=False)
    type = db.Column(db.String(30), nullable=False)   # 'clock_in', 'daily_update', 'productive_day', 'perfect_week'
    points = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='consistency_points')
    workspace = db.relationship('Workspace', backref='consistency_points')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'workspace_id', 'log_date', 'type', name='uq_consistency_user_date_type'),
    )