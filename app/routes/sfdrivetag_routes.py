from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.services.sfdrivetag_service import (
    add_tags,
    get_file_tags
)

tag_bp = Blueprint('tags', __name__)


@tag_bp.route('/tags/add', methods=['POST'])
@jwt_required()
def add_file_tags():
    if not request.json:
        return jsonify({"error": "Invalid request"}), 400

    data = request.json

    file_id = data.get('file_id')
    tags = data.get('tags')

    if not file_id or not tags:
        return jsonify({
            "error": "file_id and tags required"
        }), 400

    result = add_tags(file_id, tags)

    data, status = result

    return jsonify(data), status


@tag_bp.route('/tags/file/<int:file_id>', methods=['GET'])
@jwt_required()
def get_tags(file_id):

    result = get_file_tags(file_id)

    data, status = result

    return jsonify(data), status