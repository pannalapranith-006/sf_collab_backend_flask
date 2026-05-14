from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.erp_task import ErpTask
from app.models.user import User
from app.models.workspace import Workspace
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user,
    get_current_user_id,
    get_workspace_membership,
    is_global_admin,
)


erp_tasks_bp = Blueprint('erp_tasks', __name__)


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


def _parse_datetime(value, field_name):
    if value in (None, ''):
        return None, None

    if isinstance(value, str):
        candidate = value.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(candidate), None
        except ValueError:
            return None, error_response(f'{field_name} must be ISO datetime', 400)

    return None, error_response(f'{field_name} must be a string datetime', 400)


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


def _can_mutate_task(task, user_id, user, membership):
    role = membership.role.value if (membership and hasattr(membership.role, 'value')) else (membership.role if membership else None)
    return (
        task.created_by == user_id
        or task.assigned_to == user_id
        or role == 'admin'
        or is_global_admin(user)
    )


@erp_tasks_bp.route('/create', methods=['POST'])
@jwt_required()
def create_erp_task():
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

    _, err = _assert_admin_access(workspace_id, user_id, user)
    if err:
        return err

    title = (data.get('title') or '').strip()
    if not title:
        return error_response('title is required', 400)

    description = (data.get('description') or '').strip() or None
    assigned_to = data.get('assigned_to')

    if assigned_to is not None:
        try:
            assigned_to = int(assigned_to)
        except (TypeError, ValueError):
            return error_response('assigned_to must be an integer', 400)

        assignee_member = get_workspace_membership(workspace_id, assigned_to)
        if not assignee_member:
            return error_response('assigned_to user must be an active workspace member', 400)

    deadline, err = _parse_datetime(data.get('deadline'), 'deadline')
    if err:
        return err

    status = (data.get('status') or 'todo').strip()
    if status not in ('todo', 'in_progress', 'done'):
        return error_response('status must be one of: todo, in_progress, done', 400)

    task = ErpTask(
        workspace_id=workspace_id,
        title=title,
        description=description,
        assigned_to=assigned_to,
        deadline=deadline,
        status=status,
        created_by=user_id,
    )

    try:
        db.session.add(task)
        db.session.commit()
        return success_response({'task': task.to_dict()}, 'ERP task created', 201)
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to create ERP task: {exc}', 500)


@erp_tasks_bp.route('/list', methods=['GET'])
@jwt_required()
def list_erp_tasks():
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

    query = ErpTask.query.filter_by(workspace_id=workspace_id)

    status = request.args.get('status')
    if status:
        if status not in ('todo', 'in_progress', 'done'):
            return error_response('status must be one of: todo, in_progress, done', 400)
        query = query.filter(ErpTask.status == status)

    assigned_to = request.args.get('assigned_to')
    if assigned_to:
        try:
            assigned_to = int(assigned_to)
        except (TypeError, ValueError):
            return error_response('assigned_to must be an integer', 400)
        query = query.filter(ErpTask.assigned_to == assigned_to)

    tasks = query.order_by(ErpTask.created_at.desc()).all()
    overdue = [t for t in tasks if t.is_overdue()]

    return success_response({
        'workspace_id': workspace_id,
        'count': len(tasks),
        'overdue_count': len(overdue),
        'task_overdue_alert_candidates': [
            {
                'task_id': t.id,
                'workspace_id': t.workspace_id,
                'assigned_to': t.assigned_to,
                'deadline': t.deadline.isoformat() if t.deadline else None,
                'status': t.status.value if hasattr(t.status, 'value') else t.status,
            }
            for t in overdue
        ],
        'tasks': [t.to_dict() for t in tasks],
    })


@erp_tasks_bp.route('/update', methods=['PATCH'])
@jwt_required()
def update_erp_task():
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

    membership, err = _assert_member_access(workspace_id, user_id, user)
    if err:
        return err

    task_id = data.get('task_id')
    if task_id is None:
        return error_response('task_id is required', 400)

    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return error_response('task_id must be an integer', 400)

    task = ErpTask.query.filter_by(id=task_id, workspace_id=workspace_id).first()
    if not task:
        return error_response('ERP task not found', 404)

    if not _can_mutate_task(task, user_id, user, membership):
        return error_response('Unauthorized to update this ERP task', 403)

    if 'title' in data:
        title = (data.get('title') or '').strip()
        if not title:
            return error_response('title cannot be empty', 400)
        task.title = title

    if 'description' in data:
        task.description = (data.get('description') or '').strip() or None

    if 'status' in data:
        status = (data.get('status') or '').strip()
        if status not in ('todo', 'in_progress', 'done'):
            return error_response('status must be one of: todo, in_progress, done', 400)
        task.status = status

    if 'assigned_to' in data:
        assigned_to = data.get('assigned_to')
        if assigned_to in (None, ''):
            task.assigned_to = None
        else:
            try:
                assigned_to = int(assigned_to)
            except (TypeError, ValueError):
                return error_response('assigned_to must be an integer', 400)

            assignee_member = get_workspace_membership(workspace_id, assigned_to)
            if not assignee_member:
                return error_response('assigned_to user must be an active workspace member', 400)
            task.assigned_to = assigned_to

    if 'deadline' in data:
        deadline, err = _parse_datetime(data.get('deadline'), 'deadline')
        if err:
            return err
        task.deadline = deadline

    task.updated_at = datetime.utcnow()

    try:
        db.session.commit()
        return success_response({'task': task.to_dict()}, 'ERP task updated')
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to update ERP task: {exc}', 500)


@erp_tasks_bp.route('/workspace', methods=['GET'])
@jwt_required()
def workspace_erp_tasks():
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

    tasks = ErpTask.query.filter_by(workspace_id=workspace_id).order_by(ErpTask.created_at.desc()).all()

    summary = {
        'total': len(tasks),
        'todo': 0,
        'in_progress': 0,
        'done': 0,
        'overdue': 0,
    }

    overdue_candidates = []
    for task in tasks:
        status = task.status.value if hasattr(task.status, 'value') else task.status
        if status in summary:
            summary[status] += 1
        if task.is_overdue():
            summary['overdue'] += 1
            overdue_candidates.append({
                'task_id': task.id,
                'workspace_id': task.workspace_id,
                'assigned_to': task.assigned_to,
                'deadline': task.deadline.isoformat() if task.deadline else None,
                'status': status,
            })

    return success_response({
        'workspace_id': workspace_id,
        'summary': summary,
        'task_overdue_alert_candidates': overdue_candidates,
        'tasks': [t.to_dict() for t in tasks],
    })
