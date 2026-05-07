from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.helper import success_response, error_response
from app.services.points_calculation_service import calculate_execution_points
from app.services.points_approval_service import approve_points, reject_points, hold_points
from app.services.consistency_service import calculate_daily_consistency, calculate_weekly_consistency
from app.middleware import workspace_admin_required
from app.models.erp_task import ErpTask
from app.models.execution_point import ExecutionPoint

points_bp = Blueprint('points', __name__)

@points_bp.route('/workspaces/<int:workspace_id>/tasks/<int:task_id>/calculate-points', methods=['POST'])
@jwt_required()
@workspace_admin_required
def trigger_points_calculation(workspace_id, task_id):
    task = ErpTask.query.get(task_id)
    if not task or task.workspace_id != workspace_id:
        return error_response(message='Task not found', status=404)
    try:
        result = calculate_execution_points(task_id)
        return success_response(message='Points calculated', data={
            'id': result.id,
            'final_points': result.final_points,
            'status': result.status
        })
    except ValueError as e:
        return error_response(message=str(e), status=400)

@points_bp.route('/workspaces/<int:workspace_id>/execution-points/<int:point_id>/approve', methods=['POST'])
@jwt_required()
@workspace_admin_required
def approve_execution_point(workspace_id, point_id):
    point = ExecutionPoint.query.get(point_id)
    if not point or point.workspace_id != workspace_id:
        return error_response(message='Execution point not found', status=404)
    data = request.get_json() or {}
    comment = data.get('comment')
    user_id = int(get_jwt_identity())
    try:
        point = approve_points(point_id, user_id, comment)
        return success_response(message='Points approved', data={
            'id': point.id,
            'status': point.status,
            'final_points': point.final_points
        })
    except ValueError as e:
        return error_response(message=str(e), status=400)

@points_bp.route('/workspaces/<int:workspace_id>/execution-points/<int:point_id>/reject', methods=['POST'])
@jwt_required()
@workspace_admin_required
def reject_execution_point(workspace_id, point_id):
    point = ExecutionPoint.query.get(point_id)
    if not point or point.workspace_id != workspace_id:
        return error_response(message='Execution point not found', status=404)
    data = request.get_json() or {}
    comment = data.get('comment')
    user_id = int(get_jwt_identity())
    try:
        point = reject_points(point_id, user_id, comment)
        return success_response(message='Points rejected', data={'id': point.id, 'status': point.status})
    except ValueError as e:
        return error_response(message=str(e), status=400)

@points_bp.route('/workspaces/<int:workspace_id>/execution-points/<int:point_id>/hold', methods=['POST'])
@jwt_required()
@workspace_admin_required
def hold_execution_point(workspace_id, point_id):
    point = ExecutionPoint.query.get(point_id)
    if not point or point.workspace_id != workspace_id:
        return error_response(message='Execution point not found', status=404)
    data = request.get_json() or {}
    comment = data.get('comment')
    user_id = int(get_jwt_identity())
    try:
        point = hold_points(point_id, user_id, comment)
        return success_response(message='Points held', data={'id': point.id, 'status': point.status})
    except ValueError as e:
        return error_response(message=str(e), status=400)

@points_bp.route('/workspaces/<int:workspace_id>/consistency/daily', methods=['POST'])
@jwt_required()
@workspace_admin_required
def trigger_daily_consistency(workspace_id):
    data = request.get_json() or {}
    date_str = data.get('date')
    target_date = None
    if date_str:
        from datetime import datetime as dt
        try:
            target_date = dt.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response(message='Invalid date format. Use YYYY-MM-DD.', status=400)
    count = calculate_daily_consistency(workspace_id, target_date)
    return success_response(message=f'Daily consistency calculated for {count} members.')

@points_bp.route('/workspaces/<int:workspace_id>/consistency/weekly', methods=['POST'])
@jwt_required()
@workspace_admin_required
def trigger_weekly_consistency(workspace_id):
    data = request.get_json() or {}
    date_str = data.get('week_end')
    week_end = None
    if date_str:
        from datetime import datetime as dt
        try:
            week_end = dt.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response(message='Invalid date format. Use YYYY-MM-DD.', status=400)
    try:
        awarded = calculate_weekly_consistency(workspace_id, week_end)
        return success_response(message=f'Weekly consistency calculated. {awarded} perfect week(s) awarded.')
    except ValueError as e:
        return error_response(message=str(e), status=400)