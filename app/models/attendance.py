from datetime import datetime, time
from app.extensions import db


class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    clock_in_time = db.Column(db.DateTime)
    clock_out_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('attendance_records', lazy='dynamic'))
    workspace = db.relationship('Workspace', backref=db.backref('attendance_records', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', 'workspace_id', name='uq_attendance_user_date_workspace'),
    )

    def calculate_status(self, late_threshold_hour=9, late_threshold_minute=0):
        if not self.clock_in_time:
            self.status = 'absent'
            return
        cutoff = time(late_threshold_hour, late_threshold_minute)
        self.status = 'late' if self.clock_in_time.time() > cutoff else 'present'

    def get_duration_hours(self):
        if self.clock_in_time and self.clock_out_time:
            delta = self.clock_out_time - self.clock_in_time
            return round(delta.total_seconds() / 3600, 2)
        return 0

    def to_dict(self):
        user_name = None
        if self.user:
            user_name = f'{self.user.first_name} {self.user.last_name}'.strip()

        return {
            'id': self.id,
            'user_id': self.user_id,
            'workspace_id': self.workspace_id,
            'date': self.date.isoformat() if self.date else None,
            'clock_in_time': self.clock_in_time.isoformat() if self.clock_in_time else None,
            'clock_out_time': self.clock_out_time.isoformat() if self.clock_out_time else None,
            'status': self.status,
            'notes': self.notes,
            'duration_hours': self.get_duration_hours(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user': {
                'id': self.user.id,
                'name': user_name,
                'email': self.user.email,
            } if self.user else None,
        }
