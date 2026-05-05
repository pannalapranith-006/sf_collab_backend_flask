from datetime import datetime
from app import db

class RevenuePool(db.Model):
    __tablename__ = 'revenue_pools'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    gross_revenue = db.Column(db.Float, default=0.0, nullable=False)
    refunds_amount = db.Column(db.Float, default=0.0, nullable=False)
    chargebacks_amount = db.Column(db.Float, default=0.0, nullable=False)
    manual_exclusions_amount = db.Column(db.Float, default=0.0, nullable=False)
    eligible_revenue = db.Column(db.Float, default=0.0, nullable=False)
    team_share_percentage = db.Column(db.Float, default=40.0, nullable=False)
    team_pool_amount = db.Column(db.Float, default=0.0, nullable=False)
    status = db.Column(db.String(20), default='open')   # open, calculating, pending_admin_review, locked, payouts_generated, paid, archived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    locked_at = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)

    workspace = db.relationship('Workspace', backref='revenue_pools')

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'period_start', 'period_end', name='uq_revenue_pool_period'),
    )