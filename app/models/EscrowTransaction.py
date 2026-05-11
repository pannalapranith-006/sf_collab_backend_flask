"""
EscrowTransaction Model — Milestone Payment Trust Layer
Escrow holds real-money Balance funds safely between a Payer (Founder)
and a Payee (Contributor / Mentor) while a milestone is in progress.

Flow:
  1. Founder creates escrow → funds move: available → escrow_locked
  2. Contributor completes milestone → status = 'pending_release'
  3. Founder approves → funds released to Contributor (escrow → available)
     OR
     Dispute / cancel → funds refunded to Founder (escrow → available)

Status lifecycle:
  created → funded → active → pending_release → released
                            ↘ disputed → released | refunded
                            ↘ cancelled → refunded
"""

from datetime import datetime
from app.extensions import db


class EscrowTransaction(db.Model):
    """
    One row represents one escrow agreement (e.g. one milestone payment).

    payer   = the person depositing funds (Founder)
    payee   = the person who will receive funds upon completion (Contributor/Mentor)
    """
    __tablename__ = 'escrow_transactions'

    id = db.Column(db.Integer, primary_key=True)

    # Parties
    payer_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    payee_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Linked balance rows (the Balance model holds the actual amounts)
    payer_balance_id = db.Column(db.Integer, db.ForeignKey('balances.id'), nullable=False)
    payee_balance_id = db.Column(db.Integer, db.ForeignKey('balances.id'), nullable=True)  # null until payee has balance row

    # Amount in CENTS (mirrors Balance model convention)
    amount_cents     = db.Column(db.Integer, nullable=False)
    currency         = db.Column(db.String(3), default='USD', nullable=False)

    # What this escrow is for
    reference_type   = db.Column(db.String(50), nullable=True)   # 'milestone', 'freelance', 'mentorship'
    reference_id     = db.Column(db.String(255), nullable=True)  # e.g. task_id or milestone_id
    title            = db.Column(db.String(255), nullable=True)  # human-readable label
    description      = db.Column(db.Text, nullable=True)

    # Status machine
    # created → funded → active → pending_release → released
    #                           ↘ disputed → released | refunded
    #                           ↘ cancelled → refunded
    status           = db.Column(db.String(30), default='created', nullable=False)

    # Optional deadline for milestone completion
    due_date         = db.Column(db.DateTime, nullable=True)

    # Timestamps for each status transition (audit trail)
    funded_at        = db.Column(db.DateTime, nullable=True)
    completed_at     = db.Column(db.DateTime, nullable=True)   # payee marked done
    approved_at      = db.Column(db.DateTime, nullable=True)   # payer approved
    released_at      = db.Column(db.DateTime, nullable=True)   # money sent
    disputed_at      = db.Column(db.DateTime, nullable=True)
    cancelled_at     = db.Column(db.DateTime, nullable=True)

    # Admin resolution note (for disputes)
    resolution_note  = db.Column(db.Text, nullable=True)
    resolved_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # admin id

    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payer         = db.relationship('User', foreign_keys=[payer_id],
                                    back_populates='escrows_as_payer')
    payee         = db.relationship('User', foreign_keys=[payee_id],
                                    back_populates='escrows_as_payee')
    payer_balance = db.relationship('Balance', foreign_keys=[payer_balance_id],
                                    back_populates='escrow_as_payer')
    payee_balance = db.relationship('Balance', foreign_keys=[payee_balance_id],
                                    back_populates='escrow_as_payee')

    # ------------------------------------------------------------------
    # Business Logic Methods
    # ------------------------------------------------------------------

    def fund(self):
        """
        Lock payer's funds: available → escrow_locked.
        Called immediately when escrow is created.
        Caller must commit.
        """
        from app.models.Balance import BalanceTransaction
        if self.status != 'created':
            raise ValueError(f'Cannot fund escrow in status: {self.status}')

        self.payer_balance.lock_escrow(self.amount_cents)
        self.status    = 'funded'
        self.funded_at = datetime.utcnow()

        # Record the lock as a balance transaction for audit purposes
        BalanceTransaction.record(
            balance=self.payer_balance,
            tx_type='escrow_lock',
            amount=self.amount_cents,
            balance_before=self.payer_balance.available + self.amount_cents,  # was higher before lock
            balance_after=self.payer_balance.available,
            reference_type='escrow',
            reference_id=str(self.id),
            description=f'Escrow funded: {self.title or self.reference_id}'
        )

    def mark_active(self):
        """Move to active state once both parties acknowledge."""
        if self.status != 'funded':
            raise ValueError(f'Cannot activate escrow in status: {self.status}')
        self.status = 'active'

    def request_release(self):
        """Payee signals milestone is complete — awaiting payer approval."""
        if self.status not in ('active', 'funded'):
            raise ValueError(f'Cannot request release from status: {self.status}')
        self.status       = 'pending_release'
        self.completed_at = datetime.utcnow()

    def release(self):
        """
        Payer approves — release escrow funds to payee.
        escrow_locked (payer) → available (payee).
        Caller must commit.
        """
        from app.models.Balance import Balance, BalanceTransaction
        if self.status not in ('pending_release', 'active'):
            raise ValueError(f'Cannot release escrow in status: {self.status}')

        # Deduct from payer escrow_locked
        if self.payer_balance.escrow_locked < self.amount_cents:
            raise ValueError('Escrow funds not found in payer locked balance')
        self.payer_balance.escrow_locked -= self.amount_cents

        # Ensure payee has a balance row
        if not self.payee_balance:
            payee_balance = Balance.query.filter_by(user_id=self.payee_id).first()
            if not payee_balance:
                payee_balance = Balance(user_id=self.payee_id)
                db.session.add(payee_balance)
                db.session.flush()
            self.payee_balance_id = payee_balance.id
            self.payee_balance    = payee_balance

        # Credit payee
        before = self.payee_balance.available
        self.payee_balance.available       += self.amount_cents
        self.payee_balance.total_deposited += self.amount_cents

        # Record on payee side
        BalanceTransaction.record(
            balance=self.payee_balance,
            tx_type='escrow_release',
            amount=self.amount_cents,
            balance_before=before,
            balance_after=self.payee_balance.available,
            reference_type='escrow',
            reference_id=str(self.id),
            description=f'Escrow released: {self.title or self.reference_id}'
        )

        self.status      = 'released'
        self.approved_at = datetime.utcnow()
        self.released_at = datetime.utcnow()

    def refund(self, reason: str = 'Cancelled'):
        """
        Return funds to payer (cancellation or dispute resolved for payer).
        escrow_locked → available (payer).
        Caller must commit.
        """
        from app.models.Balance import BalanceTransaction
        if self.status in ('released', 'refunded'):
            raise ValueError(f'Cannot refund escrow in status: {self.status}')

        self.payer_balance.release_escrow(self.amount_cents)

        # Audit record on payer side
        BalanceTransaction.record(
            balance=self.payer_balance,
            tx_type='escrow_refund',
            amount=self.amount_cents,
            balance_before=self.payer_balance.available - self.amount_cents,
            balance_after=self.payer_balance.available,
            reference_type='escrow',
            reference_id=str(self.id),
            description=f'Escrow refunded: {reason}'
        )

        self.status          = 'refunded'
        self.cancelled_at    = datetime.utcnow()
        self.resolution_note = reason

    def dispute(self, reason: str = ''):
        """Mark escrow as disputed — awaiting admin resolution."""
        if self.status not in ('active', 'pending_release'):
            raise ValueError(f'Cannot dispute escrow in status: {self.status}')
        self.status      = 'disputed'
        self.disputed_at = datetime.utcnow()
        if reason:
            self.resolution_note = reason

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self):
        return {
            'id': str(self.id),
            'payer_id': str(self.payer_id),
            'payee_id': str(self.payee_id),
            'amount': self.amount_cents / 100,
            'amount_cents': self.amount_cents,
            'currency': self.currency,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'funded_at': self.funded_at.isoformat() if self.funded_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'released_at': self.released_at.isoformat() if self.released_at else None,
            'disputed_at': self.disputed_at.isoformat() if self.disputed_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'resolution_note': self.resolution_note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return (f'<EscrowTransaction id={self.id} '
                f'{self.amount_cents}¢ status={self.status}>')