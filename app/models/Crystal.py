"""
Crystal Models — Visibility Acceleration Layer
IMPORTANT PLATFORM RULE:
  Crystals are NOT money. They CANNOT be used for payments.
  Crystals only provide temporary visibility boosts.

  Money  → Balance  (real financial value)
  Boosts → Crystals (temporary discovery acceleration)
  Trust  → Reputation system (separate)

Crystal uses (allowed):
  - visibility_boost      : general platform discovery boost (24h)
  - listing_promotion     : promote a startup listing
  - launch_promotion      : front-page launch promotion
  - mentor_priority       : rise higher in mentor matchmaking queue
  - project_boost         : feature a project in discovery

Crystal uses (NEVER allowed):
  - payments between users
  - marketplace purchases
  - unlocking access that money would unlock
  - affecting reputation scores directly

Crystals can be:
  - Purchased (real money → Crystals, handled via Stripe)
  - Earned via platform events / admin bonuses (limited amounts)
"""

from datetime import datetime
from app.extensions import db


# Valid usage types for Crystals — enforced at the model level
CRYSTAL_USAGE_TYPES = {
    'purchase',            # user buys crystals with real money (incoming)
    'admin_grant',         # admin awards crystals (incoming)
    'visibility_boost',    # general boost
    'listing_promotion',   # promote startup listing
    'launch_promotion',    # front-page launch slot
    'mentor_priority',     # matchmaking queue priority
    'project_boost',       # feature a project
    'event_reward',        # earned through platform event
    'refund',              # crystals returned after failed/expired boost
}

# Boost types that consume crystals — separate from earning types
CRYSTAL_SPEND_TYPES = {
    'visibility_boost',
    'listing_promotion',
    'launch_promotion',
    'mentor_priority',
    'project_boost',
}


