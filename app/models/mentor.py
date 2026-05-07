"""
Mentorship Models — SF Collab
==============================

MentorProfile  — extended profile for users who register as mentors
MentorshipRequest — a founder requesting mentorship for a vision or startup
MentorSession  — a completed or scheduled mentorship session
MentorFeedback — feedback left by mentor on a vision/startup after a session

Flow:
  User registers as mentor → MentorProfile created
  Founder requests mentorship on Vision or Startup → MentorshipRequest created
  Mentor accepts → status = accepted
  Session happens → MentorSession recorded
  Mentor gives structured feedback → MentorFeedback created
  Vision readiness score increases (mentor_review component added)

Payment:
  Free mentorship → no payment
  Paid mentorship → Balance is debited on session confirmation
  Platform fee = 10% (same as marketplace)
"""

from datetime import datetime
from app.extensions import db
from sqlalchemy import JSON


# ─── Constants ────────────────────────────────────────────────────────────────

MENTOR_SECTORS = [
    'Technology', 'Product', 'Design', 'Marketing', 'Sales',
    'Finance', 'Legal', 'Operations', 'HR', 'Strategy',
    'AI / ML', 'Web3', 'Healthcare', 'EdTech', 'FinTech',
    'SaaS', 'Marketplace', 'Hardware', 'Media', 'Other',
]

MENTORSHIP_MODES = [
    'free_community',    # free, single session
    'paid_session',      # paid via Balance, single session
    'long_term_advisory', # ongoing relationship
]

REQUEST_STATUSES = [
    'pending',     # founder sent, mentor hasn't responded
    'accepted',    # mentor accepted, session to be scheduled
    'declined',    # mentor declined
    'completed',   # session done, feedback given
    'cancelled',   # cancelled by either party
]

MENTOR_STYLES = [
    'structured',    # formal agenda, clear outcomes
    'conversational', # open discussion
    'hands_on',      # deep technical involvement
    'advisory',      # high-level strategic guidance
    'accountability', # check-ins and accountability partner
]

PLATFORM_FEE_PERCENT = 10


# ─── MentorProfile ────────────────────────────────────────────────────────────

