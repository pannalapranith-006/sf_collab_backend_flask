from datetime import datetime
from app.extensions import db

class DriveAuditLog(db.Model):
    __tablename__ = 'drive_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("drive_files.file_id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)         # upload, delete, state_change, permission_change
    performed_by = db.Column(db.Integer, nullable=True)
    event_metadata = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "action": self.action,
            "performed_by": self.performed_by,
            "metadata": self.event_metadata,
            "created_at": self.created_at.isoformat(),
        }