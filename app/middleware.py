from functools import wraps
from flask_jwt_extended import get_jwt_identity
from app.services.membership_service import is_admin, is_any_admin
from app.utils.helper import error_response

def workspace_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = int(get_jwt_identity())
        workspace_id = kwargs.get('workspace_id')
        if not is_admin(workspace_id, user_id):
            return error_response('Admin access required', 403)
        return fn(*args, **kwargs)
    return wrapper

def workspace_member_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = int(get_jwt_identity())
        workspace_id = kwargs.get('workspace_id')
        from app.models.workspace_membership import WorkspaceMembership
        membership = WorkspaceMembership.query.filter_by(
            workspace_id=workspace_id, user_id=user_id).first()
        if not membership:
            return error_response('Workspace member access required', 403)
        return fn(*args, **kwargs)
    return wrapper

def any_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = int(get_jwt_identity())
        if not is_any_admin(user_id):
            return error_response('Admin access required', 403)
        return fn(*args, **kwargs)
    return wrapper