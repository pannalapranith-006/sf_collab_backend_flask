from datetime import datetime
from app import db

class Warning(db.Model):
    __tablename__ = 'warnings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    reference_date = db.Column(db.Date, nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    is_resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    severity = db.Column(db.String(20), nullable=False)


    user = db.relationship('User', backref='warnings')
    workspace = db.relationship('Workspace', backref='warnings')