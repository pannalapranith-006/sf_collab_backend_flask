from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import date, timedelta

from app.services.rp_batch_jobs import (
    daily_metric_builder,
    warning_summary_job,
    revenue_pool_close,
    payout_calculation_job,
    weekly_summary_builder,
)
from app.models.rp_job_status import JobStatus

batch_bp = Blueprint('batch', __name__)


def _parse_date(json_data, key='date', default_today=True):
    """Extract date from JSON body, default to today."""
    if json_data and key in json_data:
        return date.fromisoformat(json_data[key])
    return date.today() if default_today else None


# ── Job Trigger Endpoints ───────────────────────────────────

@batch_bp.route('/jobs/daily-metrics', methods=['POST'])
@jwt_required()
def trigger_daily_metrics():
    run_date = _parse_date(request.get_json())
    daily_metric_builder(run_date)
    return jsonify({'message': f'Daily metrics job triggered for {run_date}'}), 200

@batch_bp.route('/jobs/warning-summary', methods=['POST'])
@jwt_required()
def trigger_warning_summary():
    run_date = _parse_date(request.get_json())
    warning_summary_job(run_date)
    return jsonify({'message': f'Warning summary job triggered for {run_date}'}), 200

@batch_bp.route('/jobs/revenue-pool-close', methods=['POST'])
@jwt_required()
def trigger_revenue_pool_close():
    run_date = _parse_date(request.get_json())
    revenue_pool_close(run_date)
    return jsonify({'message': f'Revenue pool close job triggered for {run_date}'}), 200

@batch_bp.route('/jobs/payout-calculation', methods=['POST'])
@jwt_required()
def trigger_payout_calc():
    run_date = _parse_date(request.get_json())
    payout_calculation_job(run_date)
    return jsonify({'message': f'Payout calculation job triggered for {run_date}'}), 200

@batch_bp.route('/jobs/weekly-summary', methods=['POST'])
@jwt_required()
def trigger_weekly_summary():
    data = request.get_json() or {}
    if 'week_start' in data:
        week_start = date.fromisoformat(data['week_start'])
    else:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    weekly_summary_builder(week_start)
    return jsonify({'message': f'Weekly summary job triggered for week starting {week_start}'}), 200


# ── Status / Inspection Endpoint ────────────────────────────

@batch_bp.route('/jobs/status', methods=['GET'])
@jwt_required()
def get_job_statuses():
    """Return all job runs, newest first."""
    jobs = JobStatus.query.order_by(JobStatus.created_at.desc()).limit(50).all()
    return jsonify([{
        'job_name': j.job_name,
        'run_id': j.run_id,
        'status': j.status,
        'started_at': j.started_at.isoformat() if j.started_at else None,
        'completed_at': j.completed_at.isoformat() if j.completed_at else None,
        'run_count': j.run_count,
        'error_message': j.error_message,
    } for j in jobs]), 200