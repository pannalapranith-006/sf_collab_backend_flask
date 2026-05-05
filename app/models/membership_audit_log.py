from datetime import datetime
from app import db

class MembershipAuditLog(db.Model):
    __tablename__ = 'membership_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.JSON, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='membership_audit_logs')