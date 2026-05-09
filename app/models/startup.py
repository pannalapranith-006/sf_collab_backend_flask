from datetime import datetime, timedelta
from app.extensions import db
from sqlalchemy import Enum, JSON
from .Enums import StartupStage
import os
from sqlalchemy.ext.mutable import MutableDict, MutableList

# ─────────────────────────────────────────────────────────────
# STARTUP LIFECYCLE STATES (per product doc)
# ─────────────────────────────────────────────────────────────
STARTUP_LIFECYCLE_STATES = [
    'founder_only',   # Single founder, no team — hidden from main discovery
    'active',         # Active with team
    'recruiting',     # Actively looking for members
    'slowing',        # Activity declining
    'at_risk',        # Significant inactivity
    'dormant',        # Essentially stalled — hidden from main discovery
    'launched',       # Successfully launched
    'archived',       # Manually archived
]

class Startup(db.Model):
    __tablename__ = 'startups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    industry = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    stage = db.Column(Enum(StartupStage), default=StartupStage.idea)
    
    # Financial Foundation Fields
    revenue = db.Column(db.Float, default=0.0)
    funding_amount = db.Column(db.Float, default=0.0)
    funding_round = db.Column(db.String(50), default='pre-seed')
    burn_rate = db.Column(db.Float, default=0.0)
    runway_months = db.Column(db.Integer, default=0)
    valuation = db.Column(db.Float, default=0.0)
    financial_notes = db.Column(db.Text)
    
    # Media
    logo_path = db.Column(db.String(500))
    logo_content_type = db.Column(db.String(100))
    banner_path = db.Column(db.String(500))
    banner_content_type = db.Column(db.String(100))
    logo_url = db.Column(db.String(500))
    banner_url = db.Column(db.String(500))
    
    roles = db.Column(MutableDict.as_mutable(JSON), default=dict)
    tech_stack = db.Column(MutableList.as_mutable(JSON), default=list)
    
    positions = db.Column(db.Integer, default=0)
    
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    creator_first_name = db.Column(db.String(100))
    creator_last_name = db.Column(db.String(100))
    
    status = db.Column(db.String(50), default='active')
    member_count = db.Column(db.Integer, default=1)
    views = db.Column(db.Integer, default=0)

    # ── Week 1: Lifecycle & Execution fields ──────────────────
    # Lifecycle state (separate from 'status' which is legacy)
    lifecycle_state = db.Column(db.String(50), default='active')

    # Execution Score (0–10) — the platform's main trust signal for a startup
    execution_score = db.Column(db.Float, default=0.0)

    # Milestone tracking
    milestones_completed = db.Column(db.Integer, default=0)
    milestones_total = db.Column(db.Integer, default=0)

    # Activity tracking
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    activity_score = db.Column(db.Float, default=0.0)  # 0–100 recency score

    # Crowdfunding unlock tracking (Week 2)
    crowdfunding_unlocked = db.Column(db.Boolean, default=False)
    crowdfunding_unlocked_at = db.Column(db.DateTime, nullable=True)
    # ── End new fields ─────────────────────────────────────────
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    startup_creator = db.relationship(
        "User",
        back_populates="startups",
        foreign_keys=[creator_id]
    )
    
    startup_members = db.relationship('StartupMember', 
        back_populates='member_startup', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='StartupMember.startup_id')
    
    join_requests = db.relationship('JoinRequest', 
        back_populates='target_startup', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='JoinRequest.startup_id')
    
    startup_bookmarks = db.relationship('StartupBookmark',
        back_populates='startup',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='StartupBookmark.startup_id')
    
    startup_tasks = db.relationship('Task',
        back_populates='parent_startup',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='Task.startup_id')
    
    project_goals = db.relationship('ProjectGoal',
        back_populates='parent_startup',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='ProjectGoal.startup_id')
    
    team_performance_records = db.relationship('TeamPerformance',
        back_populates='parent_startup',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='TeamPerformance.startup_id')
    
    growth_metrics_startup = db.relationship('GrowthMetric',
        back_populates='parent_startup',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='GrowthMetric.startup_id')
    
    calendar_events = db.relationship('CalendarEvent',
        back_populates='parent_startup',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='CalendarEvent.startup_id')
        
    startup_documents = db.relationship('StartupDocument',
        back_populates='parent_startup',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='StartupDocument.startup_id')

    startup_views = db.relationship('StartupView',
        back_populates='startup',
        lazy='dynamic',
        cascade='all, delete-orphan')
    
    ratings = db.relationship('StartupRating',
        back_populates='startup',
        lazy='dynamic',
        cascade='all, delete-orphan')
    
