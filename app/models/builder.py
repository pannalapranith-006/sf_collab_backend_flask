"""
Builder Profile Models
Includes: BuilderProfile, BuilderSkill, BuilderPortfolio, BuilderApplication, SavedStartup
"""
from datetime import datetime
from sqlalchemy import Enum, JSON, ForeignKey, Table
from app.extensions import db
import enum

class ApplicationStatus(enum.Enum):
    """Application status enum"""
    pending = "pending"
    under_review = "under_review"
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"


class BuilderProfile(db.Model):
    """Extended profile for builders"""
    __tablename__ = 'builder_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)
    
    # Professional info
    title = db.Column(db.String(255), nullable=True)  # e.g., "Full Stack Developer"
    bio = db.Column(db.Text, nullable=True)
    hourly_rate = db.Column(db.Float, nullable=True)  # For hourly work
    
    # Rating & reputation
    rating = db.Column(db.Float, default=0.0)  # 0-5 stars
    review_count = db.Column(db.Integer, default=0)
    completed_projects = db.Column(db.Integer, default=0)
    
    # Statistics
    total_earnings = db.Column(db.Float, default=0.0)
    total_equity_earned = db.Column(db.Float, default=0.0)  # Percentage
    on_time_delivery_rate = db.Column(db.Float, default=100.0)  # Percentage
    
    # Preferences
    preferred_work_type = db.Column(JSON, default=[])  # ["hourly", "project", "equity"]
    industries_interested = db.Column(JSON, default=[])  # Interested startup industries

    # Matchmaking fields
    skill_tags = db.Column(JSON, default=[])  # JSON list of skill strings for matchmaking
    sector_interests = db.Column(JSON, default=[])  # Sector interests for matchmaking
    execution_score = db.Column(db.Integer, default=50)  # 0-100 execution reputation score
    availability = db.Column(db.String(50), default="AVAILABLE")  # AVAILABLE, OPEN, NOT_AVAILABLE

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='builder_profile', uselist=False)
    skills = db.relationship('BuilderSkill', backref='profile', lazy=True, cascade='all, delete-orphan')
    portfolio_items = db.relationship('BuilderPortfolio', backref='profile', lazy=True, cascade='all, delete-orphan')
    applications = db.relationship('BuilderApplication', backref='profile', lazy=True, cascade='all, delete-orphan')
    saved_startups = db.relationship('SavedStartup', backref='builder', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self, include_relations=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'bio': self.bio,
            'hourly_rate': self.hourly_rate,
            'rating': self.rating,
            'review_count': self.review_count,
            'completed_projects': self.completed_projects,
            'total_earnings': self.total_earnings,
            'total_equity_earned': self.total_equity_earned,
            'on_time_delivery_rate': self.on_time_delivery_rate,
            'preferred_work_type': self.preferred_work_type,
            'industries_interested': self.industries_interested,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        
        if include_relations:
            data['skills'] = [s.to_dict() for s in self.skills]
            data['portfolio_items'] = [p.to_dict() for p in self.portfolio_items]
        
        return data


class BuilderSkill(db.Model):
    """Builder's professional skills"""
    __tablename__ = 'builder_skills'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('builder_profiles.id'), nullable=False, index=True)
    
    # Skill info
    name = db.Column(db.String(100), nullable=False)  # e.g., "React", "Node.js"
    level = db.Column(db.String(50), nullable=True)  # "Beginner", "Intermediate", "Advanced", "Expert"
    years_of_experience = db.Column(db.Integer, nullable=True)
    
    # Verification
    is_verified = db.Column(db.Boolean, default=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verification_date = db.Column(db.DateTime, nullable=True)
    
    # Endorsements
    endorsement_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'name': self.name,
            'level': self.level,
            'years_of_experience': self.years_of_experience,
            'is_verified': self.is_verified,
            'endorsement_count': self.endorsement_count,
            'created_at': self.created_at.isoformat(),
        }


