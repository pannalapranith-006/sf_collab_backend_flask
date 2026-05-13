from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.helper import error_response, success_response, paginate
from app.models.erp_activity import UserActivity
from datetime import datetime

activities_bp = Blueprint('activities', __name__)


@activities_bp.route('', methods=['GET'])
@jwt_required()
def get_activities():
    """Get all user activity records with filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    user_id = request.args.get('user_id', type=int)
    workspace_id = request.args.get('workspace_id', type=int)
    start_date = request.args.get('start_date', type=str)
    end_date = request.args.get('end_date', type=str)

    query = UserActivity.query

    if user_id:
        query = query.filter_by(user_id=user_id)

    if workspace_id:
        query = query.filter_by(workspace_id=workspace_id)

    if start_date:
        try:
            query = query.filter(UserActivity.last_activity >= datetime.fromisoformat(start_date))
        except ValueError:
            return error_response('Invalid start_date format', 400)

    if end_date:
        try:
            query = query.filter(UserActivity.last_activity <= datetime.fromisoformat(end_date))
        except ValueError:
            return error_response('Invalid end_date format', 400)

    result = paginate(query.order_by(UserActivity.last_activity.desc()), page, per_page)

    return success_response({
        'activities': [a.to_dict() for a in result['items']],
        'pagination': {
            'page':     result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
            'pages': result['pages'],
        }
    })


@activities_bp.route('/recent', methods=['GET'])
@jwt_required()
def get_recent_activities():
    """Get the most recently active user records."""
    limit = request.args.get('limit', 20, type=int)
    user_id = request.args.get('user_id', type=int)
    workspace_id = request.args.get('workspace_id', type=int)

    query = UserActivity.query

    if user_id:
        query = query.filter_by(user_id=user_id)

    if workspace_id:
        query = query.filter_by(workspace_id=workspace_id)

    activities = query.order_by(UserActivity.last_activity.desc()).limit(limit).all()

    return success_response({
        'activities': [a.to_dict() for a in activities]
    })


@activities_bp.route('/my-activities', methods=['GET'])
@jwt_required()
def get_my_activities():
    """Get current user's activity records."""
    current_user_id = get_jwt_identity()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    workspace_id = request.args.get('workspace_id', type=int)

    query = UserActivity.query.filter_by(user_id=current_user_id)

    if workspace_id:
        query = query.filter_by(workspace_id=workspace_id)

    result = paginate(query.order_by(UserActivity.last_activity.desc()), page, per_page)

    return success_response({
        'activities': [a.to_dict() for a in result['items']],
        'pagination': {
            'page':     result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
        }
    })


# Stats endpoint — kept commented out; requires db import + rework for UserActivity columns
# (UserActivity has no 'action' column; group-by would need to be on workspace_id or status)
#
# @activities_bp.route('/stats', methods=['GET'])
# @jwt_required()
# def get_activity_stats():
#     ...