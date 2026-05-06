from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from app.extensions import db
from app.models.collaboration_request import CollaborationRequest
from app.models.vision import Vision
from app.models.user import User

collab_bp = Blueprint("collaboration", __name__)


def standard_response(success=True, data=None, error=None, code=200):
    return jsonify({
        "success": success,
        "data": data,
        "error": error
    }), code


# --------------------------------------------------
# 🔥 1. SEND COLLABORATION REQUEST
# --------------------------------------------------
@collab_bp.route("/request", methods=["POST"])
@jwt_required()
def send_collaboration_request():
    try:
        sender_id = get_jwt_identity()
        data = request.get_json()

        vision_id = data.get("vision_id")
        receiver_id = data.get("receiver_id")
        role = data.get("role")

        if not vision_id or not receiver_id or not role:
            return standard_response(False, None, "Missing required fields", 400)

        vision = Vision.query.get(vision_id)

        if not vision:
            return standard_response(False, None, "Vision not found", 404)

        # Only creator can send request
        if vision.creator_id != sender_id:
            return standard_response(False, None, "Unauthorized", 403)

        # Prevent self-invite
        if sender_id == receiver_id:
            return standard_response(False, None, "Cannot invite yourself", 400)

        # Prevent duplicate request
        existing = CollaborationRequest.query.filter_by(
            vision_id=vision_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            status="PENDING"
        ).first()

        if existing:
            return standard_response(False, None, "Request already sent", 400)

        new_request = CollaborationRequest(
            vision_id=vision_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            role=role,
            commitment=data.get("commitment"),
            equity=data.get("equity"),
            description=data.get("description"),
            status="PENDING"
        )

        db.session.add(new_request)
        db.session.commit()

        return standard_response(True, new_request.to_dict(), None, 201)

    except Exception as e:
        db.session.rollback()
        return standard_response(False, None, str(e), 500)


# --------------------------------------------------
# 🔥 2. RESPOND TO REQUEST
# --------------------------------------------------
@collab_bp.route("/request/<int:request_id>", methods=["PATCH"])
@jwt_required()
def respond_to_request(request_id):
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        action = data.get("action")  # ACCEPT / DECLINE

        if action not in ["ACCEPT", "DECLINE"]:
            return standard_response(False, None, "Invalid action", 400)

        collab_request = CollaborationRequest.query.get(request_id)

        if not collab_request:
            return standard_response(False, None, "Request not found", 404)

        # Only receiver can respond
        if collab_request.receiver_id != user_id:
            return standard_response(False, None, "Unauthorized", 403)

        if collab_request.status != "PENDING":
            return standard_response(False, None, "Already responded", 400)

        collab_request.status = "ACCEPTED" if action == "ACCEPT" else "DECLINED"
        collab_request.responded_at = datetime.utcnow()

        db.session.commit()

        return standard_response(True, collab_request.to_dict())

    except Exception as e:
        db.session.rollback()
        return standard_response(False, None, str(e), 500)


# --------------------------------------------------
# 🔥 3. GET RECEIVED REQUESTS
# --------------------------------------------------
@collab_bp.route("/received", methods=["GET"])
@jwt_required()
def get_received_requests():
    try:
        user_id = get_jwt_identity()

        requests = CollaborationRequest.query.filter_by(
            receiver_id=user_id
        ).order_by(CollaborationRequest.created_at.desc()).all()

        return standard_response(True, [r.to_dict() for r in requests])

    except Exception as e:
        return standard_response(False, None, str(e), 500)


# --------------------------------------------------
# 🔥 4. GET SENT REQUESTS
# --------------------------------------------------
@collab_bp.route("/sent", methods=["GET"])
@jwt_required()
def get_sent_requests():
    try:
        user_id = get_jwt_identity()

        requests = CollaborationRequest.query.filter_by(
            sender_id=user_id
        ).order_by(CollaborationRequest.created_at.desc()).all()

        return standard_response(True, [r.to_dict() for r in requests])

    except Exception as e:
        return standard_response(False, None, str(e), 500)