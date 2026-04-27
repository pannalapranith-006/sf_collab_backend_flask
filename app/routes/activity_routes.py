from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.helper import error_response, success_response
from datetime import datetime, timedelta

activities_bp = Blueprint('activities', __name__)

# NOTE: The Activity model does not exist in this codebase.
# These endpoints return empty/stub responses so the app boots correctly.
# Replace with real implementation once an Activity model is created.

@activities_bp.route('', methods=['GET'])
@jwt_required()
def get_activities():
    """Get all activities — stubbed until Activity model exists"""
    return success_response({
        'activities': [],
        'pagination': {'page': 1, 'per_page': 10, 'total': 0, 'pages': 0}
    })


@activities_bp.route('/recent', methods=['GET'])
@jwt_required()
def get_recent_activities():
    """Get recent activities — stubbed until Activity model exists"""
    return success_response({'activities': []})


@activities_bp.route('/my-activities', methods=['GET'])
@jwt_required()
def get_my_activities():
    """Get current user's activities — stubbed until Activity model exists"""
    return success_response({
        'activities': [],
        'pagination': {'page': 1, 'per_page': 10, 'total': 0, 'pages': 0}
    })