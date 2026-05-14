from datetime import date, datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.daily_update import DailyUpdate
from app.models.erp_alert import ErpAlert
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user,
    get_current_user_id,
    get_workspace_membership,
    is_global_admin,
)


updates_bp = Blueprint('updates', __name__)


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


@updates_bp.route('/submit', methods=['POST'])
@jwt_required()
def submit_update():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    data = request.get_json(silent=True) or {}
    workspace_id, err = _parse_workspace_id('json')
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    _, err = _assert_member_access(workspace_id, user_id, user)
    if err:
        return err

    today_work = (data.get('today_work') or '').strip()
    next_plan = (data.get('next_plan') or '').strip()
    blockers = (data.get('blockers') or '').strip() or None
    progress_rating = data.get('progress_rating')

    if not today_work:
        return error_response('today_work is required', 400)

    if not next_plan:
        return error_response('next_plan is required', 400)

    if progress_rating is not None:
        try:
            progress_rating = int(progress_rating)
        except (TypeError, ValueError):
            return error_response('progress_rating must be an integer', 400)

        if progress_rating < 1 or progress_rating > 5:
            return error_response('progress_rating must be between 1 and 5', 400)

    today = date.today()
    existing = DailyUpdate.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        date=today,
    ).first()

    if existing:
        return error_response('Daily update already submitted for today', 400, {'update': existing.to_dict()})

    record = DailyUpdate(
        user_id=user_id,
        workspace_id=workspace_id,
        date=today,
        today_work=today_work,
        next_plan=next_plan,
        blockers=blockers,
        progress_rating=progress_rating,
    )

    open_alert = ErpAlert.query.filter(
        ErpAlert.workspace_id == workspace_id,
        ErpAlert.user_id == user_id,
        ErpAlert.type == 'missing_update',
        ErpAlert.source_date == today,
        ErpAlert.resolved == False,
    ).first()

    if open_alert:
        open_alert.resolved = True
        open_alert.resolved_at = datetime.utcnow()
        open_alert.resolved_by = user_id
        open_alert.resolution_note = 'Auto-resolved by update submission'

    try:
        db.session.add(record)
        db.session.commit()
        return success_response(
            {
                'update': record.to_dict(),
                'missing_update_alert_hint': {
                    'user_id': user_id,
                    'workspace_id': workspace_id,
                    'date': today.isoformat(),
                    'action': 'submission_recorded',
                    'auto_resolved_alert_id': open_alert.id if open_alert else None,
                },
            },
            'Daily update submitted',
            201,
        )
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to submit update: {exc}', 500)


@updates_bp.route('/my', methods=['GET'])
@jwt_required()
def my_updates():
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

    limit_raw = request.args.get('limit', 30)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        return error_response('limit must be an integer', 400)

    if limit < 1:
        return error_response('limit must be >= 1', 400)

    limit = min(limit, 180)
    records = (DailyUpdate.query
               .filter_by(user_id=user_id, workspace_id=workspace_id)
               .order_by(DailyUpdate.date.desc(), DailyUpdate.created_at.desc())
               .limit(limit)
               .all())

    return success_response({'records': [r.to_dict() for r in records]})


@updates_bp.route('/workspace', methods=['GET'])
@jwt_required()
def workspace_updates():
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

    target_raw = request.args.get('date')
    if target_raw:
        try:
            target_date = datetime.strptime(target_raw, '%Y-%m-%d').date()
        except ValueError:
            return error_response('date must be YYYY-MM-DD', 400)
    else:
        target_date = date.today()

    records = (DailyUpdate.query
               .filter_by(workspace_id=workspace_id, date=target_date)
               .order_by(DailyUpdate.created_at.desc())
               .all())

    submitted_user_ids = {r.user_id for r in records}
    active_members = WorkspaceMember.query.filter_by(workspace_id=workspace_id, status='active').all()

    missing_users = []
    for m in active_members:
        if m.user_id in submitted_user_ids:
            continue
        if m.user:
            missing_users.append({
                'user_id': m.user_id,
                'name': f'{m.user.first_name} {m.user.last_name}'.strip(),
                'email': m.user.email,
                'role': m.role.value if hasattr(m.role, 'value') else m.role,
            })
        else:
            missing_users.append({
                'user_id': m.user_id,
                'name': None,
                'email': None,
                'role': m.role.value if hasattr(m.role, 'value') else m.role,
            })

    return success_response({
        'workspace_id': workspace_id,
        'date': target_date.isoformat(),
        'submitted_count': len(records),
        'missing_count': len(missing_users),
        'missing_update_candidates': missing_users,
        'records': [r.to_dict() for r in records],
    })
