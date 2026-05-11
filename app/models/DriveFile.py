"""
app/models/DriveFile.py
SF Drive — File storage model with tagging, knowledge typing, and AI summary fields.
"""
import json
from datetime import datetime
from app.extensions import db


class DriveFile(db.Model):
    __tablename__ = 'drive_files'

    # ── Core identity ─────────────────────────────────────────────────────────
    id              = db.Column(db.Integer, primary_key=True)
    filename        = db.Column(db.String(255), nullable=False)
    original_name   = db.Column(db.String(255), nullable=False)
    extension       = db.Column(db.String(20),  nullable=True)
    mime_type       = db.Column(db.String(100), nullable=True)
    size_bytes      = db.Column(db.Integer,     nullable=True)
    file_url        = db.Column(db.String(500), nullable=False)   # served path

    # ── Ownership & scope ─────────────────────────────────────────────────────
    owner_user_id   = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    startup_id      = db.Column(db.Integer, nullable=True)        # FK to startups if present
    organization_id = db.Column(db.Integer, nullable=True)
    visibility_scope = db.Column(db.String(50), default='private')
    # private | startup-members | organization-members | public

    # ── Knowledge classification ──────────────────────────────────────────────
    # knowledge_type: roadmap | milestone-proof | meeting-transcript | meeting-notes |
    #                 research | pitch | contract | invoice | design | spec | gtm |
    #                 architecture | product | legal | other
    knowledge_type  = db.Column(db.String(50), default='other')

    # file_state: uploaded | processing | indexed | active | archived
    file_state      = db.Column(db.String(30), default='uploaded')

    # ── Tags ─────────────────────────────────────────────────────────────────
    # Stored as JSON array: ["roadmap", "q2", "mvp"]
    tags_json       = db.Column(db.Text, default='[]')

    # ── Linked objects ────────────────────────────────────────────────────────
    linked_milestone_id = db.Column(db.Integer, nullable=True)
    linked_meeting_id   = db.Column(db.Integer, nullable=True)
    linked_task_id      = db.Column(db.Integer, nullable=True)

    # ── AI-generated summaries ────────────────────────────────────────────────
    summary_short   = db.Column(db.Text, nullable=True)   # 1-2 sentence summary
    summary_long    = db.Column(db.Text, nullable=True)   # detailed summary
    extracted_text  = db.Column(db.Text, nullable=True)   # raw text from file

    # indexing_status: pending | processing | done | failed
    indexing_status = db.Column(db.String(20), default='pending')

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    indexed_at      = db.Column(db.DateTime, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    uploader = db.relationship('User', foreign_keys=[owner_user_id], lazy='joined')

    # ── Tag helpers ───────────────────────────────────────────────────────────
    def get_tags(self):
        try:
            return json.loads(self.tags_json or '[]')
        except (ValueError, TypeError):
            return []

    def set_tags(self, tag_list):
        """Deduplicate, lowercase, strip whitespace."""
        cleaned = list({t.strip().lower() for t in tag_list if t.strip()})
        self.tags_json = json.dumps(cleaned)

    def add_tags(self, new_tags):
        existing = set(self.get_tags())
        for t in new_tags:
            existing.add(t.strip().lower())
        self.tags_json = json.dumps(list(existing))

    def remove_tag(self, tag):
        tags = [t for t in self.get_tags() if t != tag.strip().lower()]
        self.tags_json = json.dumps(tags)

    # ── Serialisation ─────────────────────────────────────────────────────────
    def to_dict(self, include_summaries=True):
        data = {
            'id':                  self.id,
            'filename':            self.filename,
            'original_name':       self.original_name,
            'extension':           self.extension,
            'mime_type':           self.mime_type,
            'size_bytes':          self.size_bytes,
            'file_url':            self.file_url,
            'owner_user_id':       self.owner_user_id,
            'startup_id':          self.startup_id,
            'organization_id':     self.organization_id,
            'visibility_scope':    self.visibility_scope,
            'knowledge_type':      self.knowledge_type,
            'file_state':          self.file_state,
            'tags':                self.get_tags(),
            'linked_milestone_id': self.linked_milestone_id,
            'linked_meeting_id':   self.linked_meeting_id,
            'linked_task_id':      self.linked_task_id,
            'indexing_status':     self.indexing_status,
            'created_at':          self.created_at.isoformat() if self.created_at else None,
            'updated_at':          self.updated_at.isoformat() if self.updated_at else None,
            'indexed_at':          self.indexed_at.isoformat() if self.indexed_at else None,
            'uploader': {
                'id':   self.uploader.id,
                'name': f"{self.uploader.first_name} {self.uploader.last_name}",
            } if self.uploader else None,
        }
        if include_summaries:
            data['summary_short'] = self.summary_short
            data['summary_long']  = self.summary_long
        return data