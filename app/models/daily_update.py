from datetime import datetime, date
from app import db

class DailyUpdate(db.Model):
    __tablename__ = 'daily_updates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    log_date = db.Column(db.Date, default=date.today)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='daily_updates')
    workspace = db.relationship('Workspace', backref='daily_updates')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'workspace_id', 'log_date', name='uq_daily_update_user_workspace_date'),
    )