# Drive files
    drive_files_list = db.relationship(
    "DriveFile",
    back_populates="workspace",
    foreign_keys="DriveFile.workspace_id",
    cascade="all, delete-orphan"
)

# Drive folders
    drive_folders_list = db.relationship(
    "DriveFolder",
    back_populates="workspace",
    foreign_keys="DriveFolder.workspace_id",
    cascade="all, delete-orphan"
)

    # ── HELPER FUNCTIONS ──────────────────────────────────────

    def increment_views(self, user_id):
        isViewed = StartupView.query.filter_by(startup_id=self.id, user_id=user_id).first()
        if not isViewed:
            new_view = StartupView(startup_id=self.id, user_id=user_id)
            self.views += 1
            db.session.add(new_view)
        db.session.commit()
    
    def update_member_count(self):
        active_members = self.startup_members.filter_by(is_active=True).count()
        self.member_count = active_members
        db.session.commit()
    
    def add_member(self, user_id, first_name, last_name, role='member'):
        from app.models.startUpMember import StartupMember
        member = StartupMember(
            startup_id=self.id,
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        db.session.add(member)
        self.update_member_count()
        db.session.commit()
        return member
    
    def remove_member(self, user_id):
        member = self.startup_members.filter_by(user_id=user_id, is_active=True).first()
        if member:
            db.session.delete(member)
            self.update_member_count()
            db.session.commit()
            return True
        return False

    def remove_member_by_id(self, member_id):
        member = self.startup_members.filter_by(id=member_id, is_active=True).first()
        if not member:
            return False
        db.session.delete(member)
        self.update_member_count()
        db.session.commit()
        return True

    def update_stage(self, new_stage):
        self.stage = StartupStage(new_stage)
        db.session.commit()

    def add_position(self, role_name, count=1):
        if not self.roles:
            self.roles = {}
        if role_name not in self.roles:
            self.roles[role_name] = {"roleType": "Full Time", "positionsNumber": count}
        else:
            role_data = self.roles[role_name]
            if isinstance(role_data, dict):
                role_data['positionsNumber'] = role_data.get('positionsNumber', 0) + count
            else:
                self.roles[role_name] = {"roleType": role_data, "positionsNumber": count}
        self.positions += count
        db.session.commit()
    
    def fill_position(self, role_name):
        if self.roles and role_name in self.roles:
            role_data = self.roles[role_name]
            if isinstance(role_data, dict):
                current = role_data.get('positionsNumber', 0)
                if current > 0:
                    role_data['positionsNumber'] = current - 1
                    self.positions -= 1
                    db.session.commit()
            else:
                del self.roles[role_name]
                self.positions -= 1
                db.session.commit()
    
    def get_active_members(self):
        return self.startup_members.filter_by(is_active=True).all()
    
    def add_document(self, filename, file_path, content_type, document_type='general', file_url=None):
        from app.models.startup_document import StartupDocument
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024) if os.path.exists(file_path) else 0
        if not file_url:
            unique_filename = os.path.basename(file_path)
            file_url = f"/startups/uploads/{self.id}/{unique_filename}"
        document = StartupDocument(
            startup_id=self.id,
            filename=filename,
            file_path=file_path,
            file_url=file_url,
            content_type=content_type,
            document_type=document_type,
            file_size_mb=file_size_mb
        )
        db.session.add(document)
        db.session.commit()
        return document

    def get_documents(self, document_type=None):
        query = self.startup_documents
        if document_type:
            query = query.filter_by(document_type=document_type)
        return query.all()

    # ── Week 1: Execution Score Engine ────────────────────────

    def compute_execution_score(self) -> float:
        """
        Compute and persist a 0–10 Execution Score.
        This is the platform's primary trust signal for a startup.

        Scoring inputs (weighted):
          - Milestone completion rate   → 30%
          - Team size stability         → 20%
          - Activity recency            → 20%
          - Milestones completed (abs)  → 15%
          - Member count                → 15%
        """
        score = 0.0

        # Milestone completion rate (30%)
        if self.milestones_total and self.milestones_total > 0:
            completion_rate = self.milestones_completed / self.milestones_total
            score += completion_rate * 3.0  # max 3 points
        
        # Team size (20%) — 1 member = 0, 2 = 1pt, 3 = 1.5pt, 4+ = 2pt
        active_count = self.startup_members.filter_by(is_active=True).count()
        if active_count >= 4:
            score += 2.0
        elif active_count == 3:
            score += 1.5
        elif active_count == 2:
            score += 1.0

        # Activity recency (20%) — based on last_activity_at
        if self.last_activity_at:
            days_since = (datetime.utcnow() - self.last_activity_at).days
            if days_since <= 1:
                score += 2.0
            elif days_since <= 7:
                score += 1.5
            elif days_since <= 30:
                score += 1.0
            elif days_since <= 90:
                score += 0.5

        # Milestones completed absolute (15%) — rewards getting things done
        if self.milestones_completed >= 5:
            score += 1.5
        elif self.milestones_completed >= 3:
            score += 1.0
        elif self.milestones_completed >= 1:
            score += 0.5

        # Member count contribution (15%)
        member_score = min(active_count / 5.0, 1.0) * 1.5
        score += member_score

        # Clamp to 0–10
        final_score = round(min(max(score, 0.0), 10.0), 2)
        self.execution_score = final_score

        # Auto-update lifecycle state based on score + recency
        self._auto_update_lifecycle_state()

        db.session.commit()
        return final_score

    def _auto_update_lifecycle_state(self):
        """
        Automatically transitions lifecycle_state based on current signals.
        Only transitions DOWN (active → slowing → dormant).
        Transitions UP must be triggered by explicit actions (milestone complete, member join).
        """
        if self.lifecycle_state in ('launched', 'archived', 'founder_only'):
            return  # Don't touch terminal states

        days_inactive = 0
        if self.last_activity_at:
            days_inactive = (datetime.utcnow() - self.last_activity_at).days

        active_count = self.startup_members.filter_by(is_active=True).count()

        if days_inactive > 60 or (self.execution_score < 2.0 and days_inactive > 30):
            self.lifecycle_state = 'dormant'
        elif days_inactive > 21 or self.execution_score < 4.0:
            self.lifecycle_state = 'slowing'
        elif active_count == 1 and self.lifecycle_state == 'founder_only':
            pass  # Already founder only, leave it
        elif self.positions > 0 and self.lifecycle_state in ('active', 'slowing'):
            self.lifecycle_state = 'recruiting'
        elif active_count >= 2 and self.lifecycle_state in ('founder_only', 'slowing'):
            self.lifecycle_state = 'active'

    def record_activity(self):
        """Call this whenever a meaningful action happens on the startup
        (milestone complete, member joins, task completed, etc.)"""
        self.last_activity_at = datetime.utcnow()
        # Re-evaluate lifecycle state
        if self.lifecycle_state in ('slowing', 'dormant'):
            if self.startup_members.filter_by(is_active=True).count() >= 2:
                self.lifecycle_state = 'active'
        db.session.commit()

    def check_crowdfunding_eligibility(self) -> dict:
        """
        Check whether this startup qualifies to unlock crowdfunding.
        Returns {'eligible': bool, 'reasons': list}
        """
        reasons = []
        
        if self.milestones_completed < 3:
            reasons.append(f"Need {3 - self.milestones_completed} more milestone(s) completed")
        
        active_count = self.startup_members.filter_by(is_active=True).count()
        if active_count < 2:
            reasons.append("Need at least 2 collaborators")
        
        days_active = (datetime.utcnow() - self.created_at).days
        if days_active < 14:
            reasons.append(f"Startup must be active for at least 14 days ({14 - days_active} days remaining)")

        # Founder verification check (checks User model)
        from app.models.user import User
        creator = User.query.get(self.creator_id)
        if creator and not getattr(creator, 'is_email_verified', False):
            reasons.append("Founder must verify their email")

        eligible = len(reasons) == 0
        return {'eligible': eligible, 'reasons': reasons}

    def unlock_crowdfunding(self):
        """Unlock crowdfunding if all conditions are met."""
        check = self.check_crowdfunding_eligibility()
        if not check['eligible']:
            raise ValueError(f"Crowdfunding not yet eligible: {'; '.join(check['reasons'])}")
        self.crowdfunding_unlocked = True
        self.crowdfunding_unlocked_at = datetime.utcnow()
        db.session.commit()
        return True

    # ─────────────────────────────────────────────────────────

    def _enum_to_value(self, value):
        return value.value if hasattr(value, "value") else value

    def _get_average_rating(self):
        from sqlalchemy import func
        from app.models.startup_rating import StartupRating
        result = db.session.query(func.avg(StartupRating.rating)).filter(
            StartupRating.startup_id == self.id
        ).scalar()
        return round(float(result), 2) if result else 0

    def _get_rating_count(self):
        return self.ratings.count()
    
    def to_dict(self):
        completion_rate = 0
        if self.milestones_total and self.milestones_total > 0:
            completion_rate = round(
                (self.milestones_completed / self.milestones_total) * 100, 1
            )

        return {
            'id': self.id,
            'name': self.name,
            'industry': self.industry,
            'location': self.location,
            'description': self.description,
            'stage': self._enum_to_value(self.stage),
            'positions': self.positions,
            'roles': self.roles or {},
            'tech_stack': self.tech_stack or [],
            'revenue': self.revenue,
            'funding_amount': self.funding_amount,
            'funding_round': self.funding_round,
            'burn_rate': self.burn_rate,
            'runway_months': self.runway_months,
            'valuation': self.valuation,
            'financial_notes': self.financial_notes,
            'logo_url': self.logo_url or (f'/startups/{self.id}/logo' if self.logo_path else None),
            'banner_url': self.banner_url or (f'/startups/{self.id}/banner' if self.banner_path else None),
            'creator': {
                'id': self.creator_id,
                'firstName': self.creator_first_name,
                'lastName': self.creator_last_name
            },
            'status': self.status,
            'memberCount': self.member_count,
            'views': self.views,
            'average_rating': self._get_average_rating(),
            'rating_count': self._get_rating_count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,

            # ── Week 1: Lifecycle & Execution fields ──
            'lifecycleState': self.lifecycle_state or 'active',
            'executionScore': self.execution_score or 0.0,
            'milestonesCompleted': self.milestones_completed or 0,
            'milestonesTotal': self.milestones_total or 0,
            'milestoneCompletionRate': completion_rate,
            'lastActivityAt': self.last_activity_at.isoformat() if self.last_activity_at else None,
            'crowdfundingUnlocked': self.crowdfunding_unlocked or False,

            # Visibility helper — main discovery feed should check this
            'isDiscoverable': self.lifecycle_state not in ('founder_only', 'dormant', 'archived'),
        }


class StartupView(db.Model):
    __tablename__ = 'startup_views'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    startup_id = db.Column(db.Integer, db.ForeignKey('startups.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='startup_views')
    startup = db.relationship('Startup', back_populates='startup_views')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'startup_id': self.startup_id,
            'viewed_at': self.viewed_at.isoformat()
        }