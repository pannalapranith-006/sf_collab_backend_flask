from app import db
from app.models.mvp_workspace import MVPWorkspace
from app.models.mvp_membership import MVPMembership


# -------------------------------
# HELPER
# -------------------------------
def get_membership(user_id, workspace_id):
    return MVPMembership.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        status="active"
    ).first()


# -------------------------------
# CREATE WORKSPACE
# -------------------------------
def create_workspace(user_id, name, description=None):
    if not name:
        raise ValueError("Workspace name is required")

    workspace = MVPWorkspace(
        name=name,
        description=description,
        owner_user_id=user_id
    )

    db.session.add(workspace)
    db.session.flush()

    membership = MVPMembership(
        workspace_id=workspace.id,
        user_id=user_id,
        role="admin"
    )

    db.session.add(membership)
    db.session.commit()

    return workspace


# -------------------------------
# GET WORKSPACE
# -------------------------------
def get_workspace(workspace_id, user_id):
    membership = get_membership(user_id, workspace_id)

    if not membership:
        raise PermissionError("Access denied")

    workspace = MVPWorkspace.query.get(workspace_id)

    if not workspace or not workspace.is_active:
        raise ValueError("Workspace not found")

    return workspace


# -------------------------------
# UPDATE WORKSPACE
# -------------------------------
def update_workspace(workspace_id, user_id, data):
    membership = get_membership(user_id, workspace_id)

    if not membership:
        raise PermissionError("Access denied")

    if membership.role != "admin":
        raise PermissionError("Admin access required")

    workspace = MVPWorkspace.query.get(workspace_id)

    if not workspace:
        raise ValueError("Workspace not found")

    if "name" in data:
        workspace.name = data["name"]

    if "description" in data:
        workspace.description = data["description"]

    db.session.commit()

    return workspace