class BuilderPortfolio(db.Model):
    """Builder's portfolio items (projects, works)"""
    __tablename__ = 'builder_portfolio'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('builder_profiles.id'), nullable=False, index=True)
    
    # Project info
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(500), nullable=True)  # Link to project
    image_url = db.Column(db.String(500), nullable=True)
    
    # Classification
    project_type = db.Column(db.String(100), nullable=True)  # "Web App", "Mobile", "Design", etc.
    skills_used = db.Column(JSON, default=[])  # Array of skills used
    
    # Stats
    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'profile_id': self.profile_id,
            'title': self.title,
            'description': self.description,
            'url': self.url,
            'image_url': self.image_url,
            'project_type': self.project_type,
            'skills_used': self.skills_used,
            'likes': self.likes,
            'views': self.views,
            'created_at': self.created_at.isoformat(),
        }


class BuilderApplication(db.Model):
    """Builder's applications to startups"""
    __tablename__ = 'builder_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('builder_profiles.id'), nullable=False, index=True)
    startup_id = db.Column(db.Integer, db.ForeignKey('startups.id'), nullable=False, index=True)
    
    # Application details
    status = db.Column(Enum(ApplicationStatus), default=ApplicationStatus.pending, index=True)
    role_applied_for = db.Column(db.String(255), nullable=True)  # e.g., "Frontend Developer"
    cover_letter = db.Column(db.Text, nullable=True)
    
    # Additional info
    expected_commitment = db.Column(db.String(100), nullable=True)  # "Full-time", "Part-time", "Project-based"
    proposed_rate = db.Column(db.Float, nullable=True)  # Hourly rate or equity %
    
    # Communication
    last_message = db.Column(db.Text, nullable=True)
    last_message_date = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    applied_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    review_date = db.Column(db.DateTime, nullable=True)
    withdrawn_date = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    startup = db.relationship('Startup', backref='builder_applications')
    
    def to_dict(self, include_startup=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'profile_id': self.profile_id,
            'startup_id': self.startup_id,
            'status': self.status.value if self.status else None,
            'role_applied_for': self.role_applied_for,
            'cover_letter': self.cover_letter,
            'expected_commitment': self.expected_commitment,
            'proposed_rate': self.proposed_rate,
            'applied_date': self.applied_date.isoformat(),
            'review_date': self.review_date.isoformat() if self.review_date else None,
            'updated_at': self.updated_at.isoformat(),
        }
        
        if include_startup and self.startup:
            data['startup'] = {
                'id': self.startup.id,
                'name': self.startup.name,
                'description': self.startup.description,
            }
        
        return data


class SavedStartup(db.Model):
    """Builder's saved startups (bookmarks)"""
    __tablename__ = 'saved_startups'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('builder_profiles.id'), nullable=False, index=True)
    startup_id = db.Column(db.Integer, db.ForeignKey('startups.id'), nullable=False, index=True)
    
    # Notes
    notes = db.Column(db.Text, nullable=True)  # Builder's personal notes
    is_interested = db.Column(db.Boolean, default=True)
    
    # Timestamps
    saved_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    startup = db.relationship('Startup', backref='saved_by_builders')
    
    # Unique constraint: a builder can only save a startup once
    __table_args__ = (
        db.UniqueConstraint('profile_id', 'startup_id', name='uq_builder_startup_save'),
    )
    
    def to_dict(self, include_startup=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'profile_id': self.profile_id,
            'startup_id': self.startup_id,
            'notes': self.notes,
            'is_interested': self.is_interested,
            'saved_date': self.saved_date.isoformat(),
        }
        
        if include_startup and self.startup:
            data['startup'] = {
                'id': self.startup.id,
                'name': self.startup.name,
                'description': self.startup.description,
                'logo': self.startup.logo,
                'stage': self.startup.stage,
            }
        
        return data
