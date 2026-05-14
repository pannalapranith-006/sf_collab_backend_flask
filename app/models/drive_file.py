from datetime import datetime, timezone
from sqlalchemy import ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.extensions import db

class DriveFile(db.Model):
    __tablename__ = 'drive_files'

    file_id      = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(255), nullable=False)
    folder_id    = db.Column(db.Integer, ForeignKey('drive_folders.id', ondelete='SET NULL'), nullable=True)
    workspace_id = db.Column(db.Integer, ForeignKey('startups.id',      ondelete='CASCADE'), nullable=False)
    created_by   = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    
    mime_type    = db.Column(db.String(100))
    size_bytes   = db.Column(db.BigInteger)
    
    current_version_id = db.Column(db.Integer, ForeignKey('drive_file_versions.id', ondelete='SET NULL'), nullable=True)

    # AI Enrichment & Metadata
    owner_scope_type = db.Column(db.String(20), default='startup')
    owner_scope_id   = db.Column(db.Integer)
    visibility_scope = db.Column(db.String(20), default='team')
    
    document_type    = db.Column(db.String(50))
    knowledge_type   = db.Column(db.String(50))
    tags_json        = db.Column(db.JSON)

    # AI-Generated Content
    short_summary    = db.Column(db.Text)
    long_summary     = db.Column(db.Text)
    key_entities     = db.Column(db.JSON)
    semantic_topics  = db.Column(db.JSON)
    decision_markers = db.Column(db.JSON)
    risk_markers     = db.Column(db.JSON)

    # Analytics & Search
    freshness_score   = db.Column(db.Float, default=1.0)
    canonicality_score = db.Column(db.Float, default=1.0)
    vector_index_status = db.Column(db.String(20), default='pending')

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("owner_scope_type IN ('personal', 'startup', 'org')", name='ck_owner_scope_type'),
    )

    # Relationships
    folder      = relationship('DriveFolder', back_populates='files')
    workspace   = relationship('Startup',      back_populates='drive_files_list')
    creator     = relationship('User',         back_populates='created_drive_files')
    versions    = relationship('DriveFileVersion', back_populates='file', cascade='all, delete-orphan', foreign_keys='DriveFileVersion.file_id')
    current_version = relationship('DriveFileVersion', foreign_keys=[current_version_id], overlaps="versions")
    permissions = relationship('DriveFilePermission', back_populates='file', cascade='all, delete-orphan')
    relations   = relationship('DriveFileRelation',   back_populates='file', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'file_id':      self.file_id,
            'name':         self.name,
            'folder_id':    self.folder_id,
            'workspace_id': self.workspace_id,
            'created_by':   self.created_by,
            'mime_type':    self.mime_type,
            'size_bytes':   self.size_bytes,
            'owner_scope': {
                'type': self.owner_scope_type,
                'id':   self.owner_scope_id
            },
            'visibility':   self.visibility_scope,
            'metadata': {
                'document_type':  self.document_type,
                'knowledge_type': self.knowledge_type,
                'tags':           self.tags_json
            },
            'vector_status': self.vector_index_status,
            'created_at':    self.created_at.isoformat(),
        }

