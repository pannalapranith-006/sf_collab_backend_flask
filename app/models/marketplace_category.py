"""
MarketplaceCategory Model — SF Marketplace
Fixed categories seeded on first run.
Every category must answer: "Does this help someone build or launch a startup?"

Allowed top-level categories (per SF Economy docs):
  Development — code snippets, SaaS boilerplates, integrations, scripts, components
  Design      — UI kits, landing templates, design systems, startup visual assets
  Product     — research templates, pitch decks, planning frameworks, datasets
  Growth      — SEO tools, ad creatives, funnel templates, growth playbooks
"""

from datetime import datetime
from app.extensions import db
from sqlalchemy import JSON


class MarketplaceCategory(db.Model):
    __tablename__ = 'marketplace_categories'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)  # e.g. "Development"
    slug        = db.Column(db.String(100), unique=True, nullable=False)  # e.g. "development"
    description = db.Column(db.Text, nullable=True)
    icon        = db.Column(db.String(50), nullable=True)   # lucide icon name for frontend
    sort_order  = db.Column(db.Integer, default=0)

    # Sub-types allowed within this category (JSON list of strings)
    # e.g. ["code snippets", "SaaS boilerplates", "integrations"]
    allowed_types = db.Column(JSON, default=list)

    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    listings = db.relationship('MarketplaceListing', back_populates='category')

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'icon': self.icon,
            'allowed_types': self.allowed_types or [],
            'listing_count': len([l for l in self.listings if l.is_active and l.status == 'published']),
        }

    def __repr__(self):
        return f'<MarketplaceCategory {self.name}>'


# ------------------------------------------------------------------
# Seed data — call seed_categories() inside Flask app factory
# after db.create_all() or migration
# ------------------------------------------------------------------

CATEGORY_SEED = [
    {
        'name': 'Development',
        'slug': 'development',
        'description': 'Code snippets, SaaS boilerplates, integrations, scripts, and reusable components that accelerate startup development.',
        'icon': 'Code2',
        'sort_order': 1,
        'allowed_types': [
            'code snippets',
            'SaaS boilerplates',
            'integrations',
            'scripts',
            'reusable components',
        ]
    },
    {
        'name': 'Design',
        'slug': 'design',
        'description': 'UI kits, landing page templates, design systems, and visual assets built for startup products.',
        'icon': 'Palette',
        'sort_order': 2,
        'allowed_types': [
            'UI kits',
            'landing page templates',
            'design systems',
            'startup visual assets',
        ]
    },
    {
        'name': 'Product',
        'slug': 'product',
        'description': 'Research templates, pitch deck templates, planning frameworks, and structured datasets for product teams.',
        'icon': 'LayoutDashboard',
        'sort_order': 3,
        'allowed_types': [
            'research templates',
            'pitch deck templates',
            'planning frameworks',
            'structured datasets',
        ]
    },
    {
        'name': 'Growth',
        'slug': 'growth',
        'description': 'SEO tools, ad creatives, funnel templates, and growth playbooks for startup traction.',
        'icon': 'TrendingUp',
        'sort_order': 4,
        'allowed_types': [
            'SEO tools',
            'ad creatives',
            'funnel templates',
            'growth playbooks',
        ]
    },
]


def seed_categories():
    """
    Seed the marketplace categories if they don't exist yet.
    Call this once from the Flask app factory or a CLI command.
    """
    from app.extensions import db
    for data in CATEGORY_SEED:
        existing = MarketplaceCategory.query.filter_by(slug=data['slug']).first()
        if not existing:
            cat = MarketplaceCategory(**data)
            db.session.add(cat)
    db.session.commit()
    print('[Marketplace] Categories seeded.')