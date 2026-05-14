from datetime import datetime, timedelta

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.services.erp_analytics_service import user_kpis, workspace_kpis
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user,
    get_current_user_id,
    get_workspace_membership,
    is_global_admin,
)


erp_analytics_bp = Blueprint('erp_analytics', __name__)


def _parse_workspace_id():
    raw = request.args.get('workspace_id')
    if raw is None:
        return None, error_response('workspace_id is required', 400)

    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, error_response('workspace_id must be an integer', 400)


def _parse_dates():
    end_raw = request.args.get('end_date')
    start_raw = request.args.get('start_date')

    if end_raw:
        try:
            end_date = datetime.strptime(end_raw, '%Y-%m-%d').date()
        except ValueError:
            return None, None, error_response('end_date must be YYYY-MM-DD', 400)
    else:
        end_date = datetime.utcnow().date()

    if start_raw:
        try:
            start_date = datetime.strptime(start_raw, '%Y-%m-%d').date()
        except ValueError:
            return None, None, error_response('start_date must be YYYY-MM-DD', 400)
    else:
        start_date = end_date - timedelta(days=29)

    if start_date > end_date:
        return None, None, error_response('start_date cannot be after end_date', 400)

    return start_date, end_date, None


def _assert_workspace_exists(workspace_id):
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        return None, error_response('Workspace not found', 404)
    return workspace, None


def _assert_member_access(workspace_id, user_id, user):
    membership = get_workspace_membership(workspace_id, user_id)
    if membership or is_global_admin(user):
        return membership, None
    return None, error_response('Unauthorized to access this workspace', 403)


def _assert_admin_access(workspace_id, user_id, user):
    membership = get_workspace_membership(workspace_id, user_id)
    role = membership.role.value if (membership and hasattr(membership.role, 'value')) else (membership.role if membership else None)
    if role == 'admin' or is_global_admin(user):
        return membership, None
    return None, error_response('Admin access required', 403)


@erp_analytics_bp.route('/workspace', methods=['GET'])
@jwt_required()
def workspace_analytics():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    workspace_id, err = _parse_workspace_id()
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    _, err = _assert_member_access(workspace_id, user_id, user)
    if err:
        return err

    start_date, end_date, err = _parse_dates()
    if err:
        return err

    metrics = workspace_kpis(workspace_id, start_date, end_date)

    return success_response({
        'workspace_id': workspace_id,
        'date_start': start_date.isoformat(),
        'date_end': end_date.isoformat(),
        'metrics': metrics,
    })


@erp_analytics_bp.route('/user/<int:target_user_id>', methods=['GET'])
@jwt_required()
def user_analytics(target_user_id):
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    workspace_id, err = _parse_workspace_id()
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    caller_membership, err = _assert_member_access(workspace_id, user_id, user)
    if err:
        return err

    target_membership = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        user_id=target_user_id,
        status='active',
    ).first()
    if not target_membership:
        return error_response('Target user is not an active member of this workspace', 404)

    caller_role = caller_membership.role.value if (caller_membership and hasattr(caller_membership.role, 'value')) else (caller_membership.role if caller_membership else None)
    is_admin_or_global = caller_role == 'admin' or is_global_admin(user)

    if not is_admin_or_global and user_id != target_user_id:
        return error_response('Admin access required for other user analytics', 403)

    start_date, end_date, err = _parse_dates()
    if err:
        return err

    metrics = user_kpis(target_user_id, workspace_id, start_date, end_date)

    return success_response({
        'workspace_id': workspace_id,
        'user_id': target_user_id,
        'date_start': start_date.isoformat(),
        'date_end': end_date.isoformat(),
        'metrics': metrics,
    })
