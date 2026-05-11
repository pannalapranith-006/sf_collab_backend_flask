from datetime import datetime
from app.extensions import db

class DriveFile(db.Model):
    __tablename__ = 'drive_files'

    file_id      = db.Column(db.Integer, primary_key=True)
    filename     = db.Column(db.String(255), nullable=False)
    folder_id    = db.Column(db.Integer, db.ForeignKey('drive_folders.id', ondelete='SET NULL'), nullable=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('startups.id', ondelete='CASCADE'), nullable=False)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # File metadata
    extension    = db.Column(db.String(20))
    mime_type    = db.Column(db.String(100))
    size_bytes   = db.Column(db.BigInteger)
    checksum     = db.Column(db.String(64))           # SHA256
    storage_key  = db.Column(db.String(500))          # relative path in storage
    state        = db.Column(db.String(20), default='uploaded')

    # Ownership & visibility
    owner_scope_type = db.Column(db.String(20), default='startup')
    owner_scope_id   = db.Column(db.Integer)
    owner_user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    visibility_scope = db.Column(db.String(30), default='private')
    sensitivity_level = db.Column(db.String(20), default='internal')

    # Structure
    parent_folder_id  = db.Column(db.Integer, db.ForeignKey('drive_folders.id', ondelete='SET NULL'), nullable=True)
    startup_id        = db.Column(db.Integer, db.ForeignKey('startups.id'), nullable=True)
    organization_id   = db.Column(db.Integer, nullable=True)

    # AI Enrichment & Metadata
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
    freshness_score    = db.Column(db.Float, default=1.0)
    canonicality_score = db.Column(db.Float, default=1.0)
    vector_index_status = db.Column(db.String(20), default='pending')

    # Denormalised linked IDs (synced by relation routes)
    linked_vision_id             = db.Column(db.Integer, nullable=True)
    linked_milestone_ids         = db.Column(db.JSON, default=list)
    linked_task_ids              = db.Column(db.JSON, default=list)
    linked_meeting_id            = db.Column(db.Integer, nullable=True)
    linked_crm_entity_ids        = db.Column(db.JSON, default=list)
    linked_marketplace_listing_id= db.Column(db.Integer, nullable=True)
    linked_dispute_case_id       = db.Column(db.Integer, nullable=True)
    linked_wallet_transaction_id = db.Column(db.Integer, nullable=True)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint("owner_scope_type IN ('personal', 'startup', 'org')", name='ck_owner_scope_type'),
        db.Index('ix_drive_file_workspace', 'workspace_id'),
        db.Index('ix_drive_file_folder', 'folder_id'),
        db.Index('ix_drive_file_state', 'state'),
    )

    # Relationships
    folder = db.relationship('DriveFolder', back_populates='files', foreign_keys=[folder_id])
    workspace = db.relationship('Startup', back_populates='drive_files_list', foreign_keys=[workspace_id])
    creator = db.relationship('User', back_populates='created_drive_files', foreign_keys=[created_by])
    versions    = db.relationship('DriveFileVersion', back_populates='file', cascade='all, delete-orphan')
    permissions = db.relationship('DriveFilePermission', back_populates='file', cascade='all, delete-orphan')
    relations   = db.relationship('DriveFileRelation', back_populates='file', cascade='all, delete-orphan')

    def to_dict(self, include_ai=False):
        data = {
            'file_id':      self.file_id,
            'filename':     self.filename,
            'folder_id':    self.folder_id,
            'workspace_id': self.workspace_id,
            'created_by':   self.created_by,
            'extension':    self.extension,
            'mime_type':    self.mime_type,
            'size_bytes':   self.size_bytes,
            'checksum':     self.checksum,
            'storage_key':  self.storage_key,
            'state':        self.state,
            'owner_scope': {
                'type': self.owner_scope_type,
                'id':   self.owner_scope_id,
                'user_id': self.owner_user_id,
            },
            'visibility':   self.visibility_scope,
            'sensitivity':  self.sensitivity_level,
            'parent_folder_id': self.parent_folder_id,
            'startup_id':   self.startup_id,
            'organization_id': self.organization_id,
            'metadata': {
                'document_type':  self.document_type,
                'knowledge_type': self.knowledge_type,
                'tags':           self.tags_json,
            },
            'vector_status': self.vector_index_status,
            'uploaded_at':  self.uploaded_at.isoformat() if self.uploaded_at else None,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
            'updated_at':   self.updated_at.isoformat() if self.updated_at else None,
            'links': {
                'vision_id':               self.linked_vision_id,
                'milestone_ids':           self.linked_milestone_ids or [],
                'task_ids':                self.linked_task_ids or [],
                'meeting_id':              self.linked_meeting_id,
                'crm_entity_ids':          self.linked_crm_entity_ids or [],
                'marketplace_listing_id':  self.linked_marketplace_listing_id,
                'dispute_case_id':         self.linked_dispute_case_id,
                'wallet_transaction_id':   self.linked_wallet_transaction_id,
            },
        }
        if include_ai:
            data['ai'] = {
                'short_summary':    self.short_summary,
                'long_summary':     self.long_summary,
                'key_entities':     self.key_entities,
                'semantic_topics':  self.semantic_topics,
                'decision_markers': self.decision_markers,
                'risk_markers':     self.risk_markers,
                'freshness_score':  self.freshness_score,
                'canonicality_score': self.canonicality_score,
            }
        return data


class DriveFileVersion(db.Model):
    __tablename__ = 'drive_file_versions'

    id             = db.Column(db.Integer, primary_key=True)
    file_id        = db.Column(db.Integer, db.ForeignKey('drive_files.file_id', ondelete='CASCADE'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    file_path      = db.Column(db.String(500), nullable=False)
    file_url       = db.Column(db.String(500))
    created_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_canonical   = db.Column(db.Boolean, default=False)
    size_bytes     = db.Column(db.BigInteger)
    mime_type      = db.Column(db.String(100))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('file_id', 'version_number', name='uq_file_version_number'),
        db.Index('ix_version_file', 'file_id'),
    )

    file    = db.relationship('DriveFile', back_populates='versions', foreign_keys=[file_id])
    creator = db.relationship('User', back_populates='uploaded_file_versions')

    def to_dict(self):
        return {
            'id':             self.id,
            'file_id':        self.file_id,
            'version_number': self.version_number,
            'file_url':       self.file_url,
            'is_canonical':   self.is_canonical,
            'size_bytes':     self.size_bytes,
            'mime_type':      self.mime_type,
            'created_by':     self.created_by,
            'created_at':     self.created_at.isoformat(),
        }