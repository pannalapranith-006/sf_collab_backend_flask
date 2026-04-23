from datetime import datetime, timedelta

from app.extensions import db


class ErpUserActivity(db.Model):
    __tablename__ = 'erp_user_activity'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True)
    last_login = db.Column(db.DateTime, nullable=True)
    last_activity = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_heartbeat = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    device_info = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('erp_activity_records', lazy='dynamic', cascade='all, delete-orphan'))
    workspace = db.relationship('Workspace', backref=db.backref('erp_activity_records', lazy='dynamic', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'workspace_id', name='uq_erp_user_activity_workspace_user'),
        db.Index('ix_erp_user_activity_workspace_last_activity', 'workspace_id', 'last_activity'),
    )

    @classmethod
    def get_or_create(cls, user_id, workspace_id):
        row = cls.query.filter_by(user_id=user_id, workspace_id=workspace_id).first()
        if row:
            return row

        row = cls(user_id=user_id, workspace_id=workspace_id)
        db.session.add(row)
        db.session.flush()
        return row

    def touch(self, request_obj=None):
        now = datetime.utcnow()
        self.last_activity = now
        self.last_heartbeat = now

        if self.last_login is None:
            self.last_login = now

        if request_obj:
            self.ip_address = request_obj.remote_addr
            self.device_info = request_obj.headers.get('User-Agent', '')

    def status(self):
        now = datetime.utcnow()
        delta = now - (self.last_activity or now)
        if delta < timedelta(minutes=5):
            return 'active'
        if delta < timedelta(minutes=30):
            return 'idle'
        if delta < timedelta(hours=24):
            return 'inactive'
        return 'dead'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'workspace_id': self.workspace_id,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'ip_address': self.ip_address,
            'device_info': self.device_info,
            'status': self.status(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
