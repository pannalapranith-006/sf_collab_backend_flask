from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.helper import success_response, error_response
from app.services.daily_update_service import submit_update, get_updates
from app.middleware import workspace_member_required

daily_update_bp = Blueprint('daily_update', __name__)

@daily_update_bp.route('/workspaces/<int:workspace_id>/daily-update', methods=['POST'])
@jwt_required()
@workspace_member_required
def submit_update_route(workspace_id):
    user_id = int(get_jwt_identity())
    data = request.get_json()
    content = data.get('content', '').strip()
    if not content:
        return error_response(message='Content is required', status=400)

    try:
        update = submit_update(workspace_id, user_id, content)
        return success_response(message='Daily update submitted', data={
            'id': update.id,
            'date': update.log_date.isoformat(),
            'content': update.content
        })
    except ValueError as e:
        return error_response(message=str(e), status=400)

@daily_update_bp.route('/workspaces/<int:workspace_id>/daily-updates', methods=['GET'])
@jwt_required()
@workspace_member_required
def get_updates_route(workspace_id):
    user_id = request.args.get('user_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    from datetime import datetime
    start = None
    end = None
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            return error_response(message='start_date must be YYYY-MM-DD', status=400)
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return error_response(message='end_date must be YYYY-MM-DD', status=400)

    updates = get_updates(workspace_id, user_id, start, end)
    return success_response(message='Daily updates retrieved', data=[{
        'id': u.id,
        'user_id': u.user_id,
        'date': u.log_date.isoformat(),
        'content': u.content,
        'created_at': u.created_at.isoformat()
    } for u in updates])