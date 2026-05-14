from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.sfdrivefolder_service import create_folder, get_folder_contents, move_file

folder_bp = Blueprint('folders', __name__)


@folder_bp.route('/folders/create', methods=['POST'])
@jwt_required()
def create_folder_route():
    if not request.json:
        return jsonify({"error": "Invalid request body"}), 400

    data = request.json

    if not data.get('name') or not data.get('workspace_id'):
        return jsonify({"error": "name and workspace_id required"}), 400

    user_id = get_jwt_identity()

    result = create_folder(
        name=data.get('name'),
        workspace_id=data.get('workspace_id'),
        parent_id=data.get('parent_id'),
        user_id=user_id
    )

    data, status = result
    return jsonify(data), status


@folder_bp.route('/folders/<int:folder_id>', methods=['GET'])
@jwt_required()
def list_contents(folder_id):
    workspace_id = request.args.get('workspace_id')

    if not workspace_id:
        return jsonify({"error": "workspace_id required"}), 400

    result = get_folder_contents(folder_id, workspace_id)

    data, status = result
    return jsonify(data), status


@folder_bp.route('/folders/move-file', methods=['PATCH'])
@jwt_required()
def move_file_route():
    if not request.json:
        return jsonify({"error": "Invalid request body"}), 400

    data = request.json
    user_id = get_jwt_identity()

    result = move_file(
        doc_id=data.get('doc_id'),
        new_folder_id=data.get('folder_id'),
        user_id=user_id
    )

    data, status = result
    return jsonify(data), status