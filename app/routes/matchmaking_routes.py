from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.matchmaking.matcher import find_matches_for_vision
from app.models.vision import Vision

matchmaking_bp = Blueprint("matchmaking", __name__)


def standard_response(success=True, data=None, error=None, code=200):
    return jsonify({
        "success": success,
        "data": data,
        "error": error
    }), code


# --------------------------------------------------
#  Get Matches for a Vision
# --------------------------------------------------
@matchmaking_bp.route("/vision/<int:vision_id>", methods=["GET"])
@jwt_required()
def get_matches_for_vision(vision_id):
    try:
        user_id = get_jwt_identity()

        vision = Vision.query.get(vision_id)

        if not vision:
            return standard_response(False, None, "Vision not found", 404)

        # Optional security: only creator can view matches
        if vision.creator_id != user_id:
            return standard_response(False, None, "Unauthorized", 403)

        matches = find_matches_for_vision(vision_id)

        return standard_response(True, {
            "vision_id": vision_id,
            "matches": matches
        })

    except Exception as e:
        return standard_response(False, None, str(e), 500)