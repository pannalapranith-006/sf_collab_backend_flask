from flask import Blueprint, jsonify, request, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from sympy import content
from werkzeug.utils import secure_filename

from app.models.chatConversation import ChatConversation, conversation_participants
from app.models.chatMessage import ChatMessage
from app.models.user import User
from app.extensions import db
from app.utils.helper import error_response, success_response
from app.utils.timezone_converter import get_user_timezone

import logging
import re
import os
import json
from datetime import datetime

from app.utils.chat_utils import (
    get_or_create_general_chat,
    add_user_to_general_chat,
    on_user_profile_created,
    on_founder_created,
    on_team_member_added,
    on_team_member_removed,
)
from app.notifications.helpers import (
    notify_new_message,
    notify_group_message,
    notify_mention_in_chat,
    notify_message_request,
    notify_voice_message_received,
)

# Import socket events for real-time updates
try:
    from app.socket_events import (
        emit_new_message,
        emit_message_edited,
        emit_message_deleted,
        emit_conversation_update,
        emit_to_user,
        emit_notification,
    )

    SOCKET_ENABLED = True
except ImportError:
    SOCKET_ENABLED = False
    logging.warning("Socket events not available - real-time updates disabled")


chat_bp = Blueprint("chat", __name__)

# Upload configurations
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "chat_files")
AVATAR_UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "chat_avatars")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "doc", "docx", "txt"}
ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_avatar(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS
    )


def validate_file_size(file, max_size=MAX_FILE_SIZE) -> bool:
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size <= max_size


def get_user_full_name(user_id):
    """Helper to get user's full name"""
    from app.models.user import User

    user = User.query.get(user_id)
    if user:
        return f"{user.first_name or ''} {user.last_name or ''}".strip() or "Someone"
    return "Someone"


def extract_mentions(content):
    """Extract @mentions from message content"""
    import re

    # Match @username patterns
    mentions = re.findall(r"@(\w+)", content)
    return mentions


def get_user_by_username(username):
    """Get user by username for mentions"""
    from app.models.user import User

    return User.query.filter_by(username=username).first()


# ─────────────────────────────────────────────────────────────
# GET CONVERSATIONS
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_conversations():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        delete_type = data.get("delete_type", "everyone")

        user = User.query.get(current_user_id)
        if not user:
            return error_response("User not found", 404)

        # Support ?archived=true to fetch only archived, default fetches non-archived
        include_archived = request.args.get("archived", "false").lower() == "true"

        try:
            query = (
                ChatConversation.query.join(conversation_participants)
                .filter(conversation_participants.c.user_id == current_user_id)
                .filter(
                    (conversation_participants.c.is_hidden == False)
                    | (conversation_participants.c.is_hidden == None)
                )
            )
            if include_archived:
                # Return ONLY archived conversations
                query = query.filter(conversation_participants.c.is_archived == True)
            else:
                # Exclude archived conversations (default)
                query = query.filter(
                    (conversation_participants.c.is_archived == False)
                    | (conversation_participants.c.is_archived == None)
                )
            conversations = query.order_by(ChatConversation.updated_at.desc()).all()
        except Exception:
            query = ChatConversation.query.join(conversation_participants).filter(
                conversation_participants.c.user_id == current_user_id
            )
            conversations = query.order_by(ChatConversation.updated_at.desc()).all()

        conversations_data = []
        for conv in conversations:
            try:
                conversations_data.append(conv.to_dict(for_user=user))
            except Exception as e:
                logging.error(f"Error converting conversation {conv.id}: {str(e)}")
                continue

        return success_response({"conversations": conversations_data})

    except Exception as e:
        logging.error(f"Error in get_conversations: {str(e)}")
        return error_response(f"Failed to load conversations: {str(e)}", 500)


@chat_bp.route("/conversations", methods=["POST"], strict_slashes=False)
@jwt_required()
def create_conversation():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}

        # accept either participant_ids or participantIds (frontend sometimes differs)
        participant_ids = data.get("participant_ids") or data.get("participantIds")
        if not participant_ids or not isinstance(participant_ids, list):
            return error_response(
                "Missing required field: participant_ids (must be a list)", 400
            )

        creator = User.query.get(current_user_id)
        if not creator:
            return error_response("Creator not found", 404)

        conversation = ChatConversation(
            name=data.get("name"),
            conversation_type=data.get("conversation_type", "group"),  # group chat
            created_by_id=creator.id,
            description=data.get("description"),
            avatar_url=data.get("avatar_url"),
        )

        db.session.add(conversation)
        db.session.flush()

        # creator is admin
        conversation.add_participant(creator, "admin")

        # add other participants
        participants = User.query.filter(User.id.in_(participant_ids)).all()
        for user in participants:
            if user.id != creator.id:
                conversation.add_participant(user, "member")

        db.session.commit()

        return success_response(
            {"conversation": conversation.to_dict(for_user=creator)},
            "Conversation created successfully",
            201,
        )

    except Exception as e:
        db.session.rollback()
        return error_response(f"Failed to create conversation: {str(e)}", 500)


@chat_bp.route("/conversations/<int:conversation_id>", methods=["GET"])
@jwt_required()
def get_conversation(conversation_id):
    try:
        current_user_id = get_jwt_identity()

        user = User.query.get(current_user_id)
        conversation = ChatConversation.query.get(conversation_id)

        if not user or not conversation:
            return error_response("User or conversation not found", 404)

        if not conversation.is_user_participant(current_user_id):
            return error_response("Access denied", 403)

        return success_response({"conversation": conversation.to_dict(for_user=user)})

    except Exception as e:
        logging.error(f"Error getting conversation {conversation_id}: {str(e)}")
        return error_response(f"Failed to load conversation: {str(e)}", 500)


@chat_bp.route("/conversations/<int:startup_id>", methods=["GET"])
@jwt_required()
def get_startup_conversation(startup_id):
    try:
        current_user_id = get_jwt_identity()

        user = User.query.get(current_user_id)
        conversation = ChatConversation.query.filter_by(
            parent_startup_id=startup_id
        ).first()

        if not user or not conversation:
            return error_response("User or conversation not found", 404)

        if not conversation.is_user_participant(current_user_id):
            return error_response("Access denied", 403)

        return success_response({"conversation": conversation.to_dict(for_user=user)})

    except Exception as e:
        logging.error(
            f"Error getting conversation for startup id:{startup_id}: {str(e)}"
        )
        return error_response(f"Failed to load conversation: {str(e)}", 500)


