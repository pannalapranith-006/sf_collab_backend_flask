from flask import Blueprint
from flask_jwt_extended import jwt_required
from app.utils.helper import success_response, error_response
from app.services.scheduler_service import (
    run_daily_attendance_warnings,
    run_daily_missing_updates,
    run_monthly_revenue_calculation,
    run_monthly_payout_generation,
)
from app.middleware import any_admin_required

scheduler_bp = Blueprint('scheduler', __name__)

@scheduler_bp.route('/admin/jobs/daily/attendance-warnings', methods=['POST'])
@jwt_required()
@any_admin_required
def trigger_daily_attendance():
    try:
        result = run_daily_attendance_warnings()
        return success_response(message='Daily attendance warnings run', data=result)
    except Exception as e:
        return error_response(message=str(e), status=500)

@scheduler_bp.route('/admin/jobs/daily/missing-updates', methods=['POST'])
@jwt_required()
@any_admin_required
def trigger_daily_missing_updates():
    try:
        result = run_daily_missing_updates()
        return success_response(message='Daily missing updates run', data=result)
    except Exception as e:
        return error_response(message=str(e), status=500)

@scheduler_bp.route('/admin/jobs/monthly/revenue-calculation', methods=['POST'])
@jwt_required()
@any_admin_required
def trigger_monthly_revenue():
    try:
        result = run_monthly_revenue_calculation()
        return success_response(message='Monthly revenue calculation run', data=result)
    except Exception as e:
        return error_response(message=str(e), status=500)

@scheduler_bp.route('/admin/jobs/monthly/payout-generation', methods=['POST'])
@jwt_required()
@any_admin_required
def trigger_monthly_payout():
    try:
        result = run_monthly_payout_generation()
        return success_response(message='Monthly payout generation run', data=result)
    except Exception as e:
        return error_response(message=str(e), status=500)