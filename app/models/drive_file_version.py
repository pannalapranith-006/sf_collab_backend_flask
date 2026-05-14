#from app.models.drive_file import DriveFile
from datetime import datetime
from app.extensions import db

class DriveFileVersion(db.Model):
    __tablename__ = "drive_file_version"

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey("drive_file.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    storage_key = db.Column(db.String(255), nullable=False)
    changed_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    changed_summary = db.Column(db.String(500))
    checksum = db.Column(db.String(255))
    preview_status = db.Column(db.String(50), default="pending")
    indexing_status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow,nullable =False)
    indexed_at = db.Column(db.DateTime)
    
    #Unique constraint to ensure no duplicate version numbers for the same file
    __table_args__ = (
    db.UniqueConstraint("file_id", "version_number"),
)
    
    # relationships
    file = db.relationship("DriveFile", backref="versions")
    user = db.relationship("User")


