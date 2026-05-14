from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.services.sfmeetsearch_service import search_data

search_bp = Blueprint('sfmeet_search', __name__)


@search_bp.route('/search', methods=['GET'])
@jwt_required()
def search():

    query = request.args.get('query')
    workspace_id = request.args.get('workspace_id')

    if not query or not workspace_id:
        return jsonify({
            "error": "query and workspace_id required"
        }), 400

    try:
        workspace_id = int(workspace_id)
    except:
        return jsonify({"error": "workspace_id must be integer"}), 400

    data, status = search_data(query, workspace_id)

    return jsonify(data), status