class CrystalWallet(db.Model):
    """
    One row per user — holds the user's Crystal balance.
    Completely separate from UserWallet (SF Coins / Gems) and Balance (real money).
    """
    __tablename__ = 'crystal_wallets'

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    balance      = db.Column(db.Integer, default=0, nullable=False)  # current spendable crystals
    total_earned = db.Column(db.Integer, default=0, nullable=False)  # lifetime earned
    total_spent  = db.Column(db.Integer, default=0, nullable=False)  # lifetime spent on boosts

    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user         = db.relationship('User', back_populates='crystal_wallet')
    transactions = db.relationship('CrystalTransaction', back_populates='crystal_wallet',
                                   cascade='all, delete-orphan')
    boosts       = db.relationship('VisibilityBoost', back_populates='crystal_wallet',
                                   cascade='all, delete-orphan')

    # ------------------------------------------------------------------
    # Business Logic Methods
    # ------------------------------------------------------------------

    def add_crystals(self, amount: int, usage_type: str, description: str = None,
                     reference_id: str = None) -> 'CrystalTransaction':
        """
        Credit crystals to this wallet (purchase or admin grant).
        Returns the staged CrystalTransaction (caller must commit).
        """
        if amount <= 0:
            raise ValueError('Crystal amount must be positive')
        if usage_type not in CRYSTAL_USAGE_TYPES:
            raise ValueError(f'Invalid crystal usage type: {usage_type}')
        if usage_type in CRYSTAL_SPEND_TYPES:
            raise ValueError(f'Cannot use spend type "{usage_type}" to add crystals')

        before        = self.balance
        self.balance       += amount
        self.total_earned  += amount

        return CrystalTransaction.record(
            crystal_wallet=self,
            direction='credit',
            usage_type=usage_type,
            amount=amount,
            balance_before=before,
            balance_after=self.balance,
            description=description,
            reference_id=reference_id,
        )

    def spend_crystals(self, amount: int, usage_type: str, description: str = None,
                       reference_id: str = None) -> 'CrystalTransaction':
        """
        Deduct crystals for a visibility boost.
        Returns the staged CrystalTransaction (caller must commit).

        RULE: Can only be used for visibility/discovery acceleration.
              NOT for payments.
        """
        if amount <= 0:
            raise ValueError('Crystal amount must be positive')
        if usage_type not in CRYSTAL_SPEND_TYPES:
            raise ValueError(
                f'Invalid spend type "{usage_type}". '
                f'Crystals can only be used for: {", ".join(CRYSTAL_SPEND_TYPES)}'
            )
        if amount > self.balance:
            raise ValueError(
                f'Insufficient crystals. Balance: {self.balance}, required: {amount}'
            )

        before        = self.balance
        self.balance       -= amount
        self.total_spent   += amount

        return CrystalTransaction.record(
            crystal_wallet=self,
            direction='debit',
            usage_type=usage_type,
            amount=amount,
            balance_before=before,
            balance_after=self.balance,
            description=description,
            reference_id=reference_id,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'balance': self.balance,
            'total_earned': self.total_earned,
            'total_spent': self.total_spent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<CrystalWallet user_id={self.user_id} balance={self.balance}>'


class CrystalTransaction(db.Model):
    """
    Immutable audit log of every crystal movement.

    direction: 'credit' (earning) or 'debit' (spending on boost)
    usage_type: one of CRYSTAL_USAGE_TYPES
    """
    __tablename__ = 'crystal_transactions'

    id                = db.Column(db.Integer, primary_key=True)
    crystal_wallet_id = db.Column(db.Integer, db.ForeignKey('crystal_wallets.id'), nullable=False)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    direction      = db.Column(db.String(6), nullable=False)   # 'credit' | 'debit'
    usage_type     = db.Column(db.String(30), nullable=False)  # from CRYSTAL_USAGE_TYPES
    amount         = db.Column(db.Integer, nullable=False)     # always positive
    balance_before = db.Column(db.Integer, nullable=False)
    balance_after  = db.Column(db.Integer, nullable=False)

    reference_id   = db.Column(db.String(255), nullable=True)  # e.g. boost_id or stripe ref
    description    = db.Column(db.Text, nullable=True)

    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    crystal_wallet = db.relationship('CrystalWallet', back_populates='transactions')
    user           = db.relationship('User', back_populates='crystal_transactions')

    @staticmethod
    def record(crystal_wallet: CrystalWallet, direction: str, usage_type: str,
               amount: int, balance_before: int, balance_after: int,
               reference_id: str = None, description: str = None) -> 'CrystalTransaction':
        """Stage a transaction row. Caller must commit."""
        tx = CrystalTransaction(
            crystal_wallet_id=crystal_wallet.id,
            user_id=crystal_wallet.user_id,
            direction=direction,
            usage_type=usage_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reference_id=reference_id,
            description=description,
        )
        db.session.add(tx)
        return tx

    def to_dict(self):
        return {
            'id': str(self.id),
            'crystal_wallet_id': str(self.crystal_wallet_id),
            'user_id': str(self.user_id),
            'direction': self.direction,
            'usage_type': self.usage_type,
            'amount': self.amount,
            'balance_before': self.balance_before,
            'balance_after': self.balance_after,
            'reference_id': self.reference_id,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return (f'<CrystalTransaction id={self.id} '
                f'{self.direction} {self.amount} ({self.usage_type})>')


class VisibilityBoost(db.Model):
    """
    A single active (or expired) visibility boost purchased with Crystals.

    boost_type corresponds to where the boost applies:
      - 'listing_promotion'  → startup listing
      - 'launch_promotion'   → front-page launch
      - 'mentor_priority'    → mentor matchmaking
      - 'project_boost'      → project discovery
      - 'visibility_boost'   → general profile discovery

    is_active is True while the boost is running (expires_at > now).
    The background worker (Celery) should flip is_active=False when expired.
    """
    __tablename__ = 'visibility_boosts'

    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    crystal_wallet_id = db.Column(db.Integer, db.ForeignKey('crystal_wallets.id'), nullable=False)

    boost_type        = db.Column(db.String(30), nullable=False)  # matches CRYSTAL_SPEND_TYPES
    crystals_spent    = db.Column(db.Integer, nullable=False)

    # What entity is being boosted (e.g. startup_id, project_id)
    target_type       = db.Column(db.String(50), nullable=True)   # 'startup', 'project', 'profile'
    target_id         = db.Column(db.String(255), nullable=True)

    # Duration
    duration_hours    = db.Column(db.Integer, default=24, nullable=False)
    started_at        = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at        = db.Column(db.DateTime, nullable=False)

    is_active         = db.Column(db.Boolean, default=True)

    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user              = db.relationship('User', back_populates='visibility_boosts')
    crystal_wallet    = db.relationship('CrystalWallet', back_populates='boosts')

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def check_and_expire(self):
        """Lazily expire the boost if past its expiry time."""
        if self.is_active and self.is_expired():
            self.is_active = False
            db.session.commit()

    def to_dict(self):
        self.check_and_expire()
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'boost_type': self.boost_type,
            'crystals_spent': self.crystals_spent,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'duration_hours': self.duration_hours,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active and not self.is_expired(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return (f'<VisibilityBoost id={self.id} '
                f'{self.boost_type} active={self.is_active}>')
