from datetime import date, datetime

from app.extensions import db


class DailyUpdate(db.Model):
    __tablename__ = 'daily_updates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True, default=date.today)
    today_work = db.Column(db.Text, nullable=False)
    next_plan = db.Column(db.Text, nullable=False)
    blockers = db.Column(db.Text)
    progress_rating = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('daily_updates', lazy='dynamic'))
    workspace = db.relationship('Workspace', backref=db.backref('daily_updates', lazy='dynamic', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'workspace_id', 'date', name='uq_daily_updates_user_workspace_date'),
    )

    def to_dict(self):
        user_name = None
        if self.user:
            user_name = f'{self.user.first_name} {self.user.last_name}'.strip()

        return {
            'id': self.id,
            'user_id': self.user_id,
            'workspace_id': self.workspace_id,
            'date': self.date.isoformat() if self.date else None,
            'today_work': self.today_work,
            'next_plan': self.next_plan,
            'blockers': self.blockers,
            'progress_rating': self.progress_rating,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user': {
                'id': self.user.id,
                'name': user_name,
                'email': self.user.email,
            } if self.user else None,
        }
