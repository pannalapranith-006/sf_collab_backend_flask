import hashlib
import json
from datetime import datetime, date, timedelta
from app.extensions import db
from app.models.rp_job_status import JobStatus
from flask import current_app
from app.services.rp_event_emitter import emit_event  # reuse existing emitter if needed

def _idempotency_key(job_name: str, run_date: str) -> str:
    """Unique key for a job run (name + date)."""
    raw = f"{job_name}:{run_date}"
    return hashlib.sha256(raw.encode()).hexdigest()

def _should_skip(job_name: str, run_date: str):
    """Return True if job already completed successfully for this date."""
    run_id = _idempotency_key(job_name, run_date)
    existing = JobStatus.query.filter_by(run_id=run_id, status='completed').first()
    return existing is not None

def _start_job(job_name: str, run_date: str, payload: dict = None):
    run_id = _idempotency_key(job_name, run_date)
    job = JobStatus(
        job_name=job_name,
        run_id=run_id,
        run_count=0,          # explicitly set to 0
        payload=payload or {},
        )
    job.mark_started()
    db.session.add(job)
    db.session.commit()
    return job

def _fail_job(job: JobStatus, error: str):
    job.mark_failed(error)
    db.session.commit()

def _complete_job(job: JobStatus):
    job.mark_completed()
    db.session.commit()


# ── Job Implementations ───────────────────────────────────────

def daily_metric_builder(run_date: date):
    """
    Compute daily metrics (active users, tasks completed, etc.)
    Run once per day.
    """
    job_name = 'daily_metric_builder'
    run_date_str = run_date.isoformat()
    if _should_skip(job_name, run_date_str):
        return  # already done

    job = _start_job(job_name, run_date_str, {'date': run_date_str})
    try:
        # ACTUAL METRIC LOGIC (example)
        from app.models.rp_work_task import WorkTask
        completed_tasks = WorkTask.query.filter(
            db.func.date(WorkTask.updated_at) == run_date,
            WorkTask.status == 'approved'
        ).count()
        # ... more metrics ...
        # Store metrics in a dedicated metrics table if needed
        _complete_job(job)
        emit_event('daily_metrics_built', {'date': run_date_str, 'completed_tasks': completed_tasks})
    except Exception as e:
        _fail_job(job, str(e))
        raise


def warning_summary_job(run_date: date):
    """
    Aggregate warnings for dashboards.
    """
    job_name = 'warning_summary_job'
    run_date_str = run_date.isoformat()
    if _should_skip(job_name, run_date_str):
        return

    job = _start_job(job_name, run_date_str, {'date': run_date_str})
    try:
        # Logic here (dummy)
        _complete_job(job)
    except Exception as e:
        _fail_job(job, str(e))
        raise


def revenue_pool_close(run_date: date):
    """
    Close the revenue pool for a period.
    """
    job_name = 'revenue_pool_close'
    run_date_str = run_date.isoformat()
    if _should_skip(job_name, run_date_str):
        return

    job = _start_job(job_name, run_date_str)
    try:
        # Lock pool, etc.
        _complete_job(job)
    except Exception as e:
        _fail_job(job, str(e))
        raise


def payout_calculation_job(run_date: date):
    """
    Calculate payouts based on locked pools.
    """
    job_name = 'payout_calculation_job'
    run_date_str = run_date.isoformat()
    if _should_skip(job_name, run_date_str):
        return

    job = _start_job(job_name, run_date_str)
    try:
        # Payout logic
        _complete_job(job)
    except Exception as e:
        _fail_job(job, str(e))
        raise


def weekly_summary_builder(week_start: date):
    """
    Build a weekly summary.
    """
    job_name = 'weekly_summary_builder'
    run_date_str = week_start.isoformat()
    if _should_skip(job_name, run_date_str):
        return

    job = _start_job(job_name, run_date_str, {'week_start': run_date_str})
    try:
        # Summary logic
        _complete_job(job)
    except Exception as e:
        _fail_job(job, str(e))
        raise