class MentorProfile(db.Model):
    __tablename__ = 'mentor_profiles'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'),
                            unique=True, nullable=False)

    # Application state: pending → approved → suspended
    status          = db.Column(db.String(20), default='approved', nullable=False)

    # Core profile fields
    bio             = db.Column(db.Text, nullable=True)
    sector_expertise = db.Column(JSON, default=list)   # list of strings from MENTOR_SECTORS
    experience_years = db.Column(db.Integer, default=0)
    mentorship_style = db.Column(db.String(50), default='conversational')
    linkedin_url    = db.Column(db.String(500), nullable=True)
    website_url     = db.Column(db.String(500), nullable=True)

    # Availability
    is_available        = db.Column(db.Boolean, default=True)
    available_hours_per_week = db.Column(db.Integer, default=2)  # rough indicator

    # Pricing
    is_free             = db.Column(db.Boolean, default=True)
    hourly_rate_cents   = db.Column(db.Integer, default=0)  # 0 = free
    session_rate_cents  = db.Column(db.Integer, default=0)  # per session price

    # Stats — updated automatically
    startups_mentored   = db.Column(db.Integer, default=0)
    sessions_completed  = db.Column(db.Integer, default=0)
    total_earned_cents  = db.Column(db.Integer, default=0)
    pending_payout_cents = db.Column(db.Integer, default=0)

    # Reputation — derived from session ratings
    average_rating      = db.Column(db.Float, default=0.0)
    rating_count        = db.Column(db.Integer, default=0)

    # Milestone success rate of mentored projects (manually or auto updated)
    milestone_success_rate = db.Column(db.Float, default=0.0)  # 0–100

    is_active   = db.Column(db.DateTime, nullable=True)   # last active
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow)

    # Relationships
    user     = db.relationship('User', back_populates='mentor_profile')
    requests = db.relationship('MentorshipRequest', back_populates='mentor',
                               foreign_keys='MentorshipRequest.mentor_id',
                               cascade='all, delete-orphan')
    sessions = db.relationship('MentorSession', back_populates='mentor',
                               foreign_keys='MentorSession.mentor_id',
                               cascade='all, delete-orphan')

    # ── Helpers ──────────────────────────────────────────────

    def is_approved(self) -> bool:
        return self.status == 'approved'

    @property
    def session_rate(self) -> float:
        return self.session_rate_cents / 100

    @property
    def platform_fee_cents(self) -> int:
        return int(self.session_rate_cents * PLATFORM_FEE_PERCENT / 100)

    @property
    def mentor_receives_cents(self) -> int:
        return self.session_rate_cents - self.platform_fee_cents

    def add_rating(self, score: float):
        """Recalculate average rating after a new session rating."""
        if not 1 <= score <= 5:
            raise ValueError('Rating must be 1–5')
        total = self.average_rating * self.rating_count + score
        self.rating_count += 1
        self.average_rating = round(total / self.rating_count, 2)
        db.session.commit()

    def record_session_completed(self, earned_cents: int = 0):
        self.sessions_completed += 1
        self.total_earned_cents += earned_cents
        self.pending_payout_cents += earned_cents
        db.session.commit()

    def to_dict(self, include_user=True):
        data = {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'status': self.status,
            'is_approved': self.is_approved(),
            'bio': self.bio,
            'sector_expertise': self.sector_expertise or [],
            'experience_years': self.experience_years,
            'mentorship_style': self.mentorship_style,
            'linkedin_url': self.linkedin_url,
            'website_url': self.website_url,
            'is_available': self.is_available,
            'available_hours_per_week': self.available_hours_per_week,
            'is_free': self.is_free,
            'session_rate': self.session_rate,
            'session_rate_cents': self.session_rate_cents,
            'platform_fee': self.platform_fee_cents / 100,
            'mentor_receives': self.mentor_receives_cents / 100,
            'startups_mentored': self.startups_mentored,
            'sessions_completed': self.sessions_completed,
            'average_rating': self.average_rating,
            'rating_count': self.rating_count,
            'milestone_success_rate': self.milestone_success_rate,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_user and self.user:
            data['user'] = {
                'id': str(self.user.id),
                'name': f"{self.user.first_name} {self.user.last_name}",
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
                'profile_picture': self.user.profile_picture,
                'reputation_score': self.user.reputation_score or 0,
                'xp_points': self.user.xp_points or 0,
            }
        return data

    def __repr__(self):
        return f'<MentorProfile user={self.user_id} status={self.status}>'


# ─── MentorshipRequest ────────────────────────────────────────────────────────

class MentorshipRequest(db.Model):
    __tablename__ = 'mentorship_requests'

    id          = db.Column(db.Integer, primary_key=True)
    founder_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mentor_id   = db.Column(db.Integer, db.ForeignKey('mentor_profiles.id'), nullable=False)

    # What the request is about — vision OR startup (one must be set)
    idea_id     = db.Column(db.Integer, db.ForeignKey('ideas.id'), nullable=True)
    startup_id  = db.Column(db.Integer, db.ForeignKey('startups.id'), nullable=True)

    # Request context
    message         = db.Column(db.Text, nullable=True)     # founder's message to mentor
    areas_of_help   = db.Column(JSON, default=list)         # e.g. ["GTM strategy", "technical architecture"]
    mentorship_mode = db.Column(db.String(30), default='free_community')
    status          = db.Column(db.String(20), default='pending', nullable=False)

    # Decline/cancel reason
    decline_reason  = db.Column(db.Text, nullable=True)

    # Payment — only set for paid sessions
    agreed_rate_cents = db.Column(db.Integer, default=0)
    payment_status    = db.Column(db.String(20), default='unpaid')  # unpaid | paid | refunded
    buyer_tx_id       = db.Column(db.Integer, nullable=True)  # BalanceTransaction id

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accepted_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    founder = db.relationship('User', foreign_keys=[founder_id])
    mentor  = db.relationship('MentorProfile', back_populates='requests',
                              foreign_keys=[mentor_id])
    idea    = db.relationship('Idea', foreign_keys=[idea_id])
    startup = db.relationship('Startup', foreign_keys=[startup_id])
    session = db.relationship('MentorSession', back_populates='request',
                              uselist=False, cascade='all, delete-orphan')

    def accept(self):
        self.status = 'accepted'
        self.accepted_at = datetime.utcnow()
        db.session.commit()

    def decline(self, reason: str = ''):
        self.status = 'declined'
        self.decline_reason = reason
        db.session.commit()

    def cancel(self):
        self.status = 'cancelled'
        db.session.commit()

    def complete(self):
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        db.session.commit()

    def to_dict(self):
        return {
            'id': str(self.id),
            'founder_id': str(self.founder_id),
            'mentor_id': str(self.mentor_id),
            'idea_id': str(self.idea_id) if self.idea_id else None,
            'startup_id': str(self.startup_id) if self.startup_id else None,
            'message': self.message,
            'areas_of_help': self.areas_of_help or [],
            'mentorship_mode': self.mentorship_mode,
            'status': self.status,
            'decline_reason': self.decline_reason,
            'agreed_rate_cents': self.agreed_rate_cents,
            'agreed_rate': self.agreed_rate_cents / 100,
            'payment_status': self.payment_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'founder': {
                'id': str(self.founder.id),
                'name': f"{self.founder.first_name} {self.founder.last_name}",
                'profile_picture': self.founder.profile_picture,
            } if self.founder else None,
            'mentor': self.mentor.to_dict() if self.mentor else None,
            'idea': {
                'id': str(self.idea.id),
                'title': self.idea.title,
                'readiness_score': self.idea.readiness_score,
            } if self.idea else None,
            'startup': {
                'id': str(self.startup.id),
                'name': self.startup.name,
            } if self.startup else None,
        }


# ─── MentorSession ───────────────────────────────────────────────────────────

class MentorSession(db.Model):
    __tablename__ = 'mentor_sessions'

    id          = db.Column(db.Integer, primary_key=True)
    request_id  = db.Column(db.Integer, db.ForeignKey('mentorship_requests.id'),
                            unique=True, nullable=False)
    mentor_id   = db.Column(db.Integer, db.ForeignKey('mentor_profiles.id'), nullable=False)
    founder_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Session content
    summary     = db.Column(db.Text, nullable=True)         # mentor's session notes
    action_items = db.Column(JSON, default=list)             # list of follow-up actions
    readiness_impact = db.Column(db.Float, default=0.0)     # how much readiness improved

    # Rating from founder
    founder_rating  = db.Column(db.Float, nullable=True)    # 1–5
    founder_review  = db.Column(db.Text, nullable=True)

    # Payment
    amount_cents    = db.Column(db.Integer, default=0)
    platform_fee_cents = db.Column(db.Integer, default=0)
    mentor_cut_cents   = db.Column(db.Integer, default=0)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    request = db.relationship('MentorshipRequest', back_populates='session')
    mentor  = db.relationship('MentorProfile', back_populates='sessions',
                              foreign_keys=[mentor_id])
    founder = db.relationship('User', foreign_keys=[founder_id])

    def to_dict(self):
        return {
            'id': str(self.id),
            'request_id': str(self.request_id),
            'mentor_id': str(self.mentor_id),
            'founder_id': str(self.founder_id),
            'summary': self.summary,
            'action_items': self.action_items or [],
            'readiness_impact': self.readiness_impact,
            'founder_rating': self.founder_rating,
            'founder_review': self.founder_review,
            'amount': self.amount_cents / 100,
            'platform_fee': self.platform_fee_cents / 100,
            'mentor_cut': self.mentor_cut_cents / 100,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }