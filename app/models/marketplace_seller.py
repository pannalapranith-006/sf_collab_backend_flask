"""
Seller Model — SF Marketplace
A Seller is a user who has registered to sell digital resources
on the SF Marketplace.

Rules (per SF Economy docs):
- Every listing must help someone build or launch a startup
- Seller trust is visible: verification, reputation, delivery history, disputes
- Sellers receive 90% of sale price — platform takes 10%
- Balance is the only payment currency (NOT Crystals)
"""

from datetime import datetime
from app.extensions import db
from sqlalchemy import JSON


class Seller(db.Model):
    __tablename__ = 'marketplace_sellers'

    id                      = db.Column(db.Integer, primary_key=True)
    user_id                 = db.Column(db.Integer, db.ForeignKey('users.id'),
                                        unique=True, nullable=False)

    # Trust & Verification
    # unverified → pending → verified → suspended
    verification_status     = db.Column(db.String(20), default='unverified', nullable=False)

    # Cached reputation score (0–100). Sourced from User.reputation_score
    # but can be weighted by marketplace-specific signals
    reputation_score        = db.Column(db.Float, default=0.0)

    # Delivery & Dispute counters (affect trust display)
    delivery_history_count  = db.Column(db.Integer, default=0)   # successful deliveries
    dispute_count           = db.Column(db.Integer, default=0)    # disputes raised against seller

    # JSON list of category names this seller specialises in
    # e.g. ["Development", "Design"]
    specialization_categories = db.Column(JSON, default=list)

    # Seller bio / storefront description
    bio                     = db.Column(db.Text, nullable=True)

    # Payout info — links to Balance wallet (Balance.user_id == user_id)
    # Stripe Connect account ID stored on User.stripe_connect_account_id
    total_earned_cents      = db.Column(db.Integer, default=0)   # lifetime earnings in cents
    pending_payout_cents    = db.Column(db.Integer, default=0)   # awaiting next payout run

    is_active               = db.Column(db.Boolean, default=True)
    created_at              = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at              = db.Column(db.DateTime, default=datetime.utcnow,
                                        onupdate=datetime.utcnow)

    # Relationships
    user     = db.relationship('User', back_populates='seller_profile')
    listings = db.relationship('MarketplaceListing', back_populates='seller',
                               cascade='all, delete-orphan')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_verified(self) -> bool:
        return self.verification_status == 'verified'

    def trust_score(self) -> float:
        """
        Simple trust signal for display (0–100).
        Combines reputation + delivery rate.
        Dispute history reduces score.
        """
        base = self.reputation_score or 0.0
        delivery_bonus = min(self.delivery_history_count / 10, 1.0) * 20
        dispute_penalty = min(self.dispute_count * 5, 30)
        return round(max(0, base + delivery_bonus - dispute_penalty), 1)

    def record_delivery(self):
        """Call after a successful order delivery."""
        self.delivery_history_count += 1
        db.session.commit()

    def record_dispute(self):
        """Call when a dispute is raised against this seller."""
        self.dispute_count += 1
        db.session.commit()

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'verification_status': self.verification_status,
            'is_verified': self.is_verified(),
            'reputation_score': self.reputation_score,
            'trust_score': self.trust_score(),
            'delivery_history_count': self.delivery_history_count,
            'dispute_count': self.dispute_count,
            'specialization_categories': self.specialization_categories or [],
            'bio': self.bio,
            'total_earned': self.total_earned_cents / 100,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            # Embed basic user info for display
            'user': {
                'id': str(self.user.id),
                'name': f"{self.user.first_name} {self.user.last_name}",
                'profile_picture': self.user.profile_picture,
            } if self.user else None
        }

    def __repr__(self):
        return f'<Seller user_id={self.user_id} status={self.verification_status}>'