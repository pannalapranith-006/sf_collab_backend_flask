from datetime import datetime

from sqlalchemy import Enum

from app.extensions import db


class ErpTask(db.Model):
    __tablename__ = 'erp_tasks'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    deadline = db.Column(db.DateTime, nullable=True, index=True)
    status = db.Column(Enum('todo', 'in_progress', 'done', name='erp_task_status_enum'), nullable=False, default='todo')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    workspace = db.relationship('Workspace', backref=db.backref('erp_tasks', lazy='dynamic', cascade='all, delete-orphan'))
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref=db.backref('assigned_erp_tasks', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by], backref=db.backref('created_erp_tasks', lazy='dynamic'))

    def _enum_to_value(self, value):
        return value.value if hasattr(value, 'value') else value

    def is_overdue(self):
        if self.deadline and self._enum_to_value(self.status) != 'done':
            return datetime.utcnow() > self.deadline
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'title': self.title,
            'description': self.description,
            'assigned_to': self.assigned_to,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'status': self._enum_to_value(self.status),
            'created_by': self.created_by,
            'is_overdue': self.is_overdue(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'assignee': {
                'id': self.assignee.id,
                'name': f'{self.assignee.first_name} {self.assignee.last_name}'.strip(),
                'email': self.assignee.email,
            } if self.assignee else None,
            'creator': {
                'id': self.creator.id,
                'name': f'{self.creator.first_name} {self.creator.last_name}'.strip(),
                'email': self.creator.email,
            } if self.creator else None,
        }
