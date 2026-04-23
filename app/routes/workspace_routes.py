from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.user import User
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user_id,
    get_current_user,
    is_global_admin,
    workspace_member_required,
    workspace_admin_required,
)


workspace_bp = Blueprint('workspace', __name__)


def _to_slug(name):
    base = ''.join(ch.lower() if ch.isalnum() else '-' for ch in name).strip('-')
    while '--' in base:
        base = base.replace('--', '-')
    return base or 'workspace'


def _unique_slug(name):
    base = _to_slug(name)
    slug = base
    index = 2
    while Workspace.query.filter_by(slug=slug).first():
        slug = f'{base}-{index}'
        index += 1
    return slug


@workspace_bp.route('/create', methods=['POST'])
@jwt_required()
def create_workspace():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return error_response('Workspace name is required', 400)

    owner_user_id = data.get('owner_user_id', user_id)
    try:
        owner_user_id = int(owner_user_id)
    except (TypeError, ValueError):
        return error_response('owner_user_id must be an integer', 400)

    if owner_user_id != user_id and not is_global_admin(user):
        return error_response('Only admin can create workspace for another user', 403)

    owner = User.query.get(owner_user_id)
    if not owner:
        return error_response('Owner user not found', 404)

    try:
        workspace = Workspace(
            name=name,
            slug=_unique_slug(name),
            owner_user_id=owner_user_id,
            is_active=True,
        )
        db.session.add(workspace)
        db.session.flush()

        db.session.add(WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_user_id,
            role='admin',
            status='active',
        ))
        db.session.commit()

        return success_response({
            'workspace': workspace.to_dict(),
        }, 'Workspace created', 201)
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to create workspace: {exc}', 500)


@workspace_bp.route('/<int:workspace_id>', methods=['GET'])
@workspace_member_required('workspace_id')
def get_workspace(workspace_id):
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        return error_response('Workspace not found', 404)

    membership = g.get('current_workspace_membership')

    return success_response({
        'workspace': workspace.to_dict(),
        'membership': membership.to_dict() if membership else None,
    })


@workspace_bp.route('/<int:workspace_id>/users', methods=['GET'])
@workspace_admin_required('workspace_id')
def list_workspace_users(workspace_id):
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        return error_response('Workspace not found', 404)

    members = (WorkspaceMember.query
               .filter_by(workspace_id=workspace_id)
               .order_by(WorkspaceMember.joined_at.asc())
               .all())

    return success_response({
        'workspace': workspace.to_dict(),
        'users': [m.to_dict(include_user=True) for m in members],
        'count': len(members),
    })
