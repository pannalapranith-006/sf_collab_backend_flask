from flask import Blueprint, request, jsonify
from app.services.mvp_workspace_service import (
    create_workspace,
    get_workspace,
    update_workspace
)

# -----------------------------------
# Blueprint Registration
# -----------------------------------
mvp_workspace_bp = Blueprint("mvp_workspace", __name__)


# -----------------------------------
# CREATE WORKSPACE
# -----------------------------------
@mvp_workspace_bp.route("/api/mvp/workspaces", methods=["POST"])
def create_workspace_api():
    """
    Create a new workspace (company)

    Expected JSON:
    {
        "user_id": int,
        "name": str,
        "description": str (optional)
    }
    """
    try:
        data = request.get_json()

        # 🔹 Replace this with JWT later
        user_id = data.get("user_id")
        name = data.get("name")
        description = data.get("description")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        if not name:
            return jsonify({"error": "Workspace name is required"}), 400

        workspace = create_workspace(user_id, name, description)

        return jsonify({
            "message": "Workspace created successfully",
            "workspace": workspace.to_dict()
        }), 201

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 400


# -----------------------------------
# GET WORKSPACE
# -----------------------------------
@mvp_workspace_bp.route("/api/mvp/workspaces/<int:workspace_id>", methods=["GET"])
def get_workspace_api(workspace_id):
    """
    Get workspace details

    Query Params:
    ?user_id=1
    """
    try:
        # 🔹 Replace with JWT later
        user_id = request.args.get("user_id", type=int)

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        workspace = get_workspace(workspace_id, user_id)

        return jsonify({
            "workspace": workspace.to_dict()
        }), 200

    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# -----------------------------------
# UPDATE WORKSPACE
# -----------------------------------
@mvp_workspace_bp.route("/api/mvp/workspaces/<int:workspace_id>", methods=["PATCH"])
def update_workspace_api(workspace_id):
    """
    Update workspace (Admin only)

    Expected JSON:
    {
        "user_id": int,
        "name": str (optional),
        "description": str (optional)
    }
    """
    try:
        data = request.get_json()

        # 🔹 Replace with JWT later
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        workspace = update_workspace(workspace_id, user_id, data)

        return jsonify({
            "message": "Workspace updated successfully",
            "workspace": workspace.to_dict()
        }), 200

    except PermissionError as e:
        return jsonify({"error": str(e)}), 403

    except Exception as e:
        return jsonify({"error": str(e)}), 400