from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.erp_alert import ErpAlert
from app.models.workspace import Workspace
from app.services.erp_alert_engine import run_alert_jobs
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user,
    get_current_user_id,
    get_workspace_membership,
    is_global_admin,
)


erp_alerts_bp = Blueprint('erp_alerts', __name__)


def _parse_workspace_id(source='args'):
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


@erp_alerts_bp.route('/list', methods=['GET'])
@jwt_required()
def list_alerts():
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

    query = ErpAlert.query.filter_by(workspace_id=workspace_id)

    alert_type = request.args.get('type')
    if alert_type:
        if alert_type not in ('missing_update', 'late_attendance', 'task_overdue', 'inactive_user'):
            return error_response('Invalid type filter', 400)
        query = query.filter(ErpAlert.type == alert_type)

    resolved = request.args.get('resolved')
    if resolved is not None:
        if resolved.lower() not in ('true', 'false'):
            return error_response('resolved must be true or false', 400)
        query = query.filter(ErpAlert.resolved == (resolved.lower() == 'true'))

    limit_raw = request.args.get('limit', 50)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        return error_response('limit must be an integer', 400)

    if limit < 1:
        return error_response('limit must be >= 1', 400)

    limit = min(limit, 200)
    records = query.order_by(ErpAlert.created_at.desc()).limit(limit).all()

    return success_response({'workspace_id': workspace_id, 'count': len(records), 'alerts': [r.to_dict() for r in records]})


@erp_alerts_bp.route('/<int:alert_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_alert(alert_id):
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    alert = ErpAlert.query.get(alert_id)
    if not alert:
        return error_response('Alert not found', 404)

    _, err = _assert_admin_access(alert.workspace_id, user_id, user)
    if err:
        return err

    if alert.resolved:
        return error_response('Alert already resolved', 400, {'alert': alert.to_dict()})

    data = request.get_json(silent=True) or {}
    resolution_note = (data.get('resolution_note') or '').strip() or None

    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = user_id
    alert.resolution_note = resolution_note

    try:
        db.session.commit()
        return success_response({'alert': alert.to_dict()}, 'Alert resolved')
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to resolve alert: {exc}', 500)


@erp_alerts_bp.route('/run-jobs', methods=['POST'])
@jwt_required()
def run_jobs():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    data = request.get_json(silent=True) or {}
    workspace_id = data.get('workspace_id')

    if workspace_id is not None:
        try:
            workspace_id = int(workspace_id)
        except (TypeError, ValueError):
            return error_response('workspace_id must be an integer', 400)

        _, err = _assert_workspace_exists(workspace_id)
        if err:
            return err

        _, err = _assert_admin_access(workspace_id, user_id, user)
        if err:
            return err

    elif not is_global_admin(user):
        return error_response('workspace_id is required for non-global-admin users', 400)

    target_raw = data.get('date')
    target_date = None
    if target_raw:
        try:
            target_date = datetime.strptime(target_raw, '%Y-%m-%d').date()
        except ValueError:
            return error_response('date must be YYYY-MM-DD', 400)

    inactivity_days = data.get('inactivity_days', 3)
    try:
        inactivity_days = int(inactivity_days)
    except (TypeError, ValueError):
        return error_response('inactivity_days must be an integer', 400)

    if inactivity_days < 1 or inactivity_days > 60:
        return error_response('inactivity_days must be between 1 and 60', 400)

    try:
        totals = run_alert_jobs(workspace_id=workspace_id, target_date=target_date, inactivity_days=inactivity_days)
        return success_response({'workspace_id': workspace_id, 'date': (target_date.isoformat() if target_date else None), 'totals': totals}, 'Alert jobs executed')
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to run alert jobs: {exc}', 500)
