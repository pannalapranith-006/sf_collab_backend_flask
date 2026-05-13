from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.models.Enums import UserRoles
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.utils.helper import error_response


def get_current_user_id():
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


def get_current_user():
    user_id = get_current_user_id()
    if not user_id:
        return None
    return User.query.get(user_id)


def is_global_admin(user):
    if not user:
        return False
    role = user.role.value if hasattr(user.role, 'value') else user.role
    return role == UserRoles.admin.value or role == 'admin'


def get_workspace_membership(workspace_id, user_id):
    return WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        user_id=user_id,
        status='active',
    ).first()


def _workspace_id_from_kwargs(kwargs, param_name):
    workspace_id = kwargs.get(param_name)
    if workspace_id is None:
        return None
    try:
        return int(workspace_id)
    except (TypeError, ValueError):
        return None


def workspace_member_required(workspace_id_arg='workspace_id', allow_global_admin=True):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()

            workspace_id = _workspace_id_from_kwargs(kwargs, workspace_id_arg)
            if workspace_id is None:
                return error_response('Workspace ID is required in route', 400)

            user_id = get_current_user_id()
            if not user_id:
                return error_response('Invalid auth identity', 401)

            user = User.query.get(user_id)
            if not user:
                return error_response('User not found', 404)

            membership = get_workspace_membership(workspace_id, user_id)
            if not membership and not (allow_global_admin and is_global_admin(user)):
                return error_response('Unauthorized to access this workspace', 403)

            g.current_user = user
            g.current_workspace_membership = membership
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def workspace_admin_required(workspace_id_arg='workspace_id', allow_global_admin=True):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()

            workspace_id = _workspace_id_from_kwargs(kwargs, workspace_id_arg)
            if workspace_id is None:
                return error_response('Workspace ID is required in route', 400)

            user_id = get_current_user_id()
            if not user_id:
                return error_response('Invalid auth identity', 401)

            user = User.query.get(user_id)
            if not user:
                return error_response('User not found', 404)

            membership = get_workspace_membership(workspace_id, user_id)
            member_role = membership.role.value if (membership and hasattr(membership.role, 'value')) else (membership.role if membership else None)
            is_workspace_admin = member_role == 'admin'
            if not is_workspace_admin and not (allow_global_admin and is_global_admin(user)):
                return error_response('Admin access required', 403)

            g.current_user = user
            g.current_workspace_membership = membership
            return fn(*args, **kwargs)

        return wrapper

    return decorator
