from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.holiday import Holiday
from app.models.workspace import Workspace
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user,
    get_current_user_id,
    get_workspace_membership,
    is_global_admin,
)


holiday_bp = Blueprint('holiday', __name__)


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


def _parse_date(date_raw):
    if not date_raw:
        return None, error_response('date is required', 400)

    try:
        return datetime.strptime(date_raw, '%Y-%m-%d').date(), None
    except ValueError:
        return None, error_response('date must be YYYY-MM-DD', 400)


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


@holiday_bp.route('/create', methods=['POST'])
@jwt_required()
def create_holiday():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()

    workspace_id, err = _parse_workspace_id('json')
    if err:
        return err

    if not name:
        return error_response('name is required', 400)

    holiday_date, err = _parse_date(data.get('date'))
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    _, err = _assert_admin_access(workspace_id, user_id, user)
    if err:
        return err

    existing = Holiday.query.filter_by(workspace_id=workspace_id, date=holiday_date).first()
    if existing:
        return error_response('Holiday already exists for this date', 400, {'holiday': existing.to_dict()})

    holiday = Holiday(workspace_id=workspace_id, date=holiday_date, name=name)

    try:
        db.session.add(holiday)
        db.session.commit()
        return success_response({'holiday': holiday.to_dict()}, 'Holiday created', 201)
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to create holiday: {exc}', 500)


@holiday_bp.route('/list', methods=['GET'])
@jwt_required()
def list_holidays():
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

    records = (Holiday.query
               .filter_by(workspace_id=workspace_id)
               .order_by(Holiday.date.asc())
               .all())

    return success_response({
        'workspace_id': workspace_id,
        'count': len(records),
        'holidays': [h.to_dict() for h in records],
    })


@holiday_bp.route('/<int:holiday_id>', methods=['DELETE'])
@jwt_required()
def delete_holiday(holiday_id):
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    holiday = Holiday.query.get(holiday_id)
    if not holiday:
        return error_response('Holiday not found', 404)

    _, err = _assert_admin_access(holiday.workspace_id, user_id, user)
    if err:
        return err

    try:
        holiday_data = holiday.to_dict()
        db.session.delete(holiday)
        db.session.commit()
        return success_response({'holiday': holiday_data}, 'Holiday deleted')
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to delete holiday: {exc}', 500)
