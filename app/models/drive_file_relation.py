from datetime import datetime
from app.extensions import db

RELATION_TYPES = ("milestone", "task", "meeting", "crm_entity", "marketplace_listing",
                  "dispute_case", "wallet_transaction", "vision", "startup", "organization")
ENTITY_TYPES = RELATION_TYPES

class DriveFileRelation(db.Model):
    __tablename__ = 'drive_file_relations'

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey("drive_files.file_id", ondelete="CASCADE"),
                        nullable=False, index=True)
    relation_type = db.Column(db.String(64), nullable=False)
    related_entity_id = db.Column(db.Integer, nullable=False)
    related_entity_type = db.Column(db.String(64), nullable=False)
    related_entity_label = db.Column(db.String(512), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                                   nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("file_id", "relation_type", "related_entity_id",
                            name="uq_file_relation_type_entity"),
        db.Index("ix_file_relation_entity", "related_entity_type", "related_entity_id"),
    )

    file = db.relationship("DriveFile", back_populates="relations", foreign_keys=[file_id])

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "relation_type": self.relation_type,
            "related_entity_id": self.related_entity_id,
            "related_entity_type": self.related_entity_type,
            "related_entity_label": self.related_entity_label,
            "created_by_user_id": self.created_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }