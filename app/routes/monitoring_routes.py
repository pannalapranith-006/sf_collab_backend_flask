from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.utils.helper import success_response, error_response
from app.services.warning_engine import (
    scan_missing_attendance,
    scan_missing_updates,
    scan_overdue_tasks,
    scan_inactivity
)
from app.services.fraud_detection_service import run_all_fraud_checks
from app.middleware import workspace_admin_required

monitoring_bp = Blueprint('monitoring', __name__)

@monitoring_bp.route('/workspaces/<int:workspace_id>/monitor-updates', methods=['POST'])
@jwt_required()
@workspace_admin_required
def run_update_monitoring(workspace_id):
    data = request.get_json() or {}
    date_str = data.get('date')
    target_date = None
    if date_str:
        from datetime import datetime as dt
        try:
            target_date = dt.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response(message='Invalid date format. Use YYYY-MM-DD', status=400)
    results = scan_missing_updates(workspace_id, target_date)
    return success_response(message='Update monitoring completed', data=results)

@monitoring_bp.route('/workspaces/<int:workspace_id>/monitor-attendance', methods=['POST'])
@jwt_required()
@workspace_admin_required
def run_attendance_monitoring(workspace_id):
    data = request.get_json() or {}
    date_str = data.get('date')
    target_date = None
    if date_str:
        from datetime import datetime as dt
        try:
            target_date = dt.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response(message='Invalid date format. Use YYYY-MM-DD.', status=400)
    count = scan_missing_attendance(workspace_id, target_date)
    return success_response(message=f'{count} missing attendance warning(s) created.')

@monitoring_bp.route('/workspaces/<int:workspace_id>/monitor-tasks', methods=['POST'])
@jwt_required()
@workspace_admin_required
def run_task_monitoring(workspace_id):
    data = request.get_json() or {}
    date_str = data.get('date')
    current_date = None
    if date_str:
        from datetime import datetime as dt
        try:
            current_date = dt.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response(message='Invalid date format. Use YYYY-MM-DD.', status=400)
    count = scan_overdue_tasks(workspace_id, current_date)
    return success_response(message=f'{count} overdue task warning(s) created.')

@monitoring_bp.route('/workspaces/<int:workspace_id>/monitor-inactivity', methods=['POST'])
@jwt_required()
@workspace_admin_required
def run_inactivity_monitoring(workspace_id):
    data = request.get_json() or {}
    days = data.get('days', 7)
    try:
        days = int(days)
    except (ValueError, TypeError):
        return error_response(message='days must be an integer', status=400)
    count = scan_inactivity(workspace_id, days)
    return success_response(message=f'{count} inactivity warning(s) created.')

@monitoring_bp.route('/workspaces/<int:workspace_id>/fraud-check/all', methods=['POST'])
@jwt_required()
@workspace_admin_required
def run_all_fraud_checks_route(workspace_id):
    results = run_all_fraud_checks(workspace_id)
    return success_response(message='Fraud detection completed', data=results)