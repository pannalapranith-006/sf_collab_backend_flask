from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.helper import success_response, error_response
from app.services.attendance_service import clock_in, clock_out, mark_absentees
from app.middleware import workspace_member_required, workspace_admin_required

attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('/workspaces/<int:workspace_id>/clock-in', methods=['POST'])
@jwt_required()
@workspace_member_required
def clock_in_route(workspace_id):
    user_id = int(get_jwt_identity())
    try:
        clock_in(workspace_id, user_id)
        return success_response(message='Clocked in successfully')
    except ValueError as e:
        return error_response(message=str(e), status=400)

@attendance_bp.route('/workspaces/<int:workspace_id>/clock-out', methods=['POST'])
@jwt_required()
@workspace_member_required
def clock_out_route(workspace_id):
    user_id = int(get_jwt_identity())
    try:
        clock_out(workspace_id, user_id)
        return success_response(message='Clocked out successfully')
    except ValueError as e:
        return error_response(message=str(e), status=400)

@attendance_bp.route('/workspaces/<int:workspace_id>/mark-absent', methods=['POST'])
@jwt_required()
@workspace_admin_required
def mark_absent_route(workspace_id):
    data = request.get_json() or {}
    target_date_str = data.get('date')
    try:
        if target_date_str:
            from datetime import datetime as dt
            target_date = dt.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = None
    except ValueError:
        return error_response(message='Invalid date format. Use YYYY-MM-DD.', status=400)

    count = mark_absentees(workspace_id, target_date)
    return success_response(message=f'{count} absent record(s) created.')
