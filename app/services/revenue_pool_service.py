from datetime import date, datetime
from app import db
from app.models.revenue_pool import RevenuePool
from app.services.membership_audit_service import log_membership_action

def create_pool(workspace_id, period_start, period_end, gross_revenue=0, refunds=0, chargebacks=0, exclusions=0, team_share=40.0):
    """Create a new revenue pool for a workspace period (unique constraint enforced)."""
    eligible = max(gross_revenue - refunds - chargebacks - exclusions, 0)
    team_pool = round(eligible * (team_share / 100.0), 2)

    pool = RevenuePool(
        workspace_id=workspace_id,
        period_start=period_start,
        period_end=period_end,
        gross_revenue=gross_revenue,
        refunds_amount=refunds,
        chargebacks_amount=chargebacks,
        manual_exclusions_amount=exclusions,
        eligible_revenue=eligible,
        team_share_percentage=team_share,
        team_pool_amount=team_pool,
        status='open'
    )
    db.session.add(pool)
    db.session.commit()

    log_membership_action(
        'revenue_pool_created',
        workspace_id=workspace_id,
        details={
            'pool_id': pool.id,
            'period': f'{period_start} -> {period_end}',
            'eligible_revenue': eligible,
            'team_pool': team_pool
        }
    )
    return pool

def update_pool_financials(pool_id, gross_revenue=None, refunds=None, chargebacks=None, exclusions=None, team_share=None):
    """Update financial figures and recalculate eligible & team pool. Only in open/calculating states."""
    pool = RevenuePool.query.get(pool_id)
    if not pool:
        raise ValueError('Pool not found')
    if pool.status not in ['open', 'calculating']:
        raise ValueError('Pool can only be modified while open or calculating')

    if gross_revenue is not None:
        pool.gross_revenue = gross_revenue
    if refunds is not None:
        pool.refunds_amount = refunds
    if chargebacks is not None:
        pool.chargebacks_amount = chargebacks
    if exclusions is not None:
        pool.manual_exclusions_amount = exclusions
    if team_share is not None:
        pool.team_share_percentage = team_share

    pool.eligible_revenue = max(
        pool.gross_revenue - pool.refunds_amount - pool.chargebacks_amount - pool.manual_exclusions_amount,
        0
    )
    pool.team_pool_amount = round(pool.eligible_revenue * (pool.team_share_percentage / 100.0), 2)

    db.session.commit()
    log_membership_action('revenue_pool_updated', workspace_id=pool.workspace_id, details={'pool_id': pool.id})
    return pool

def lock_pool(pool_id):
    """Lock pool for payout calculation. Only from pending_admin_review state."""
    pool = RevenuePool.query.get(pool_id)
    if not pool:
        raise ValueError('Pool not found')
    if pool.status != 'pending_admin_review':
        raise ValueError('Pool must be in pending_admin_review state to lock')
    pool.status = 'locked'
    pool.locked_at = datetime.utcnow()
    db.session.commit()
    log_membership_action('revenue_pool_locked', workspace_id=pool.workspace_id, details={'pool_id': pool.id})
    return pool

def mark_pool_paid(pool_id):
    """Move from 'locked' to 'paid'."""
    pool = RevenuePool.query.get(pool_id)
    if not pool:
        raise ValueError('Pool not found')
    if pool.status != 'locked':
        raise ValueError('Only locked pools can be marked as paid')

    pool.status = 'paid'
    pool.paid_at = datetime.utcnow()

    db.session.commit()
    log_membership_action('revenue_pool_paid', workspace_id=pool.workspace_id,
                          details={'pool_id': pool.id})
    return pool

# Additional status transitions can be added later (archive, mark paid, etc.)