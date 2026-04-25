from datetime import datetime, timezone
from sqlalchemy import ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import relationship
from app.extensions import db

class DriveFolder(db.Model):
    __tablename__ = 'drive_folders'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(255), nullable=False)
    parent_id   = db.Column(db.Integer, ForeignKey('drive_folders.id', ondelete='CASCADE'), nullable=True)
    workspace_id = db.Column(db.Integer, ForeignKey('startups.id',      ondelete='CASCADE'), nullable=False)
    created_by  = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    parent      = relationship('DriveFolder', remote_side=[id], backref='subfolders')
    startup     = relationship('Startup',     back_populates='drive_folders_list')
    creator     = relationship('User',        back_populates='created_folders')
    files       = relationship('DriveFile',   back_populates='folder', cascade='all, delete-orphan')
    permissions = relationship('DriveFilePermission', back_populates='folder', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':           self.id,
            'name':         self.name,
            'parent_id':    self.parent_id,
            'workspace_id': self.workspace_id,
            'created_by':   self.created_by,
            'created_at':   self.created_at.isoformat(),
        }

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
    owner_scope_type = db.Column(db.String(20), default='startup')  # personal | startup | org
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

class DriveFilePermission(db.Model):
    __tablename__ = 'drive_file_permissions'

    id        = db.Column(db.Integer, primary_key=True)
    file_id   = db.Column(db.Integer, ForeignKey('drive_files.file_id',  ondelete='CASCADE'), nullable=True)
    folder_id = db.Column(db.Integer, ForeignKey('drive_folders.id',    ondelete='CASCADE'), nullable=True)
    user_id   = db.Column(db.Integer, ForeignKey('users.id',            ondelete='CASCADE'), nullable=False)

    role       = db.Column(db.String(20), default='viewer')

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint('file_id IS NOT NULL OR folder_id IS NOT NULL', name='ck_permission_target'),
        Index('idx_permission_user', 'user_id'),
    )

    # Relationships
    file   = relationship('DriveFile',   back_populates='permissions')
    folder = relationship('DriveFolder', back_populates='permissions')
    user   = relationship('User',        back_populates='drive_permissions_list')

    def to_dict(self):
        return {
            'id':         self.id,
            'role':       self.role,
            'user_id':    self.user_id,
        }

class DriveFileRelation(db.Model):
    __tablename__ = 'drive_file_relations'

    id                  = db.Column(db.Integer, primary_key=True)
    file_id             = db.Column(db.Integer, ForeignKey('drive_files.file_id', ondelete='CASCADE'), nullable=False)
    related_entity_type = db.Column(db.String(50), nullable=False)
    related_entity_id   = db.Column(db.Integer,    nullable=False)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("related_entity_type IN ('task', 'milestone', 'meeting')", name='ck_relation_entity_type'),
    )

    # Relationships
    file = relationship('DriveFile', back_populates='relations')

    def to_dict(self):
        return {
            'id':                  self.id,
            'file_id':             self.file_id,
            'related_entity_type': self.related_entity_type,
            'related_entity_id':   self.related_entity_id,
            'created_at':          self.created_at.isoformat(),
        }
