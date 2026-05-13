"""
Balance Model — Real Money Layer
Balance represents REAL financial value inside the SF platform.

It is strictly separate from Crystals (visibility) and SF Coins (gamification).

Balance is used for:
  - Marketplace purchases (hiring contributors, buying services)
  - Contributor / mentor payouts
  - Crowdfunding contributions
  - Escrow (milestone payments held in trust)
  - Withdrawals to bank / Stripe

RULE: Balance must never be confused with Crystals.
      Balance = money. Crystals = visibility acceleration only.
"""

from datetime import datetime
from app.extensions import db


class Balance(db.Model):
    """
    One row per user. Stores the user's real-money wallet state.
    
    Fields:
      available       — funds the user can spend or withdraw right now
      pending         — funds waiting for confirmation (e.g. incoming Stripe payment)
      escrow_locked   — funds frozen for active milestone / collaboration payments
      total_deposited — lifetime deposits (audit trail)
      total_withdrawn — lifetime withdrawals (audit trail)
    """
    __tablename__ = 'balances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    # All amounts stored as integer CENTS (e.g. $10.50 → 1050) to avoid float drift
    available      = db.Column(db.Integer, default=0, nullable=False)  # spendable right now
    pending        = db.Column(db.Integer, default=0, nullable=False)  # awaiting confirmation
    escrow_locked  = db.Column(db.Integer, default=0, nullable=False)  # frozen for active escrow

    # Lifetime counters for analytics
    total_deposited  = db.Column(db.Integer, default=0, nullable=False)
    total_withdrawn  = db.Column(db.Integer, default=0, nullable=False)
    total_paid_out   = db.Column(db.Integer, default=0, nullable=False)  # sent to others

    currency = db.Column(db.String(3), default='USD', nullable=False)  # ISO 4217

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user             = db.relationship('User', back_populates='balance')
    transactions     = db.relationship('BalanceTransaction', back_populates='balance',
                                       cascade='all, delete-orphan')
    escrow_as_payer  = db.relationship('EscrowTransaction',
                                       foreign_keys='EscrowTransaction.payer_balance_id',
                                       back_populates='payer_balance',
                                       cascade='all, delete-orphan')
    escrow_as_payee  = db.relationship('EscrowTransaction',
                                       foreign_keys='EscrowTransaction.payee_balance_id',
                                       back_populates='payee_balance')

    # ------------------------------------------------------------------
    # Helper: amounts are always in cents
    # ------------------------------------------------------------------

    def deposit(self, cents: int, description: str = 'Deposit') -> 'BalanceTransaction':
        """
        Add real money to the available balance (e.g. from Stripe).
        Returns the recorded BalanceTransaction (caller must commit).
        """
        if cents <= 0:
            raise ValueError('Deposit amount must be positive')

        before = self.available
        self.available       += cents
        self.total_deposited += cents

        return BalanceTransaction.record(
            balance=self,
            tx_type='deposit',
            amount=cents,
            balance_before=before,
            balance_after=self.available,
            description=description,
        )

    def withdraw(self, cents: int, description: str = 'Withdrawal') -> 'BalanceTransaction':
        """
        Remove real money from the available balance (payout to bank/Stripe).
        Raises if insufficient funds.
        """
        if cents <= 0:
            raise ValueError('Withdrawal amount must be positive')
        if cents > self.available:
            raise ValueError(f'Insufficient balance. Available: {self.available} cents')

        before = self.available
        self.available       -= cents
        self.total_withdrawn += cents

        return BalanceTransaction.record(
            balance=self,
            tx_type='withdrawal',
            amount=cents,
            balance_before=before,
            balance_after=self.available,
            description=description,
        )

    def pay(self, cents: int, reference_type: str = None,
            reference_id: str = None, description: str = 'Payment') -> 'BalanceTransaction':
        """
        Deduct balance for a marketplace/mentorship/crowdfunding payment.
        Caller is responsible for crediting the recipient's balance separately.
        """
        if cents <= 0:
            raise ValueError('Payment amount must be positive')
        if cents > self.available:
            raise ValueError(f'Insufficient balance. Available: {self.available} cents')

        before = self.available
        self.available     -= cents
        self.total_paid_out += cents

        return BalanceTransaction.record(
            balance=self,
            tx_type='payment',
            amount=cents,
            balance_before=before,
            balance_after=self.available,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )

    def receive(self, cents: int, reference_type: str = None,
                reference_id: str = None, description: str = 'Received payment') -> 'BalanceTransaction':
        """
        Credit the available balance when receiving a payment (e.g. escrow release).
        """
        if cents <= 0:
            raise ValueError('Amount must be positive')

        before = self.available
        self.available       += cents
        self.total_deposited += cents  # counts as lifetime inflow

        return BalanceTransaction.record(
            balance=self,
            tx_type='receive',
            amount=cents,
            balance_before=before,
            balance_after=self.available,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )

    def lock_escrow(self, cents: int) -> None:
        """Move funds from available → escrow_locked (called when creating an escrow)."""
        if cents <= 0:
            raise ValueError('Escrow amount must be positive')
        if cents > self.available:
            raise ValueError(f'Insufficient balance for escrow. Available: {self.available} cents')
        self.available     -= cents
        self.escrow_locked += cents

    def release_escrow(self, cents: int) -> None:
        """Move funds from escrow_locked back to available (on cancellation)."""
        if cents > self.escrow_locked:
            raise ValueError('Cannot release more than locked escrow amount')
        self.escrow_locked -= cents
        self.available     += cents

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'currency': self.currency,
            # Expose amounts in dollars for the frontend (divide by 100)
            'available':       self.available / 100,
            'pending':         self.pending / 100,
            'escrow_locked':   self.escrow_locked / 100,
            'total_deposited': self.total_deposited / 100,
            'total_withdrawn': self.total_withdrawn / 100,
            'total_paid_out':  self.total_paid_out / 100,
            # Raw cents for internal use
            'available_cents':      self.available,
            'pending_cents':        self.pending,
            'escrow_locked_cents':  self.escrow_locked,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return (f'<Balance user_id={self.user_id} '
                f'available={self.available}¢ escrow={self.escrow_locked}¢>')


