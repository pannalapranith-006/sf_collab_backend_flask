from datetime import date, datetime, timedelta
from app import db
from app.models.job_log import JobLog
from app.models.workspace import Workspace
from app.services.warning_engine import (
    scan_missing_attendance,
    scan_missing_updates
)
from app.services.revenue_pool_service import calculate_pool
# from app.services.payout_service import generate_payouts   # will be added later

def _start_job(job_name, workspace_id=None):
    log = JobLog(job_name=job_name, workspace_id=workspace_id, status='started')
    db.session.add(log)
    db.session.commit()
    return log

def _complete_job(log, details=None):
    log.status = 'completed'
    log.completed_at = datetime.utcnow()
    if details:
        log.details = details
    db.session.commit()

def _fail_job(log, error_msg):
    log.status = 'failed'
    log.completed_at = datetime.utcnow()
    log.details = {'error': error_msg}
    db.session.commit()

# -------------------------------------------------------------------
# Daily jobs – run once per day (early morning) for all workspaces
# -------------------------------------------------------------------
def run_daily_attendance_warnings():
    """Scan yesterday's missing attendance for all workspaces."""
    yesterday = date.today() - timedelta(days=1)
    workspaces = Workspace.query.all()
    results = {}
    for ws in workspaces:
        log = _start_job('daily_attendance_warnings', ws.id)
        try:
            count = scan_missing_attendance(ws.id, target_date=yesterday)
            _complete_job(log, {'warnings_created': count, 'for_date': yesterday.isoformat()})
            results[ws.id] = count
        except Exception as e:
            _fail_job(log, str(e))
            results[ws.id] = 0
    return results

def run_daily_missing_updates():
    """Scan yesterday's missing/late updates for all workspaces."""
    yesterday = date.today() - timedelta(days=1)
    workspaces = Workspace.query.all()
    results = {}
    for ws in workspaces:
        log = _start_job('daily_missing_updates', ws.id)
        try:
            warnings = scan_missing_updates(ws.id, target_date=yesterday)
            _complete_job(log, {'warnings': warnings, 'for_date': yesterday.isoformat()})
            results[ws.id] = warnings
        except Exception as e:
            _fail_job(log, str(e))
            results[ws.id] = {}
    return results

# -------------------------------------------------------------------
# Monthly jobs – run at the start of a new month for the previous month
# -------------------------------------------------------------------
def run_monthly_revenue_calculation():
    """
    For each workspace, find the latest open/calculating pool for the
    previous month and calculate it. (Actually should find the pool
    for the month just ended and move it from open→calculating.)
    """
    today = date.today()
    workspaces = Workspace.query.all()
    results = {}
    for ws in workspaces:
        log = _start_job('monthly_revenue_calc', ws.id)
        try:
            from app.models.revenue_pool import RevenuePool
            pools = RevenuePool.query.filter(
                RevenuePool.workspace_id == ws.id,
                RevenuePool.status == 'open',
                RevenuePool.period_end <= today
            ).all()
            for pool in pools:
                calculate_pool(pool.id)
            _complete_job(log, {'pools_calculated': len(pools)})
            results[ws.id] = len(pools)
        except Exception as e:
            _fail_job(log, str(e))
            results[ws.id] = 0
    return results

def run_monthly_payout_generation():
    """
    Generate payouts for locked pools that haven't had payouts generated yet.
    Placeholder – to be implemented when Payout Calculation Engine is ready.
    """
    workspaces = Workspace.query.all()
    results = {}
    for ws in workspaces:
        log = _start_job('monthly_payout_generation', ws.id)
        try:
            # TODO: call payout generation service
            _complete_job(log, {'payouts_generated': 0})
            results[ws.id] = 0
        except Exception as e:
            _fail_job(log, str(e))
            results[ws.id] = 0
    return results