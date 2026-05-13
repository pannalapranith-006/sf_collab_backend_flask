"""
MarketplaceListing Model — SF Marketplace
A digital resource listed for sale by a Seller.

Rules (per SF Economy docs):
- Every listing must help someone build or launch a startup.
- Price is in cents (integer) to avoid float drift.
- Balance is the only payment currency. Crystals can boost visibility only.
- Platform fee = 10%. Seller receives 90%.
- File URL points to local uploads/marketplace/ directory.

Status lifecycle:
  draft → published → archived
  draft → rejected   (admin rejects during review)
"""

from datetime import datetime
from app.extensions import db
from sqlalchemy import JSON


# Allowed file extensions for digital products
ALLOWED_PRODUCT_EXTENSIONS = {
    'zip', 'pdf', 'fig', 'sketch', 'xd',
    'pptx', 'docx', 'xlsx', 'csv', 'json',
    'png', 'jpg', 'jpeg', 'svg', 'webp',
    'mp4', 'mov',
    'py', 'js', 'ts', 'jsx', 'tsx', 'html', 'css',
}

PLATFORM_FEE_PERCENT = 10   # Platform takes 10%, seller receives 90%


class MarketplaceListing(db.Model):
    __tablename__ = 'marketplace_listings'

    id          = db.Column(db.Integer, primary_key=True)
    seller_id   = db.Column(db.Integer, db.ForeignKey('marketplace_sellers.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('marketplace_categories.id'), nullable=False)

    # Core listing fields
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    item_type   = db.Column(db.String(100), nullable=True)   # sub-type within category e.g. "UI kit"

    # Pricing — stored in cents
    price_cents     = db.Column(db.Integer, nullable=False)   # e.g. 2000 = $20.00
    currency        = db.Column(db.String(3), default='USD', nullable=False)

    # Files — stored locally at uploads/marketplace/<seller_id>/
    file_url        = db.Column(db.Text, nullable=True)       # path to main downloadable file
    file_name       = db.Column(db.String(255), nullable=True)
    file_size_bytes = db.Column(db.Integer, nullable=True)
    file_type       = db.Column(db.String(50), nullable=True)  # mime type or extension

    # Preview images — JSON list of relative URLs
    # e.g. ["/uploads/marketplace/previews/1_preview1.png"]
    preview_images  = db.Column(JSON, default=list)

    # Tags for search
    tags            = db.Column(JSON, default=list)

    # Stats
    downloads_count = db.Column(db.Integer, default=0)
    views_count     = db.Column(db.Integer, default=0)
    rating          = db.Column(db.Float, default=0.0)   # average rating 0–5
    rating_count    = db.Column(db.Integer, default=0)   # number of ratings

    # Status — draft | published | archived | rejected
    status          = db.Column(db.String(20), default='draft', nullable=False)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Visibility boost via Crystals (does NOT affect price or reputation)
    is_boosted      = db.Column(db.Boolean, default=False)
    boost_expires_at = db.Column(db.DateTime, nullable=True)

    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow)

    # Relationships
    seller   = db.relationship('Seller', back_populates='listings')
    category = db.relationship('MarketplaceCategory', back_populates='listings')

    # ------------------------------------------------------------------
    # Business Logic
    # ------------------------------------------------------------------

    @property
    def price(self) -> float:
        """Price in dollars for display."""
        return self.price_cents / 100

    @property
    def platform_fee_cents(self) -> int:
        """Platform fee in cents (10%)."""
        return int(self.price_cents * PLATFORM_FEE_PERCENT / 100)

    @property
    def seller_receives_cents(self) -> int:
        """Amount seller receives after platform fee."""
        return self.price_cents - self.platform_fee_cents

    def publish(self):
        """Move listing from draft to published."""
        if self.status not in ('draft', 'rejected'):
            raise ValueError(f'Cannot publish listing in status: {self.status}')
        if not self.file_url:
            raise ValueError('Cannot publish a listing without an uploaded file')
        self.status = 'published'
        db.session.commit()

    def archive(self):
        """Seller archives a published listing."""
        self.status = 'archived'
        self.is_active = False
        db.session.commit()

    def reject(self, reason: str = ''):
        """Admin rejects a listing (does not meet marketplace rules)."""
        self.status = 'rejected'
        self.rejection_reason = reason
        db.session.commit()

    def increment_views(self):
        """Call when a user views the listing detail page."""
        self.views_count += 1
        db.session.commit()

    def increment_downloads(self):
        """Call after a successful purchase and file delivery."""
        self.downloads_count += 1
        db.session.commit()

    def add_rating(self, score: float):
        """
        Add a single rating (1–5) and recalculate average.
        Call after a verified purchase.
        """
        if not 1 <= score <= 5:
            raise ValueError('Rating must be between 1 and 5')
        total = self.rating * self.rating_count + score
        self.rating_count += 1
        self.rating = round(total / self.rating_count, 2)
        db.session.commit()

    def is_boost_active(self) -> bool:
        if self.is_boosted and self.boost_expires_at:
            return datetime.utcnow() < self.boost_expires_at
        return False

    def to_dict(self, include_seller=True):
        data = {
            'id': str(self.id),
            'seller_id': str(self.seller_id),
            'category_id': str(self.category_id),
            'category': self.category.to_dict() if self.category else None,
            'title': self.title,
            'description': self.description,
            'item_type': self.item_type,
            'price': self.price,
            'price_cents': self.price_cents,
            'platform_fee': self.platform_fee_cents / 100,
            'seller_receives': self.seller_receives_cents / 100,
            'currency': self.currency,
            'file_url': self.file_url,
            'file_name': self.file_name,
            'file_size_bytes': self.file_size_bytes,
            'file_type': self.file_type,
            'preview_images': self.preview_images or [],
            'tags': self.tags or [],
            'downloads_count': self.downloads_count,
            'views_count': self.views_count,
            'rating': self.rating,
            'rating_count': self.rating_count,
            'status': self.status,
            'is_boosted': self.is_boost_active(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_seller and self.seller:
            data['seller'] = self.seller.to_dict()
        return data

    def __repr__(self):
        return f'<MarketplaceListing id={self.id} "{self.title}" status={self.status}>'