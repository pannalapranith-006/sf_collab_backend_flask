from datetime import datetime
from app.extensions import db


class DailyUpdate(db.Model):
    __tablename__ = 'daily_updates'

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    workspace_id    = db.Column(db.Integer, nullable=False, index=True)
    did_today       = db.Column(db.Text)
    will_do_next    = db.Column(db.Text)
    blockers        = db.Column(db.Text)
    progress_rating = db.Column(db.Integer)   # 1–5
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('daily_updates', lazy='dynamic'))

    def to_dict(self):
        from app.models.user import User
        user = User.query.get(self.user_id)
        return {
            'id':              self.id,
            'user_id':         self.user_id,
            'workspace_id':    self.workspace_id,
            'did_today':       self.did_today,
            'will_do_next':    self.will_do_next,
            'blockers':        self.blockers,
            'progress_rating': self.progress_rating,
            'created_at':      self.created_at.isoformat() if self.created_at else None,
            'user': {
                'id':   user.id,
                'name': f"{user.first_name} {user.last_name}",
            } if user else None,
        }


class Holiday(db.Model):
    __tablename__ = 'erp_holidays'

    id           = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)
    name         = db.Column(db.String(100), nullable=False)
    start_date   = db.Column(db.Date, nullable=False)
    end_date     = db.Column(db.Date, nullable=False)   # same as start_date for single-day

    def to_dict(self):
        return {
            'id':           self.id,
            'workspace_id': self.workspace_id,
            'name':         self.name,
            'start_date':   self.start_date.isoformat() if self.start_date else None,
            'end_date':     self.end_date.isoformat()   if self.end_date   else None,
        }


class UserUpdateStreak(db.Model):
    __tablename__ = 'user_update_streaks'

    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    workspace_id      = db.Column(db.Integer, nullable=False)
    missed_streak     = db.Column(db.Integer, default=0, nullable=False)
    last_submitted_at = db.Column(db.DateTime, nullable=True)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('update_streaks', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'workspace_id', name='uq_user_workspace_streak'),
    )