@chat_bp.route("/conversations/with-user", methods=["POST"])
@jwt_required()
def get_or_create_direct_conversation():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}
        other_user_id = data.get("other_user_id")
        if current_user_id == other_user_id:
            return error_response("You cannot create a conversation with yourself", 400)

        current_user = User.query.get(current_user_id)
        other_user = User.query.get(other_user_id)

        if not current_user or not other_user:
            return error_response("User not found", 404)

        conversation = (
            ChatConversation.query.join(conversation_participants)
            .filter(ChatConversation.conversation_type == "direct")
            .filter(
                conversation_participants.c.user_id.in_(
                    [current_user_id, other_user_id]
                )
            )
            .group_by(ChatConversation.id)
            .having(db.func.count(ChatConversation.id) == 2)
            .first()
        )

        if conversation:
            conversation.unhide_for_user(current_user_id)
            return success_response(
                {
                    "conversation": conversation.to_dict(for_user=current_user),
                    "created": False,
                }
            )

        conversation = ChatConversation(
            conversation_type="direct", created_by_id=current_user_id
        )
        db.session.add(conversation)
        db.session.flush()

        conversation.add_participant(current_user, "member")
        conversation.add_participant(other_user, "member")

        db.session.commit()

        return success_response(
            {
                "conversation": conversation.to_dict(for_user=current_user),
                "created": True,
            },
            "Conversation created",
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to get/create conversation: {str(e)}")
        return error_response(f"Failed to get or create conversation: {str(e)}", 500)


@chat_bp.route("/conversations/group", methods=["POST"])
@jwt_required()
def create_group_conversation():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}

        name = data.get("name")
        participant_ids = data.get("participant_user_ids", [])

        if not name:
            return error_response("Group name is required", 400)

        if not participant_ids or not isinstance(participant_ids, list):
            return error_response("participant_user_ids must be a non-empty list", 400)

        current_user = User.query.get(current_user_id)
        if not current_user:
            return error_response("User not found", 404)

        conversation = ChatConversation(
            conversation_type="group", name=name, created_by_id=current_user_id
        )
        db.session.add(conversation)
        db.session.flush()

        conversation.add_participant(current_user, "admin")

        for user_id in participant_ids:
            user = User.query.get(user_id)
            if user:
                conversation.add_participant(user, "member")

        db.session.commit()

        return success_response(
            {"conversation": conversation.to_dict(for_user=current_user)},
            "Group conversation created",
            201,
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to create group conversation: {str(e)}")
        return error_response(f"Failed to create group conversation: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# GENERAL CHAT
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/general", methods=["GET"])
@jwt_required()
def get_general_chat():
    try:
        from app.utils.general_chat import get_or_create_general_chat as _get_general

        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            return error_response("User not found", 404)

        general_chat = _get_general()
        if not general_chat:
            return error_response("General chat not available", 404)

        return success_response({"conversation": general_chat.to_dict(for_user=user)})

    except Exception as e:
        logging.error(f"Error getting general chat: {str(e)}")
        return error_response(f"Failed to get general chat: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# MARK CONVERSATION AS READ
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>/mark-read", methods=["POST"])
@jwt_required()
def mark_conversation_read(conversation_id):
    try:
        current_user_id = get_jwt_identity()

        user = User.query.get(current_user_id)
        conversation = ChatConversation.query.get(conversation_id)

        if not user or not conversation:
            return error_response("User or conversation not found", 404)

        if not conversation.is_user_participant(current_user_id):
            return error_response("Access denied", 403)

        conversation.mark_as_read(current_user_id)

        return success_response({"message": "Conversation marked as read"})

    except Exception as e:
        logging.error(f"Error marking conversation as read: {str(e)}")
        return error_response(f"Failed to mark conversation as read: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# GET MESSAGES
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>/messages", methods=["GET"])
@jwt_required()
def get_messages(conversation_id):
    try:
        current_user_id = get_jwt_identity()
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        user = User.query.get(current_user_id)
        conversation = ChatConversation.query.get(conversation_id)

        if not user or not conversation:
            return error_response("User or conversation not found", 404)

        if not conversation.is_user_participant(current_user_id):
            return error_response("Access denied", 403)
        return fetch_messages(
            conversation, user, limit, offset, current_user_id, conversation_id
        )

    except Exception as e:
        logging.error(f"Error in get_messages: {str(e)}")
        return error_response(f"Failed to load messages: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTION TO GET MESSAGES
# ─────────────────────────────────────────────────────────────
def fetch_messages(conversation, user, limit, offset, current_user_id, conversation_id):
    # ── Enrich messages with persistent read/delivered status ──────────────
    # For each message sent by the current user, check if other participants
    # have read past it using conversation_user_reads.last_read_at
    try:
        messages = conversation.get_messages_for_user(user, limit, offset)

        from app.models.chatConversation import conversation_user_reads
        from sqlalchemy import and_

        # Get last_read_at for every OTHER participant in this conversation
        other_read_times = {}
        for participant in conversation.participants:
            if str(participant.id) == str(current_user_id):
                continue
            row = db.session.execute(
                db.text(
                    "SELECT last_read_at FROM conversation_user_reads "
                    "WHERE conversation_id = :cid AND user_id = :uid"
                ),
                {"cid": conversation_id, "uid": participant.id},
            ).first()
            if row and row.last_read_at:
                other_read_times[participant.id] = row.last_read_at

        # Enrich each message
        for msg in messages:
            # Only add status for messages sent by the current user
            if str(msg.get("sender_id")) != str(current_user_id):
                continue

            msg_time_str = msg.get("created_at") or msg.get("createdAt")
            if not msg_time_str:
                continue

            # Parse message time
            from datetime import datetime

            try:
                if isinstance(msg_time_str, str):
                    msg_time = datetime.fromisoformat(
                        msg_time_str.replace("Z", "+00:00").replace("+00:00", "")
                    )
                else:
                    msg_time = msg_time_str
            except Exception:
                continue

            # Check if any recipient has read at or after this message
            is_read = any(
                read_time >= msg_time for read_time in other_read_times.values()
            )

            if is_read:
                msg["status"] = "read"
                msg["delivery_status"] = "read"
                # Find the latest read_at among recipients who have read it
                read_ats = [t for t in other_read_times.values() if t >= msg_time]
                msg["read_at"] = max(read_ats).isoformat() if read_ats else None
            else:
                # Mark as delivered if the message was sent (it reached the server)
                msg["status"] = "delivered"
                msg["delivery_status"] = "delivered"
                msg["delivered_at"] = msg_time_str

    except Exception as e:
        logging.warning(f"Could not enrich message statuses: {e}")
    # ── End status enrichment ───────────────────────────────────────────────

    return success_response(
        {"conversation": conversation.to_dict(for_user=user), "messages": messages}
    )


# ─────────────────────────────────────────────────────────────
# GET MESSAGES BY STARTUP ID (for startup-specific conversations)
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:startup_id>/messages", methods=["GET"])
@jwt_required()
def get_startup_messages(startup_id):
    try:
        current_user_id = get_jwt_identity()
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)

        user = User.query.get(current_user_id)
        conversation = ChatConversation.query.filter_by(
            parent_startup_id=startup_id
        ).first()

        return fetch_messages(
            conversation, user, limit, offset, current_user_id, conversation.id
        )

    except Exception as e:
        logging.error(f"Error in get_startup_messages: {str(e)}")
        return error_response(f"Failed to load startup messages: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# SEND MESSAGE (conversation_id)
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>/messages", methods=["POST"])
@jwt_required()
def send_message(conversation_id):
    current_user_id = get_jwt_identity()

    file_url = None

    is_file_upload = "file" in request.files

    if is_file_upload:
        file = request.files.get("file")
        if not file:
            return error_response("No file provided", 400)

        if file.filename == "":
            return error_response("No file selected", 400)

        if not allowed_file(file.filename):
            return error_response(
                f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}',
                400,
            )

        if not validate_file_size(file):
            return error_response(
                f"File size exceeds maximum limit of {MAX_FILE_SIZE / (1024*1024)}MB",
                400,
            )

        content = request.form.get("content", "Sent a file")
        message_type = request.form.get("message_type", "file")
        reply_to_id = request.form.get("reply_to_id", type=int)
        data = None
    else:
        data = request.get_json() or {}
        content = data.get("content")
        message_type = data.get("message_type", "text")
        reply_to_id = data.get("reply_to_id")
        file = None

    if not content and not file_url:
        return error_response("Missing required field: content", 400)

    user = User.query.get(current_user_id)
    conversation = ChatConversation.query.get(conversation_id)

    if not user or not conversation:
        return error_response("User or conversation not found", 404)

    if not conversation.is_user_participant(user.id):
        return error_response("Access denied", 403)

    try:
        sender_timezone = get_user_timezone(user)
        original_content = content
        metadata_data = (
            {} if is_file_upload else (data.get("metadata_data", {}) if data else {})
        )

        time_pattern = r"\[(\d{1,2}:\d{2})\]"
        has_existing_placeholders = bool(re.search(time_pattern, original_content))
        if has_existing_placeholders:
            metadata_data["has_time_placeholders"] = True
            metadata_data["sender_timezone"] = sender_timezone
            metadata_data["sent_at_utc"] = datetime.utcnow().isoformat()

        file_url = None
        file_name = None
        file_size = None
        file_type = None

        if file:
            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{current_user_id}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

            file.save(file_path)

            file_name = filename
            file_size = os.path.getsize(file_path)
            file_type = file.content_type
            file_url = f"/api/chat/uploads/{unique_filename}"

            metadata_data["file_info"] = {
                "original_name": file_name,
                "size": file_size,
                "type": file_type,
                "uploaded_at": datetime.utcnow().isoformat(),
            }

        message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=user.id,
            original_content=original_content,
            message_type=message_type,
            metadata_data=metadata_data,
            reply_to_id=reply_to_id,
            sender_timezone=sender_timezone,
            file_url=file_url,
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
        )

        db.session.add(message)
        conversation.updated_at = datetime.utcnow()

        # ✅ FIX: was user_id (undefined)
        conversation.increment_unread_count(current_user_id)

        db.session.commit()
        # Emit new message realtime
        if SOCKET_ENABLED:
            emit_new_message(conversation_id, message.to_dict(for_user=user))

        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: New Message (4.6) - Using Helpers
        # ════════════════════════════════════════════════════════════
        try:
            sender_name = get_user_full_name(current_user_id)

            # Notify all participants except sender
            for participant in conversation.participants:
                if int(participant.id) != int(current_user_id):
                    # Use appropriate notification based on conversation type
                    if conversation.conversation_type == "group":
                        notify_group_message(
                            user_id=participant.id,
                            sender_id=current_user_id,
                            sender_name=sender_name,
                            group_name=conversation.name or "Group Chat",
                            message_id=message.id,
                        )
                    elif message_type == "voice":
                        notify_voice_message_received(
                            user_id=participant.id,
                            sender_id=current_user_id,
                            sender_name=sender_name,
                            message_id=message.id,
                        )
                    else:
                        notify_new_message(
                            user_id=participant.id,
                            sender_id=current_user_id,
                            sender_name=sender_name,
                            message_id=message.id,
                            conversation_id=conversation.id,
                        )

            # Handle @mentions in message content
            mentions = extract_mentions(original_content)
            for username in mentions:
                mentioned_user = get_user_by_username(username)
                if mentioned_user and int(mentioned_user.id) != int(current_user_id):
                    # Check if mentioned user is part of the conversation
                    if mentioned_user in conversation.participants:
                        notify_mention_in_chat(
                            user_id=mentioned_user.id,
                            mentioner_id=current_user_id,
                            mentioner_name=sender_name,
                            chat_name=conversation.name or "Direct Message",
                            message_id=message.id,
                        )

        except Exception as e:
            print(f"⚠️ Message notification failed: {e}")

        # ✅ FIX: always return a response
        return success_response(
            {
                "message": message.to_dict(for_user=user),
                "conversation": conversation.to_dict(for_user=user),
            },
            "Message sent",
            201,
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to send message: {str(e)}")
        return error_response(f"Failed to send message: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# SEND DIRECT MESSAGE (and Message Request on first contact)
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/direct", methods=["POST"])
@jwt_required()
def send_direct_message():
    """
    Send a message to a user.
    If a direct conversation does not exist, create it automatically.
    Also send a "Message Request" notification on first contact.
    """
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}

        recipient_id = data.get("recipient_user_id")
        content = data.get("content")

        if not recipient_id or not content:
            return error_response("recipient_user_id and content are required", 400)

        if recipient_id == current_user_id:
            return error_response("You cannot message yourself", 400)

        sender = User.query.get(current_user_id)
        recipient = User.query.get(recipient_id)

        if not sender or not recipient:
            return error_response("User not found", 404)

        conversation = (
            ChatConversation.query.join(conversation_participants)
            .filter(ChatConversation.conversation_type == "direct")
            .filter(
                conversation_participants.c.user_id.in_([current_user_id, recipient_id])
            )
            .group_by(ChatConversation.id)
            .having(db.func.count(ChatConversation.id) == 2)
            .first()
        )

        is_new_conversation = False

        if not conversation:
            is_new_conversation = True
            conversation = ChatConversation(
                conversation_type="direct", created_by_id=current_user_id
            )
            db.session.add(conversation)
            db.session.flush()

            conversation.add_participant(sender, "member")
            conversation.add_participant(recipient, "member")

        message = ChatMessage(
            conversation_id=conversation.id,
            sender_id=current_user_id,
            original_content=content,
            message_type="text",
            sender_timezone=get_user_timezone(sender),
        )

        db.session.add(message)

        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Direct Message (4.6)
        # ════════════════════════════════════════════════════════════
        try:
            sender_name = get_user_full_name(current_user_id)
            notify_new_message(
                user_id=recipient_id,
                sender_id=current_user_id,
                sender_name=sender_name,
                message_id=message.id,
                conversation_id=conversation.id,
            )
        except Exception as e:
            print(f"⚠️ Direct message notification failed: {e}")

        conversation.updated_at = datetime.utcnow()
        conversation.increment_unread_count(current_user_id)
        db.session.commit()

        if SOCKET_ENABLED:
            emit_new_message(conversation.id, message.to_dict(for_user=sender))

        # ─────────────────────────────────────────────────────────
        # ✨ NOTIFICATION: Message Request (first contact only)
        # ─────────────────────────────────────────────────────────
        if is_new_conversation:
            try:
                from app.models.notification import Notification

                notification = Notification(
                    user_id=recipient_id,
                    notification_type="info",
                    title="📩 New message request",
                    message=f"{sender.first_name} {sender.last_name} wants to message you",
                    data={
                        "requester_id": current_user_id,
                        "message_preview": content[:100] if content else "",
                        "entity_type": "message_request",
                        "entity_id": conversation.id,
                    },
                )
                db.session.add(notification)
                db.session.commit()

                if SOCKET_ENABLED:
                    emit_notification(recipient_id, notification.to_dict())

            except Exception as e:
                logging.warning(f"⚠️ Message request notification failed: {e}")
                db.session.rollback()

        return success_response(
            {
                "conversation": conversation.to_dict(for_user=sender),
                "message": message.to_dict(for_user=sender),
                "conversation_created": is_new_conversation,
            },
            "Message sent",
            201,
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to send direct message: {str(e)}")
        return error_response(f"Failed to send message: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# EDIT MESSAGE
# ─────────────────────────────────────────────────────────────
@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>", methods=["PUT"]
)
@jwt_required()
def edit_message(conversation_id, message_id):
    current_user_id = get_jwt_identity()
    data = request.get_json() or {}

    content = data.get("content", "").strip()
    file_url = data.get("file_url")

    # Only error if BOTH are missing
    if not content and not file_url:
        return (
            jsonify({"error": "Message must contain text or a file", "success": False}),
            400,
        )

    try:
        message = ChatMessage.query.get(message_id)
        if not message:
            return error_response("Message not found", 404)

        if message.conversation_id != conversation_id:
            return error_response("Message does not belong to this conversation", 400)
        if int(message.sender_id) != int(current_user_id):
            return error_response("You can only edit your own messages", 403)

        new_content = data.get("content")
        metadata_data = data.get("metadata_data", message.metadata_data or {})

        time_pattern = r"\[(\d{1,2}:\d{2})\]"
        has_existing_placeholders = bool(re.search(time_pattern, new_content))
        if has_existing_placeholders:
            metadata_data["has_time_placeholders"] = True
            metadata_data["edited_with_time_placeholders"] = True

        message.edit_message(new_content, metadata_data)

        user = User.query.get(current_user_id)
        response_data = message.to_dict(for_user=user)

        if SOCKET_ENABLED:
            emit_message_edited(conversation_id, response_data)

        return success_response(
            {"message": response_data}, "Message edited successfully"
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to edit message: {str(e)}")
        return error_response(f"Failed to edit message: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# REACT TO MESSAGE (toggle reaction)
# ─────────────────────────────────────────────────────────────
@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>/reactions",
    methods=["POST"],
)
@jwt_required()
def react_to_message(conversation_id, message_id):
    current_user_id = int(get_jwt_identity())  # cast to int — sender_id is int in DB
    data = request.get_json() or {}
    reaction_emoji = data.get("emoji")

    if not reaction_emoji:
        return error_response("emoji is required", 400)

    try:
        message = ChatMessage.query.get(message_id)
        if not message or message.conversation_id != conversation_id:
            return error_response("Message not found", 404)

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or not conversation.is_user_participant(current_user_id):
            return error_response("Access denied", 403)

        metadata = message.metadata_data or {}
        reactions = metadata.get("reactions", {})  # {"👍":[1,2], "❤️":[3]}

        users = reactions.get(reaction_emoji, [])
        is_adding = current_user_id not in users  # True = adding, False = removing
        if current_user_id in users:
            users.remove(current_user_id)
            if users:
                reactions[reaction_emoji] = users
            else:
                reactions.pop(reaction_emoji, None)
        else:
            users.append(current_user_id)
            reactions[reaction_emoji] = users

        metadata["reactions"] = reactions
        message.metadata_data = metadata
        db.session.commit()

        if SOCKET_ENABLED:
            emit_message_edited(conversation_id, message.to_dict())

        # ─────────────────────────────────────────────────────────
        # ✨ NOTIFICATION: Message Reaction
        # ─────────────────────────────────────────────────────────
        try:
            from app.models.notification import Notification

            # Only notify when ADDING a reaction (not removing), and never notify yourself
            if is_adding and message.sender_id != current_user_id:
                reactor = User.query.get(current_user_id)
                if reactor:
                    notification = Notification(
                        user_id=message.sender_id,
                        notification_type="info",
                        title=f"😊 {reactor.first_name} reacted to your message",
                        message=f"Reacted with {reaction_emoji}",
                        data={
                            "message_id": message.id,
                            "conversation_id": message.conversation_id,
                            "reactor_id": current_user_id,
                            "reaction": reaction_emoji,
                            "entity_type": "message",
                            "entity_id": message.id,
                        },
                    )
                    db.session.add(notification)
                    db.session.commit()

                    if SOCKET_ENABLED:
                        emit_notification(message.sender_id, notification.to_dict())

        except Exception as e:
            logging.warning(f"⚠️ Reaction notification failed: {e}")
            db.session.rollback()

        return success_response({"message": message.to_dict()}, "Reaction updated")

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to react to message: {str(e)}")
        return error_response(f"Failed to react to message: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# DELETE MESSAGE (with delete for everyone / delete for me)
# ─────────────────────────────────────────────────────────────
@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>", methods=["DELETE"]
)
@jwt_required()
def delete_message(conversation_id, message_id):
    current_user_id = get_jwt_identity()

    try:
        # Get delete_type from request body
        data = request.get_json(silent=True) or {}
        delete_type = data.get("delete_type", "everyone")  # 'everyone' or 'me'

        message = ChatMessage.query.get(message_id)
        conversation = ChatConversation.query.get(conversation_id)

        if not message:
            return error_response("Message not found", 404)

        if message.conversation_id != conversation_id:
            return error_response("Message does not belong to this conversation", 400)

        # Only message sender can delete
        if int(message.sender_id) != int(current_user_id):
            return error_response("You can only delete your own messages", 403)

        # For "delete for me" - just return success, frontend handles hiding locally
        if delete_type == "me":
            return success_response(
                {"message_id": message_id, "delete_type": "me"},
                "Message hidden for you",
            )

        # For "delete for everyone" - check 1-hour limit
        from datetime import timedelta

        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        if message.created_at < one_hour_ago:
            return error_response(
                "Messages can only be deleted for everyone within 1 hour of sending. You can still delete for yourself.",
                400,
            )

        # Delete attached file if exists
        if message.file_url:
            try:
                file_path = os.path.join(
                    UPLOAD_FOLDER, os.path.basename(message.file_url)
                )
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.error(f"Failed to delete file: {str(e)}")

        # Mark message as deleted (soft delete)
        message.is_deleted = True
        message.original_content = "This message was deleted"
        db.session.commit()

        # Emit socket event for real-time update
        if SOCKET_ENABLED:
            emit_message_deleted(conversation_id, message_id)

        return success_response(
            {"message_id": message_id, "delete_type": "everyone"},
            "Message deleted successfully",
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to delete message: {str(e)}")
        return error_response(f"Failed to delete message: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# SERVE UPLOADED FILE
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/uploads/<path:filename>", methods=["GET"])
def serve_uploaded_file(filename):
    try:
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False)
    except FileNotFoundError:
        return error_response("File not found", 404)


# ─────────────────────────────────────────────────────────────
# GET CONVERSATION FILES
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>/files", methods=["GET"])
@jwt_required()
def get_conversation_files(conversation_id):
    try:
        current_user_id = get_jwt_identity()

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation:
            return error_response("Conversation not found", 404)

        if not conversation.is_user_participant(current_user_id):
            return error_response("Access denied", 403)

        messages_with_files = (
            ChatMessage.query.filter_by(conversation_id=conversation_id)
            .filter(ChatMessage.file_url.isnot(None))
            .order_by(ChatMessage.created_at.desc())
            .all()
        )

        files = []
        for msg in messages_with_files:
            file_url = msg.file_url
            if file_url and not file_url.startswith("http"):
                file_url = request.host_url.rstrip("/") + file_url

            files.append(
                {
                    "id": msg.id,
                    "file_name": msg.file_name,
                    "file_url": file_url,
                    "file_size": msg.file_size,
                    "file_type": msg.file_type,
                    "uploaded_by": {
                        "id": msg.sender_id,
                        "firstName": msg.message_sender.first_name,
                        "lastName": msg.message_sender.last_name,
                    },
                    "uploaded_at": msg.created_at.isoformat(),
                    "is_image": msg.is_image(),
                    "is_document": msg.is_document(),
                }
            )

        return success_response(
            {"files": files, "total_count": len(files)}, "Files retrieved successfully"
        )

    except Exception as e:
        logging.error(f"Failed to get conversation files: {str(e)}")
        return error_response(f"Failed to get files: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# ADD PARTICIPANT (with notifications)
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>/participants", methods=["POST"])
@jwt_required()
def add_participant(conversation_id):
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}

        user_id = data.get("user_id")
        role = data.get("role", "member")

        if not user_id:
            return error_response("User ID is required", 400)

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation:
            return error_response("Conversation not found", 404)

        if conversation.created_by_id != current_user_id:
            return error_response("Only conversation creator can add participants", 403)

        user = User.query.get(user_id)
        if not user:
            return error_response("User not found", 404)

        if conversation.is_user_participant(user_id):
            return error_response("User is already a participant", 400)

        conversation.add_participant(user, role)

        creator = User.query.get(current_user_id)
        notif_content = f"👥 {creator.get_full_name()} added {user.get_full_name()} to the conversation"

        notif_message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=current_user_id,
            original_content=notif_content,
            message_type="system",
            metadata_data={"action": "participant_added", "user_id": user_id},
            sender_timezone="UTC",
        )

        db.session.add(notif_message)
        conversation.updated_at = datetime.utcnow()
        db.session.commit()

        if SOCKET_ENABLED:
            emit_new_message(conversation_id, notif_message.to_dict())
            emit_to_user(
                user_id,
                "added_to_conversation",
                {"conversation": conversation.to_dict(for_user=user)},
            )

        # ─────────────────────────────────────────────────────────
        # ✨ NOTIFICATION: Added to Group Chat
        # ─────────────────────────────────────────────────────────
        if user_id != current_user_id:
            try:
                from app.models.notification import Notification

                adder = creator
                notification = Notification(
                    user_id=user_id,  # ✅ FIX: was new_participant_id (undefined)
                    notification_type="info",
                    title="👥 Added to group chat",
                    message=f'{adder.first_name} added you to "{conversation.name or "a group"}"',
                    data={
                        "conversation_id": conversation.id,
                        "added_by": current_user_id,
                        "entity_type": "conversation",
                        "entity_id": conversation.id,
                    },
                )
                db.session.add(notification)
                db.session.commit()

                if SOCKET_ENABLED:
                    emit_notification(
                        user_id, notification.to_dict()
                    )  # ✅ FIX: emit to user_id

            except Exception as e:
                logging.warning(f"⚠️ Group add notification failed: {e}")
                db.session.rollback()

        return success_response(
            {
                "message": "Participant added successfully",
                "notification": notif_message.to_dict(),
            }
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to add participant: {str(e)}")
        return error_response(f"Failed to add participant: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# REMOVE PARTICIPANT
# ─────────────────────────────────────────────────────────────
@chat_bp.route(
    "/conversations/<int:conversation_id>/participants/<int:user_id>",
    methods=["DELETE"],
)
@jwt_required()
def remove_participant(conversation_id, user_id):
    try:
        current_user_id = get_jwt_identity()

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation:
            return error_response("Conversation not found", 404)

        if conversation.created_by_id != current_user_id:
            return error_response(
                "Only conversation creator can remove participants", 403
            )

        if user_id == conversation.created_by_id:
            return error_response("Cannot remove conversation creator", 400)

        user = User.query.get(user_id)
        if not user:
            return error_response("User not found", 404)

        if not conversation.is_user_participant(user_id):
            return error_response("User is not a participant", 400)

        stmt = (
            conversation_participants.update()
            .where(
                (conversation_participants.c.conversation_id == conversation_id)
                & (conversation_participants.c.user_id == user_id)
            )
            .values(left_at=datetime.utcnow())
        )

        db.session.execute(stmt)
        db.session.commit()

        creator = User.query.get(current_user_id)
        notif_content = f"👋 {user.get_full_name()} was removed from the conversation"

        notif_message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=current_user_id,
            original_content=notif_content,
            message_type="system",
            metadata_data={"action": "participant_removed", "user_id": user_id},
            sender_timezone="UTC",
        )

        db.session.add(notif_message)
        conversation.updated_at = datetime.utcnow()
        db.session.commit()

        if SOCKET_ENABLED:
            emit_new_message(conversation_id, notif_message.to_dict())
            emit_to_user(
                user_id,
                "removed_from_conversation",
                {"conversation_id": conversation_id},
            )

        return success_response(
            {
                "message": "Participant removed successfully",
                "notification": notif_message.to_dict(),
            }
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to remove participant: {str(e)}")
        return error_response(f"Failed to remove participant: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# LEAVE GROUP CHAT (user removes themselves)
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>/leave", methods=["POST"])
@jwt_required()
def leave_conversation(conversation_id):
    """Allow a user to leave a group conversation."""
    try:
        current_user_id = get_jwt_identity()

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation:
            return error_response("Conversation not found", 404)

        # Can't leave direct conversations
        if conversation.conversation_type == "direct":
            return error_response(
                "Cannot leave a direct conversation. Use delete instead.", 400
            )

        # Can't leave general chat
        if conversation.conversation_type == "general":
            return error_response("Cannot leave the general chat", 400)

        if not conversation.is_user_participant(current_user_id):
            return error_response("You are not a participant in this conversation", 400)

        user = User.query.get(current_user_id)
        if not user:
            return error_response("User not found", 404)

        # If user is the creator and there are other participants, transfer ownership
        if conversation.created_by_id == current_user_id:
            other_participants = [
                p for p in conversation.participants if p.id != current_user_id
            ]
            if other_participants:
                # Transfer ownership to the first other participant
                new_owner = other_participants[0]
                conversation.created_by_id = new_owner.id

                # Update their role to admin
                stmt = (
                    conversation_participants.update()
                    .where(
                        (conversation_participants.c.conversation_id == conversation_id)
                        & (conversation_participants.c.user_id == new_owner.id)
                    )
                    .values(role="admin")
                )
                db.session.execute(stmt)

        # Remove the user from participants (simple delete, no left_at column needed)
        stmt = conversation_participants.delete().where(
            (conversation_participants.c.conversation_id == conversation_id)
            & (conversation_participants.c.user_id == current_user_id)
        )
        db.session.execute(stmt)

        # Add system message about leaving
        notif_content = f"👋 {user.get_full_name()} left the conversation"
        notif_message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=current_user_id,
            original_content=notif_content,
            message_type="system",
            metadata_data={"action": "participant_left", "user_id": current_user_id},
            sender_timezone="UTC",
        )
        db.session.add(notif_message)
        conversation.updated_at = datetime.utcnow()
        db.session.commit()

        # Emit socket events
        if SOCKET_ENABLED:
            emit_new_message(conversation_id, notif_message.to_dict())
            emit_to_user(
                current_user_id,
                "left_conversation",
                {"conversation_id": conversation_id},
            )

        return success_response(
            {"message": "You have left the conversation"},
            "Left conversation successfully",
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to leave conversation: {str(e)}")
        return error_response(f"Failed to leave conversation: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# ARCHIVE/HIDE CONVERSATION (for current user only)
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>/archive", methods=["POST"])
@jwt_required()
def archive_conversation(conversation_id):
    """Archive/hide a conversation for the current user only."""
    try:
        current_user_id = get_jwt_identity()

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation:
            return error_response("Conversation not found", 404)

        if not conversation.is_user_participant(current_user_id):
            return error_response("Access denied", 403)

        # Update the participant record to mark as archived
        stmt = (
            conversation_participants.update()
            .where(
                (conversation_participants.c.conversation_id == conversation_id)
                & (conversation_participants.c.user_id == current_user_id)
            )
            .values(is_archived=True, archived_at=datetime.utcnow())
        )
        db.session.execute(stmt)
        db.session.commit()

        return success_response(
            {"message": "Conversation archived"}, "Conversation archived successfully"
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to archive conversation: {str(e)}")
        return error_response(f"Failed to archive conversation: {str(e)}", 500)


@chat_bp.route("/conversations/<int:conversation_id>/unarchive", methods=["POST"])
@jwt_required()
def unarchive_conversation(conversation_id):
    """Unarchive a conversation for the current user."""
    try:
        current_user_id = get_jwt_identity()

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation:
            return error_response("Conversation not found", 404)

        stmt = (
            conversation_participants.update()
            .where(
                (conversation_participants.c.conversation_id == conversation_id)
                & (conversation_participants.c.user_id == current_user_id)
            )
            .values(is_archived=False, archived_at=None)
        )
        db.session.execute(stmt)
        db.session.commit()

        return success_response(
            {"message": "Conversation unarchived"},
            "Conversation unarchived successfully",
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to unarchive conversation: {str(e)}")
        return error_response(f"Failed to unarchive conversation: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# PIN / UNPIN CONVERSATION  (per-user, persists in DB)
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>/pin", methods=["POST"])
@jwt_required()
def pin_conversation(conversation_id):
    """Pin a conversation for the current user."""
    try:
        current_user_id = get_jwt_identity()
        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or not conversation.is_user_participant(current_user_id):
            return error_response("Conversation not found or access denied", 404)

        db.session.execute(
            db.text("""UPDATE conversation_participants
                       SET is_pinned = 1, pinned_at = :now
                       WHERE conversation_id = :cid AND user_id = :uid"""),
            {"cid": conversation_id, "uid": current_user_id, "now": datetime.utcnow()},
        )
        db.session.commit()

        # Emit to user so ChatDock + ChatPage both update in real-time
        if SOCKET_ENABLED:
            emit_to_user(
                current_user_id,
                "conversation_pinned",
                {"conversation_id": conversation_id, "is_pinned": True},
            )

        return success_response(
            {"conversation_id": conversation_id, "is_pinned": True},
            "Conversation pinned",
        )
    except Exception as e:
        logging.error(f"Pin conversation failed: {e}")
        db.session.rollback()
        return error_response(f"Failed to pin conversation: {str(e)}", 500)


@chat_bp.route("/conversations/<int:conversation_id>/pin", methods=["DELETE"])
@jwt_required()
def unpin_conversation(conversation_id):
    """Unpin a conversation for the current user."""
    try:
        current_user_id = get_jwt_identity()
        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or not conversation.is_user_participant(current_user_id):
            return error_response("Conversation not found or access denied", 404)

        db.session.execute(
            db.text("""UPDATE conversation_participants
                       SET is_pinned = 0, pinned_at = NULL
                       WHERE conversation_id = :cid AND user_id = :uid"""),
            {"cid": conversation_id, "uid": current_user_id},
        )
        db.session.commit()

        if SOCKET_ENABLED:
            emit_to_user(
                current_user_id,
                "conversation_pinned",
                {"conversation_id": conversation_id, "is_pinned": False},
            )

        return success_response(
            {"conversation_id": conversation_id, "is_pinned": False},
            "Conversation unpinned",
        )
    except Exception as e:
        logging.error(f"Unpin conversation failed: {e}")
        db.session.rollback()
        return error_response(f"Failed to unpin conversation: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# DELETE CONVERSATION (removes user from conversation)
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/conversations/<int:conversation_id>", methods=["DELETE"])
@jwt_required()
def delete_conversation(conversation_id):
    try:
        current_user_id = get_jwt_identity()

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation:
            return error_response("Conversation not found", 404)

        # Check if user is a participant
        if not conversation.is_user_participant(current_user_id):
            return error_response("You are not a participant in this conversation", 403)

        # Can't delete general chat
        if conversation.conversation_type == "general":
            return error_response("Cannot delete the general chat", 403)

        # Can't delete a group — must leave first
        if conversation.conversation_type == "group":
            return error_response(
                "You must leave this group before deleting it. Use Leave Group first.",
                403,
            )

        # Soft-hide only — stay participant so history is preserved and
        # the conversation reappears when a new message arrives
        conversation.hide_for_user(current_user_id)

        # Emit socket event
        if SOCKET_ENABLED:
            emit_to_user(
                current_user_id,
                "conversation_deleted",
                {"conversation_id": conversation_id},
            )

        return success_response({"message": "Conversation removed from your list"})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to delete conversation: {str(e)}")
        return error_response(f"Failed to delete conversation: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────
# TESTING: SETUP GENERAL CHAT
# ─────────────────────────────────────────────────────────────
@chat_bp.route("/setup-general-chat", methods=["POST"])
@jwt_required()
def setup_general_chat():
    from app.utils.chat_utils import (
        get_or_create_general_chat as _get_or_create,
        sync_all_users_to_general_chat,
    )

    current_user_id = get_jwt_identity()

    general_chat = _get_or_create(admin_user_id=current_user_id)
    stats = sync_all_users_to_general_chat()

    return success_response(
        {"general_chat_id": general_chat.id, "sync_stats": stats},
        "General chat setup complete!",
    )


# ─────────────────────────────────────────────────────────────
# FEATURE 3: STAR / UNSTAR A MESSAGE
# ─────────────────────────────────────────────────────────────
@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>/star",
    methods=["POST"],
)
@jwt_required()
def star_message(conversation_id, message_id):
    """Star a message for the current user."""
    try:
        current_user_id = get_jwt_identity()

        # Verify participation
        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or not conversation.is_user_participant(current_user_id):
            return error_response("Not a participant", 403)

        message = ChatMessage.query.get(message_id)
        if not message or message.conversation_id != conversation_id:
            return error_response("Message not found", 404)

        # Upsert into message_stars
        existing = db.session.execute(
            db.text(
                "SELECT id FROM message_stars WHERE user_id = :uid AND message_id = :mid"
            ),
            {"uid": current_user_id, "mid": message_id},
        ).fetchone()

        if not existing:
            db.session.execute(
                db.text(
                    "INSERT INTO message_stars (user_id, message_id, created_at) VALUES (:uid, :mid, :now)"
                ),
                {"uid": current_user_id, "mid": message_id, "now": datetime.utcnow()},
            )
            db.session.commit()

        return success_response(
            {"message_id": message_id, "is_starred": True}, "Message starred"
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Star message failed: {e}")
        return error_response(str(e), 500)


@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>/star",
    methods=["DELETE"],
)
@jwt_required()
def unstar_message(conversation_id, message_id):
    """Unstar a message."""
    try:
        current_user_id = get_jwt_identity()
        db.session.execute(
            db.text(
                "DELETE FROM message_stars WHERE user_id = :uid AND message_id = :mid"
            ),
            {"uid": current_user_id, "mid": message_id},
        )
        db.session.commit()
        return success_response(
            {"message_id": message_id, "is_starred": False}, "Message unstarred"
        )
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)


@chat_bp.route("/conversations/<int:conversation_id>/starred", methods=["GET"])
@jwt_required()
def get_starred_messages(conversation_id):
    """Get all starred messages in a conversation for the current user."""
    try:
        current_user_id = get_jwt_identity()
        rows = db.session.execute(
            db.text("""
                SELECT m.id, m.content, m.created_at, m.sender_id
                FROM chat_messages m
                JOIN message_stars s ON s.message_id = m.id
                WHERE m.conversation_id = :cid AND s.user_id = :uid
                ORDER BY s.created_at DESC
            """),
            {"cid": conversation_id, "uid": current_user_id},
        ).fetchall()
        messages = [
            {
                "id": r.id,
                "content": r.content,
                "created_at": str(r.created_at),
                "sender_id": r.sender_id,
            }
            for r in rows
        ]
        return success_response({"messages": messages}, "Starred messages fetched")
    except Exception as e:
        return error_response(str(e), 500)


# ─────────────────────────────────────────────────────────────
# FEATURE 3: PIN / UNPIN A MESSAGE
# ─────────────────────────────────────────────────────────────
@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>/pin",
    methods=["POST"],
)
@jwt_required()
def pin_message(conversation_id, message_id):
    """Pin a message in a conversation (admins or any participant)."""
    try:
        current_user_id = get_jwt_identity()

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or not conversation.is_user_participant(current_user_id):
            return error_response("Not a participant", 403)

        message = ChatMessage.query.get(message_id)
        if not message or message.conversation_id != conversation_id:
            return error_response("Message not found", 404)

        existing = db.session.execute(
            db.text(
                "SELECT id FROM pinned_messages WHERE conversation_id = :cid AND message_id = :mid"
            ),
            {"cid": conversation_id, "mid": message_id},
        ).fetchone()

        if not existing:
            db.session.execute(
                db.text("""
                    INSERT INTO pinned_messages (conversation_id, message_id, pinned_by, created_at)
                    VALUES (:cid, :mid, :uid, :now)
                """),
                {
                    "cid": conversation_id,
                    "mid": message_id,
                    "uid": current_user_id,
                    "now": datetime.utcnow(),
                },
            )
            db.session.commit()

        return success_response(
            {"message_id": message_id, "is_pinned": True}, "Message pinned"
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Pin message failed: {e}")
        return error_response(str(e), 500)


@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>/pin",
    methods=["DELETE"],
)
@jwt_required()
def unpin_message(conversation_id, message_id):
    """Unpin a message."""
    try:
        current_user_id = get_jwt_identity()
        db.session.execute(
            db.text(
                "DELETE FROM pinned_messages WHERE conversation_id = :cid AND message_id = :mid"
            ),
            {"cid": conversation_id, "mid": message_id},
        )
        db.session.commit()
        return success_response(
            {"message_id": message_id, "is_pinned": False}, "Message unpinned"
        )
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)


@chat_bp.route("/conversations/<int:conversation_id>/pinned", methods=["GET"])
@jwt_required()
def get_pinned_messages(conversation_id):
    """Get all pinned messages in a conversation."""
    try:
        current_user_id = get_jwt_identity()
        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or not conversation.is_user_participant(current_user_id):
            return error_response("Not a participant", 403)

        rows = db.session.execute(
            db.text("""
                SELECT m.id, m.content, m.created_at, m.sender_id, p.pinned_by
                FROM chat_messages m
                JOIN pinned_messages p ON p.message_id = m.id
                WHERE p.conversation_id = :cid
                ORDER BY p.created_at DESC
            """),
            {"cid": conversation_id},
        ).fetchall()
        messages = [
            {
                "id": r.id,
                "content": r.content,
                "created_at": str(r.created_at),
                "sender_id": r.sender_id,
                "pinned_by": r.pinned_by,
            }
            for r in rows
        ]
        return success_response({"messages": messages}, "Pinned messages fetched")
    except Exception as e:
        return error_response(str(e), 500)


# ─────────────────────────────────────────────────────────────
# FEATURE 3: SAVE / REMOVE MESSAGE AS TASK
# ─────────────────────────────────────────────────────────────
@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>/task",
    methods=["POST"],
)
@jwt_required()
def save_message_task(conversation_id, message_id):
    """Save a message as a task for the current user."""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}
        due_date = data.get("due_date")
        note = data.get("note")

        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or not conversation.is_user_participant(current_user_id):
            return error_response("Not a participant", 403)

        message = ChatMessage.query.get(message_id)
        if not message or message.conversation_id != conversation_id:
            return error_response("Message not found", 404)

        # Upsert
        existing = db.session.execute(
            db.text(
                "SELECT id FROM message_tasks WHERE user_id = :uid AND message_id = :mid"
            ),
            {"uid": current_user_id, "mid": message_id},
        ).fetchone()

        if existing:
            db.session.execute(
                db.text(
                    "UPDATE message_tasks SET due_date = :dd, note = :note WHERE user_id = :uid AND message_id = :mid"
                ),
                {
                    "dd": due_date,
                    "note": note,
                    "uid": current_user_id,
                    "mid": message_id,
                },
            )
        else:
            db.session.execute(
                db.text("""
                    INSERT INTO message_tasks (user_id, message_id, conversation_id, due_date, note, created_at)
                    VALUES (:uid, :mid, :cid, :dd, :note, :now)
                """),
                {
                    "uid": current_user_id,
                    "mid": message_id,
                    "cid": conversation_id,
                    "dd": due_date,
                    "note": note,
                    "now": datetime.utcnow(),
                },
            )
        db.session.commit()
        return success_response(
            {"message_id": message_id, "is_task": True}, "Task saved"
        )

    except Exception as e:
        db.session.rollback()
        logging.error(f"Save task failed: {e}")
        return error_response(str(e), 500)


@chat_bp.route(
    "/conversations/<int:conversation_id>/messages/<int:message_id>/task",
    methods=["DELETE"],
)
@jwt_required()
def remove_message_task(conversation_id, message_id):
    """Remove a message task."""
    try:
        current_user_id = get_jwt_identity()
        db.session.execute(
            db.text(
                "DELETE FROM message_tasks WHERE user_id = :uid AND message_id = :mid"
            ),
            {"uid": current_user_id, "mid": message_id},
        )
        db.session.commit()
        return success_response(
            {"message_id": message_id, "is_task": False}, "Task removed"
        )
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)


@chat_bp.route("/tasks", methods=["GET"])
@jwt_required()
def get_my_tasks():
    """Get all tasks saved by the current user."""
    try:
        current_user_id = get_jwt_identity()
        rows = db.session.execute(
            db.text("""
                SELECT t.id, t.message_id, t.conversation_id, t.due_date, t.note, t.created_at,
                       m.content, m.sender_id
                FROM message_tasks t
                JOIN chat_messages m ON m.id = t.message_id
                WHERE t.user_id = :uid
                ORDER BY t.created_at DESC
            """),
            {"uid": current_user_id},
        ).fetchall()
        tasks = [
            {
                "id": r.id,
                "message_id": r.message_id,
                "conversation_id": r.conversation_id,
                "due_date": str(r.due_date) if r.due_date else None,
                "note": r.note,
                "created_at": str(r.created_at),
                "message_content": r.content,
                "sender_id": r.sender_id,
            }
            for r in rows
        ]
        return success_response({"tasks": tasks}, "Tasks fetched")
    except Exception as e:
        return error_response(str(e), 500)
