from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.user import User

from app.utils.workspace_context import (
    get_current_workspace_id,
    require_workspace_member,
    require_workspace_admin
)

workspace_bp = Blueprint("workspace", __name__)

#Create Workspace
@workspace_bp.route("/create", methods=["POST"])
@jwt_required()
def create_workspace():
    data = request.get_json()

    name = data.get("name")
    slug = data.get("slug")

    if not name or not slug:
        return jsonify({"error": "Name and slug are required"}), 400

    #  Check duplicate slug
    existing = Workspace.query.filter_by(slug=slug).first()
    if existing:
        return jsonify({"error": "Slug already exists"}), 400

    user_id = get_jwt_identity()

    #  Create workspace
    workspace = Workspace(
        workspace_name=name,
        slug=slug,
        owner_user_id=user_id
    )

    db.session.add(workspace)
    db.session.commit()

    #  Add creator as admin
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user_id,
        role="admin",
        status="active"
    )

    db.session.add(member)

    #  Set active workspace
    user = User.query.get(user_id)
    user.active_workspace_id = workspace.id

    db.session.commit()

    return jsonify({
        "message": "Workspace created",
        "workspace_id": workspace.id
    }), 201

#Get Workspace Protected
@workspace_bp.route("/<int:id>", methods=["GET"])
@jwt_required()
@require_workspace_member
def get_workspace(id):
    workspace = Workspace.query.get(id)

    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404

    return jsonify({
        "id": workspace.id,
        "name": workspace.workspace_name,
        "slug": workspace.slug
    })

#Get my workspaces
@workspace_bp.route("/my", methods=["GET"])
@jwt_required()
def get_my_workspaces():
    user_id = get_jwt_identity()

    memberships = WorkspaceMember.query.filter_by(
        user_id=user_id,
        status="active"
    ).all()

    result = []

    for m in memberships:
        workspace = Workspace.query.get(m.workspace_id)
        if workspace:
            result.append({
                "id": workspace.id,
                "name": workspace.workspace_name,
                "role": m.role
            })

    return jsonify(result)

#Switch workspaces
@workspace_bp.route("/switch/<int:workspace_id>", methods=["POST"])
@jwt_required()
def switch_workspace(workspace_id):
    user_id = get_jwt_identity()

    member = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        user_id=user_id,
        status="active"
    ).first()

    if not member:
        return jsonify({"error": "Not a member of this workspace"}), 403

    user = User.query.get(user_id)
    user.active_workspace_id = workspace_id

    db.session.commit()

    return jsonify({"message": "Workspace switched successfully"})

#Get workspace members
@workspace_bp.route("/<int:workspace_id>/members", methods=["GET"])
@jwt_required()
@require_workspace_member
def get_workspace_members(workspace_id):
    members = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        status="active"
    ).all()

    result = []

    for m in members:
        user = User.query.get(m.user_id)
        if user:
            result.append({
                "user_id": user.id,
                "email": user.email,
                "role": m.role
            })

    return jsonify(result)

#delete workspace Admin only
@workspace_bp.route("/<int:workspace_id>", methods=["DELETE"])
@jwt_required()
@require_workspace_admin
def delete_workspace(workspace_id):
    workspace = Workspace.query.get(workspace_id)

    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404

    db.session.delete(workspace)
    db.session.commit()

    return jsonify({"message": "Workspace deleted successfully"})