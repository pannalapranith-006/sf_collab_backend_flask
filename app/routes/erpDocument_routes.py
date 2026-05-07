from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.erpDocument_service import (
    handle_upload,
    get_documents,
    remove_document,
    download_document
)


documents_bp = Blueprint('documents', __name__)


@documents_bp.route('/documents/upload', methods=['POST'])
@jwt_required()
def upload_document():
    file = request.files.get('file')
    workspace_id = request.form.get('workspace_id')
    folder = request.form.get('folder', 'general')

    user_id = get_jwt_identity()

    if not file:
        return jsonify({"error": "No file provided"}), 400

    result = handle_upload(file, workspace_id, folder, user_id)
    if isinstance(result, tuple):
        data, status = result
        return jsonify(data), status
    return jsonify(result), 200


@documents_bp.route('/documents/list', methods=['GET'])
@jwt_required()
def list_documents():
    workspace_id = request.args.get('workspace_id')

    result = get_documents(workspace_id)
    if isinstance(result, tuple):
        data, status = result
        return jsonify(data), status
    return jsonify(result), 200

@documents_bp.route('/documents/<int:doc_id>/download', methods=['GET'])
@jwt_required()
def download(doc_id):
    user_id = get_jwt_identity()

    result = download_document(doc_id, user_id)

    return result  

@documents_bp.route('/documents/<int:doc_id>', methods=['DELETE'])
@jwt_required()
def delete_document(doc_id):
    user_id = get_jwt_identity()

    result = remove_document(doc_id, user_id)

    # handle (data, status) response
    if isinstance(result, tuple):
        data, status = result
        return jsonify(data), status

    return jsonify(result), 200