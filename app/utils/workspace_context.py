from flask import request, g, has_request_context
from flask_jwt_extended import get_jwt_identity
from app.models.user import User

def get_current_workspace_id():
    if not has_request_context():
        return None

    workspace_id = request.headers.get("X-Workspace-Id")

    if workspace_id:
        return int(workspace_id)

    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    return user.active_workspace_id if user else None

