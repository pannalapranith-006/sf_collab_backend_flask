from datetime import datetime
from app import db

class WorkspaceMembership(db.Model):
    __tablename__ = 'workspace_memberships'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='member')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (optional, but useful)
    workspace = db.relationship('Workspace', backref='memberships')
    user = db.relationship('User', backref='memberships')

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user'),
    )