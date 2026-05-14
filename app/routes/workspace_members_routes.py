from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.helper import success_response, error_response
from app.services.membership_service import add_member, remove_member, update_role
from app.middleware import workspace_admin_required

workspace_members_bp = Blueprint('workspace_members', __name__)

@workspace_members_bp.route('/workspaces/<int:workspace_id>/members', methods=['POST'])
@jwt_required()
@workspace_admin_required
def add_member_route(workspace_id):
    data = request.get_json()
    user_id = data.get('user_id')
    role = data.get('role', 'member')
    if not user_id:
        return error_response(message='user_id is required', status=400)
    try:
        add_member(workspace_id, user_id, role,
                   admin_user_id=int(get_jwt_identity()))
        return success_response(message='Member added successfully')
    except ValueError as e:
        return error_response(message=str(e), status=400)

@workspace_members_bp.route('/workspaces/<int:workspace_id>/members/<int:user_id>', methods=['DELETE'])
@jwt_required()
@workspace_admin_required
def remove_member_route(workspace_id, user_id):
    try:
        remove_member(workspace_id, user_id)
        return success_response(message='Member removed successfully')
    except ValueError as e:
        return error_response(message=str(e), status=404)

@workspace_members_bp.route('/workspaces/<int:workspace_id>/members/<int:user_id>/role', methods=['PUT'])
@jwt_required()
@workspace_admin_required
def update_role_route(workspace_id, user_id):
    data = request.get_json()
    new_role = data.get('role')
    if not new_role:
        return error_response(message='role is required', status=400)
    try:
        update_role(workspace_id, user_id, new_role)
        return success_response(message='Role updated successfully')
    except ValueError as e:
        return error_response(message=str(e), status=400)