from functools import wraps
from flask import request
from flask_jwt_extended import get_jwt_identity
from app.models.user import User


def get_current_workspace_id():

    workspace_id = request.headers.get("X-Workspace-Id")

    if workspace_id:
        return int(workspace_id)

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    return user.active_workspace_id if user else None


def require_workspace_member(f):

    @wraps(f)
    def decorator(*args, **kwargs):
        return f(*args, **kwargs)

    return decorator


def require_workspace_admin(f):

    @wraps(f)
    def decorator(*args, **kwargs):
        return f(*args, **kwargs)

    return decorator