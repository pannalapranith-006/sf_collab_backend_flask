"""
MarketplacePurchase Model
==========================
Records every completed purchase of a marketplace listing.

Payment flow:
  1. Buyer's Balance is debited (full price)
  2. Platform fee (10%) is kept
  3. Seller's Balance is credited (90%)
  4. Seller's pending_payout_cents increases
  5. File download URL is made available to buyer

One purchase row = one transaction. Idempotency is enforced
by checking existing purchases before creating new ones.
"""

from datetime import datetime
from app.extensions import db


class MarketplacePurchase(db.Model):
    __tablename__ = 'marketplace_purchases'

    id          = db.Column(db.Integer, primary_key=True)

    # Parties
    buyer_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id   = db.Column(db.Integer, db.ForeignKey('marketplace_sellers.id'), nullable=False)
    listing_id  = db.Column(db.Integer, db.ForeignKey('marketplace_listings.id'), nullable=False)

    # Amounts in cents
    price_cents        = db.Column(db.Integer, nullable=False)  # what buyer paid
    platform_fee_cents = db.Column(db.Integer, nullable=False)  # 10%
    seller_cut_cents   = db.Column(db.Integer, nullable=False)  # 90%

    currency    = db.Column(db.String(3), default='USD')
    status      = db.Column(db.String(20), default='completed')  # completed | refunded

    # Linked balance transaction IDs for audit
    buyer_tx_id  = db.Column(db.Integer, nullable=True)   # BalanceTransaction.id (debit)
    seller_tx_id = db.Column(db.Integer, nullable=True)   # BalanceTransaction.id (credit)

    # Rating left by the buyer (null until rated)
    rating       = db.Column(db.Float, nullable=True)     # 1.0 – 5.0
    review_text  = db.Column(db.Text, nullable=True)
    rated_at     = db.Column(db.DateTime, nullable=True)

    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    buyer   = db.relationship('User', foreign_keys=[buyer_id])
    seller  = db.relationship('Seller', foreign_keys=[seller_id])
    listing = db.relationship('MarketplaceListing')

    def to_dict(self):
        return {
            'id': str(self.id),
            'buyer_id': str(self.buyer_id),
            'seller_id': str(self.seller_id),
            'listing_id': str(self.listing_id),
            'listing': self.listing.to_dict(include_seller=False) if self.listing else None,
            'price': self.price_cents / 100,
            'platform_fee': self.platform_fee_cents / 100,
            'seller_cut': self.seller_cut_cents / 100,
            'currency': self.currency,
            'status': self.status,
            'rating': self.rating,
            'review_text': self.review_text,
            'rated_at': self.rated_at.isoformat() if self.rated_at else None,
            'purchased_at': self.purchased_at.isoformat() if self.purchased_at else None,
        }

    def __repr__(self):
        return f'<MarketplacePurchase id={self.id} listing={self.listing_id} buyer={self.buyer_id}>'