class DriveFileVersion(db.Model):
    __tablename__ = 'drive_file_versions'

    id             = db.Column(db.Integer, primary_key=True)
    file_id        = db.Column(db.Integer, ForeignKey('drive_files.file_id', ondelete='CASCADE'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    file_path      = db.Column(db.String(500), nullable=False)
    file_url       = db.Column(db.String(500))
    created_by     = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    
    is_canonical   = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint('file_id', 'version_number', name='uq_file_version_number'),
    )

    # Relationships
    file    = relationship('DriveFile', back_populates='versions', foreign_keys=[file_id], overlaps="current_version")
    creator = relationship('User',      back_populates='uploaded_file_versions')

    def to_dict(self):
        return {
            'id':             self.id,
            'file_id':        self.file_id,
            'version_number': self.version_number,
            'file_url':       self.file_url,
            'is_canonical':   self.is_canonical,
            'created_at':     self.created_at.isoformat(),
        }
from datetime import datetime
from app.extensions import db

class DriveFile(db.Model):
    __tablename__ = "drive_files"

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    filename = db.Column(db.String(512), nullable=False)
    extension = db.Column(db.String(32), nullable=True)
    mime_type = db.Column(db.String(128), nullable=True)
    size_bytes = db.Column(db.BigInteger, nullable=True)

    # storage_key is the object-storage path / key (e.g. S3 key)
    storage_key = db.Column(db.String(1024), nullable=True)
    checksum = db.Column(db.String(128), nullable=True)

    # Ownership / scope
    owner_scope_type = db.Column(db.String(32), nullable=False)
    owner_scope_id = db.Column(db.Integer, nullable=False)

    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    workspace_id = db.Column(db.Integer, nullable=True, index=True)
    startup_id = db.Column(db.Integer, nullable=True, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)

    # Folder placement – parent_folder_id without FK
    parent_folder_id = db.Column(db.Integer, nullable=True, index=True)

    # Visibility & sensitivity
    visibility_scope = db.Column(db.String(64), nullable=False, default="private")
    sensitivity_level = db.Column(db.String(32), nullable=False, default="internal")

    # Classification
    document_type = db.Column(db.String(64), nullable=True)
    knowledge_type = db.Column(db.String(64), nullable=True)

    # Lifecycle state
    state = db.Column(db.String(32), nullable=False, default="uploaded", index=True)

    # Versioning – removed DriveFileVersion references
    version_number = db.Column(db.Integer, nullable=False, default=1)

    # Tags
    tags_json = db.Column(db.JSON, nullable=True, default=list)

    # AI / knowledge fields
    summary_short = db.Column(db.Text, nullable=True)
    summary_long = db.Column(db.Text, nullable=True)

    key_entities_json = db.Column(db.JSON, nullable=True)
    semantic_topics_json = db.Column(db.JSON, nullable=True)
    decision_markers_json = db.Column(db.JSON, nullable=True)
    risk_markers_json = db.Column(db.JSON, nullable=True)

    freshness_score = db.Column(db.Float, nullable=True)
    canonicality_score = db.Column(db.Float, nullable=True)

    contradiction_group_id = db.Column(db.Integer, nullable=True)
    superseded_by_file_id = db.Column(db.Integer, db.ForeignKey("drive_files.id", ondelete="SET NULL"), nullable=True)

    embedding_status = db.Column(db.String(32), nullable=False, default="pending")
    indexing_status = db.Column(db.String(32), nullable=False, default="pending")

    # Optional relation IDs
    linked_vision_id = db.Column(db.Integer, nullable=True)
    linked_milestone_ids = db.Column(db.JSON, nullable=True, default=list)
    linked_task_ids = db.Column(db.JSON, nullable=True, default=list)
    linked_meeting_id = db.Column(db.Integer, nullable=True)
    linked_crm_entity_ids = db.Column(db.JSON, nullable=True, default=list)
    linked_marketplace_listing_id = db.Column(db.Integer, nullable=True)
    linked_dispute_case_id = db.Column(db.Integer, nullable=True)
    linked_wallet_transaction_id = db.Column(db.Integer, nullable=True)

    # Timestamps with Python-side defaults
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.utcnow(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow(), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    indexed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships – removed parent_folder and versions
    superseded_by = db.relationship("DriveFile", remote_side=[id], foreign_keys=[superseded_by_file_id])

    relations = db.relationship(
    "DriveFileRelation",
    back_populates="file",
    cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<DriveFile id={self.id} name={self.filename!r} state={self.state}>"

    def to_dict(self, include_ai=False):
        data = {
            "id": self.id,
            "filename": self.filename,
            "extension": self.extension,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "owner_scope_type": self.owner_scope_type,
            "owner_scope_id": self.owner_scope_id,
            "owner_user_id": self.owner_user_id,
            "workspace_id": self.workspace_id,
            "startup_id": self.startup_id,
            "organization_id": self.organization_id,
            "parent_folder_id": self.parent_folder_id,
            "visibility_scope": self.visibility_scope,
            "sensitivity_level": self.sensitivity_level,
            "document_type": self.document_type,
            "knowledge_type": self.knowledge_type,
            "state": self.state,
            "version_number": self.version_number,
            "tags_json": self.tags_json or [],
            "embedding_status": self.embedding_status,
            "indexing_status": self.indexing_status,
            "linked_vision_id": self.linked_vision_id,
            "linked_milestone_ids": self.linked_milestone_ids or [],
            "linked_task_ids": self.linked_task_ids or [],
            "linked_meeting_id": self.linked_meeting_id,
            "linked_crm_entity_ids": self.linked_crm_entity_ids or [],
            "linked_marketplace_listing_id": self.linked_marketplace_listing_id,
            "linked_dispute_case_id": self.linked_dispute_case_id,
            "linked_wallet_transaction_id": self.linked_wallet_transaction_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }

        if include_ai:
            data.update({
                "summary_short": self.summary_short,
                "summary_long": self.summary_long,
                "key_entities_json": self.key_entities_json,
                "semantic_topics_json": self.semantic_topics_json,
                "decision_markers_json": self.decision_markers_json,
                "risk_markers_json": self.risk_markers_json,
                "freshness_score": self.freshness_score,
                "canonicality_score": self.canonicality_score,
                "contradiction_group_id": self.contradiction_group_id,
                "superseded_by_file_id": self.superseded_by_file_id,
            })

        return data
