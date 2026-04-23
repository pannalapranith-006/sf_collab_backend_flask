from datetime import datetime

from sqlalchemy import Enum

from app.extensions import db


class ErpAlert(db.Model):
    __tablename__ = 'erp_alerts'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    type = db.Column(
        Enum('missing_update', 'late_attendance', 'task_overdue', 'inactive_user', name='erp_alert_type_enum'),
        nullable=False,
        index=True,
    )
    priority = db.Column(
        Enum('low', 'medium', 'high', name='erp_alert_priority_enum'),
        nullable=False,
        default='medium',
    )
    message = db.Column(db.Text, nullable=False)
    resolved = db.Column(db.Boolean, nullable=False, default=False, index=True)
    reference_id = db.Column(db.Integer, nullable=True)
    source_date = db.Column(db.Date, nullable=False, index=True)
    dedupe_key = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)

    workspace = db.relationship('Workspace', backref=db.backref('erp_alerts', lazy='dynamic', cascade='all, delete-orphan'))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('erp_alerts', lazy='dynamic'))
    resolver = db.relationship('User', foreign_keys=[resolved_by])

    __table_args__ = (
        db.Index('ix_erp_alert_lookup', 'workspace_id', 'type', 'source_date', 'resolved'),
    )

    def _enum_to_value(self, value):
        return value.value if hasattr(value, 'value') else value

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'user_id': self.user_id,
            'type': self._enum_to_value(self.type),
            'priority': self._enum_to_value(self.priority),
            'message': self.message,
            'resolved': self.resolved,
            'reference_id': self.reference_id,
            'source_date': self.source_date.isoformat() if self.source_date else None,
            'dedupe_key': self.dedupe_key,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
            'resolution_note': self.resolution_note,
            'user': {
                'id': self.user.id,
                'name': f'{self.user.first_name} {self.user.last_name}'.strip(),
                'email': self.user.email,
            } if self.user else None,
        }