class BalanceTransaction(db.Model):
    """
    Immutable audit log of every real-money movement.

    Transaction types:
      deposit               — user tops up via Stripe / payment gateway
      withdrawal            — user cashes out to their bank
      payment               — user pays another user (marketplace, mentorship, crowdfunding)
      receive               — user receives a payment
      escrow_lock           — funds moved to escrow (awaiting milestone completion)
      escrow_release        — escrow released to payee after milestone approved
      escrow_refund         — escrow returned to payer (milestone rejected / cancelled)
      adjustment            — admin manual correction
    """
    __tablename__ = 'balance_transactions'

    id             = db.Column(db.Integer, primary_key=True)
    balance_id     = db.Column(db.Integer, db.ForeignKey('balances.id'), nullable=False)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    tx_type        = db.Column(db.String(30), nullable=False)   # see docstring above
    amount         = db.Column(db.Integer, nullable=False)       # in CENTS, always positive
    balance_before = db.Column(db.Integer, nullable=False)       # snapshot before
    balance_after  = db.Column(db.Integer, nullable=False)       # snapshot after

    status         = db.Column(db.String(20), default='completed')  # completed | pending | failed

    reference_type = db.Column(db.String(50), nullable=True)   # 'marketplace', 'escrow', 'mentorship', etc.
    reference_id   = db.Column(db.String(255), nullable=True)  # ID of the related entity
    description    = db.Column(db.Text, nullable=True)

    stripe_payment_id = db.Column(db.String(255), nullable=True)  # Stripe reference if applicable

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    balance = db.relationship('Balance', back_populates='transactions')
    user    = db.relationship('User', back_populates='balance_transactions')

    @staticmethod
    def record(balance: 'Balance', tx_type: str, amount: int,
               balance_before: int, balance_after: int,
               reference_type: str = None, reference_id: str = None,
               description: str = None, status: str = 'completed',
               stripe_payment_id: str = None) -> 'BalanceTransaction':
        """
        Factory — create and stage a transaction (caller must commit).
        Never updates balances itself — that is the caller's responsibility.
        """
        tx = BalanceTransaction(
            balance_id=balance.id,
            user_id=balance.user_id,
            tx_type=tx_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            status=status,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            stripe_payment_id=stripe_payment_id,
        )
        db.session.add(tx)
        return tx

    def to_dict(self):
        return {
            'id': str(self.id),
            'balance_id': str(self.balance_id),
            'user_id': str(self.user_id),
            'tx_type': self.tx_type,
            'amount': self.amount / 100,          # dollars
            'amount_cents': self.amount,
            'balance_before': self.balance_before / 100,
            'balance_after': self.balance_after / 100,
            'status': self.status,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'description': self.description,
            'stripe_payment_id': self.stripe_payment_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return (f'<BalanceTransaction id={self.id} '
                f'{self.tx_type} {self.amount}¢ user={self.user_id}>')