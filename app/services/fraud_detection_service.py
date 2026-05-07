from datetime import date, datetime, timedelta
from sqlalchemy import func
from app import db
from app.models.erp_task import ErpTask
from app.models.execution_point import ExecutionPoint
from app.models.revenue_pool import RevenuePool
from app.services.warning_service import create_warning

def _unresolved_fraud_warning_exists(user_id, workspace_id, type, reference_date=None, reference_id=None):
    from app.models.warning import Warning
    q = Warning.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        type=type,
        severity='admin_review',
        is_resolved=False
    )
    if reference_date:
        q = q.filter_by(reference_date=reference_date)
    if reference_id:
        q = q.filter_by(reference_id=reference_id)
    return q.first() is not None

def detect_duplicate_tasks(workspace_id, window_days=1):
    """
    Flags tasks that have the same title and assignee within a short time window.
    This could indicate task farming (creating many similar tasks for points).
    """
    cutoff = date.today() - timedelta(days=window_days)
    # find duplicate titles per assignee within the window
    dupes = db.session.query(
        ErpTask.title,
        ErpTask.assignee_id,
        func.count(ErpTask.id).label('cnt')
    ).filter(
        ErpTask.workspace_id == workspace_id,
        ErpTask.assignee_id.isnot(None),
        func.date(ErpTask.created_at) >= cutoff
    ).group_by(ErpTask.title, ErpTask.assignee_id).having(func.count(ErpTask.id) > 1).all()

    count = 0
    for title, assignee_id, cnt in dupes:
        if not _unresolved_fraud_warning_exists(assignee_id, workspace_id, 'duplicate_tasks', reference_date=date.today()):
            create_warning(
                user_id=assignee_id,
                workspace_id=workspace_id,
                type='duplicate_tasks',
                message=f'Created {cnt} tasks with the same title "{title}" in the last {window_days} day(s)',
                severity='admin_review',
                reference_date=date.today()
            )
            count += 1
    return count

def detect_task_farming(workspace_id, small_task_threshold=5, window_days=1):
    """
    Flags users who complete too many small tasks within a short time.
    small tasks = complexity 'small' and status 'approved'.
    """
    cutoff = date.today() - timedelta(days=window_days)
    small_tasks = db.session.query(
        ErpTask.assignee_id,
        func.count(ErpTask.id).label('cnt')
    ).filter(
        ErpTask.workspace_id == workspace_id,
        ErpTask.assignee_id.isnot(None),
        ErpTask.complexity == 'small',
        ErpTask.status == 'approved',
        ErpTask.updated_at >= cutoff
    ).group_by(ErpTask.assignee_id).having(func.count(ErpTask.id) >= small_task_threshold).all()

    count = 0
    for assignee_id, cnt in small_tasks:
        if not _unresolved_fraud_warning_exists(assignee_id, workspace_id, 'task_farming', reference_date=date.today()):
            create_warning(
                user_id=assignee_id,
                workspace_id=workspace_id,
                type='task_farming',
                message=f'Completed {cnt} small tasks in the last {window_days} day(s)',
                severity='admin_review',
                reference_date=date.today()
            )
            count += 1
    return count

def detect_point_spikes(workspace_id, spike_factor=3):
    """
    Compares current month's points to last month's. If user's points increased
    by more than spike_factor times, flag as point spike.
    We'll check against the latest locked pool's period.
    """
    # find current open/calculating pool (this month's period)
    current_pool = RevenuePool.query.filter(
        RevenuePool.workspace_id == workspace_id,
        RevenuePool.status.in_(['open', 'calculating'])
    ).order_by(RevenuePool.period_start.desc()).first()

    if not current_pool:
        return 0  # no active pool, can't compare

    # get users' approved points for current period vs previous period
    current_points = db.session.query(
        ExecutionPoint.user_id,
        func.sum(ExecutionPoint.final_points).label('total')
    ).filter(
        ExecutionPoint.workspace_id == workspace_id,
        ExecutionPoint.status == 'approved',
        ExecutionPoint.created_at >= current_pool.period_start,
        ExecutionPoint.created_at <= current_pool.period_end
    ).group_by(ExecutionPoint.user_id).all()

    # previous pool (last locked/paid/archived)
    previous_pool = RevenuePool.query.filter(
        RevenuePool.workspace_id == workspace_id,
        RevenuePool.id != current_pool.id,
        RevenuePool.status.in_(['locked', 'paid', 'archived'])
    ).order_by(RevenuePool.period_end.desc()).first()

    count = 0
    for user_id, curr_total in current_points:
        if not previous_pool:
            break
        prev_points = db.session.query(func.sum(ExecutionPoint.final_points)).filter(
            ExecutionPoint.user_id == user_id,
            ExecutionPoint.workspace_id == workspace_id,
            ExecutionPoint.status == 'approved',
            ExecutionPoint.created_at >= previous_pool.period_start,
            ExecutionPoint.created_at <= previous_pool.period_end
        ).scalar() or 0

        if prev_points > 0 and curr_total / prev_points >= spike_factor:
            if not _unresolved_fraud_warning_exists(user_id, workspace_id, 'point_spike', reference_date=date.today()):
                create_warning(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    type='point_spike',
                    message=f'Point total jumped from {prev_points:.1f} to {curr_total:.1f} (more than {spike_factor}x)',
                    severity='admin_review',
                    reference_date=date.today()
                )
                count += 1
    return count

def detect_payout_concentration(workspace_id, threshold=50.0):
    """
    Flags if any user accumulates more than threshold% of total approved points
    in the current (open/calculating) revenue pool.
    """
    current_pool = RevenuePool.query.filter(
        RevenuePool.workspace_id == workspace_id,
        RevenuePool.status.in_(['open', 'calculating'])
    ).order_by(RevenuePool.period_start.desc()).first()

    if not current_pool:
        return 0

    points = db.session.query(
        ExecutionPoint.user_id,
        func.sum(ExecutionPoint.final_points).label('total')
    ).filter(
        ExecutionPoint.workspace_id == workspace_id,
        ExecutionPoint.status == 'approved',
        ExecutionPoint.created_at >= current_pool.period_start,
        ExecutionPoint.created_at <= current_pool.period_end
    ).group_by(ExecutionPoint.user_id).all()

    total_points = sum(p.total for p in points)
    if total_points == 0:
        return 0

    count = 0
    for user_id, user_total in points:
        pct = (user_total / total_points) * 100
        if pct >= threshold:
            if not _unresolved_fraud_warning_exists(user_id, workspace_id, 'payout_concentration', reference_date=date.today()):
                create_warning(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    type='payout_concentration',
                    message=f'User has {pct:.1f}% of total approved points (threshold {threshold}%)',
                    severity='admin_review',
                    reference_date=date.today()
                )
                count += 1
    return count

def run_all_fraud_checks(workspace_id):
    """Run all fraud detectors and return summary counts."""
    return {
        'duplicate_tasks': detect_duplicate_tasks(workspace_id),
        'task_farming': detect_task_farming(workspace_id),
        'point_spikes': detect_point_spikes(workspace_id),
        'payout_concentration': detect_payout_concentration(workspace_id),
    }