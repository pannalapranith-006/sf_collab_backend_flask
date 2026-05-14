from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.erp_user_activity import ErpUserActivity
from app.models.workspace import Workspace
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user,
    get_current_user_id,
    get_workspace_membership,
    is_global_admin,
)


erp_activity_bp = Blueprint('erp_activity', __name__)


def _parse_workspace_id(source='json'):
    if source == 'json':
        raw = (request.get_json(silent=True) or {}).get('workspace_id')
    else:
        raw = request.args.get('workspace_id')

    if raw is None:
        return None, error_response('workspace_id is required', 400)

    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, error_response('workspace_id must be an integer', 400)


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


@erp_activity_bp.route('/heartbeat', methods=['POST'])
@jwt_required()
def heartbeat():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    workspace_id, err = _parse_workspace_id('json')
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    _, err = _assert_member_access(workspace_id, user_id, user)
    if err:
        return err

    record = ErpUserActivity.get_or_create(user_id, workspace_id)
    record.touch(request)

    now = datetime.utcnow()
    user.last_login = now
    user.last_activity_date = now.date()

    try:
        db.session.commit()
        return success_response({'activity': record.to_dict()}, 'Heartbeat recorded')
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to record heartbeat: {exc}', 500)


@erp_activity_bp.route('/me', methods=['GET'])
@jwt_required()
def my_activity():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    workspace_id, err = _parse_workspace_id('args')
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    _, err = _assert_member_access(workspace_id, user_id, user)
    if err:
        return err

    record = ErpUserActivity.query.filter_by(user_id=user_id, workspace_id=workspace_id).first()
    if not record:
        return success_response({
            'activity': {
                'user_id': user_id,
                'workspace_id': workspace_id,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'last_activity': None,
                'last_heartbeat': None,
                'status': 'unknown',
            }
        })

    return success_response({'activity': record.to_dict()})


@erp_activity_bp.route('/workspace', methods=['GET'])
@jwt_required()
def workspace_activity():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    workspace_id, err = _parse_workspace_id('args')
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    _, err = _assert_admin_access(workspace_id, user_id, user)
    if err:
        return err

    records = (ErpUserActivity.query
               .filter_by(workspace_id=workspace_id)
               .order_by(ErpUserActivity.last_activity.desc())
               .all())

    summary = {'active': 0, 'idle': 0, 'inactive': 0, 'dead': 0, 'unknown': 0, 'total': len(records)}
    payload = []

    for record in records:
        data = record.to_dict()
        status = data.get('status') or 'unknown'
        if status in summary:
            summary[status] += 1
        else:
            summary['unknown'] += 1

        if record.user:
            data['user'] = {
                'id': record.user.id,
                'name': f'{record.user.first_name} {record.user.last_name}'.strip(),
                'email': record.user.email,
            }
        payload.append(data)

    return success_response({
        'workspace_id': workspace_id,
        'summary': summary,
        'records': payload,
    })
