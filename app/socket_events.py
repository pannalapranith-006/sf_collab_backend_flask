"""
socket_events.py  —  Refactored with centralized PresenceManager.

Key changes from original:
- PresenceManager is the single source of truth for online/idle/offline state.
- Broadcasts a unified `presence_update` event on every state change.
- Heartbeat handler refreshes last_active without a reconnect cycle.
- last_seen is stamped in UTC only on disconnect — never on activity.
- Away detection uses IDLE_THRESHOLD_SECS = 300 (5 minutes), matching the frontend.
- Background thread checks every 30 s and emits presence_update for idle users.
"""

from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio, db
from flask_jwt_extended import decode_token
from flask import request
from datetime import datetime, timedelta
import threading
import logging

print("✅ socket_events.py loaded")

# ─── Presence Manager ─────────────────────────────────────────────────────────

class PresenceManager:
    """
    Single source of truth for all connected-user presence data.

    Internal structure per user_id (string):
        {
            "sids":        set of active socket session IDs,
            "last_active": datetime (UTC),
            "last_seen":   datetime (UTC) | None,
            "status":      "online" | "idle" | "offline",
        }
    """

    IDLE_THRESHOLD_SECS = 300   # 5 minutes — must match IDLE_THRESHOLD_MS on frontend
    CHECK_INTERVAL_SECS = 30    # background thread cadence

    def __init__(self):
        self._lock  = threading.Lock()
        self._users = {}        # { user_id: { sids, last_active, last_seen, status } }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_or_create(self, user_id):
        uid = str(user_id)
        if uid not in self._users:
            self._users[uid] = {
                "sids":        set(),
                "last_active": datetime.utcnow(),
                "last_seen":   None,
                "status":      "offline",
            }
        return self._users[uid]

    def _broadcast_presence(self, user_id, status, last_seen_iso=None):
        """Emit the unified presence_update event to all connected clients."""
        socketio.emit("presence_update", {
            "user_id":   str(user_id),
            "status":    status,
            "last_seen": last_seen_iso,
        })
        # Also emit legacy user_status so older frontend code still works
        socketio.emit("user_status", {
            "user_id":   str(user_id),
            "status":    status,
            "last_seen": last_seen_iso,
            "timestamp": last_seen_iso or datetime.utcnow().isoformat(),
        })

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self, user_id, sid):
        uid = str(user_id)
        now = datetime.utcnow()
        with self._lock:
            entry = self._get_or_create(uid)
            entry["sids"].add(sid)
            entry["last_active"] = now
            entry["status"]      = "online"
        self._broadcast_presence(uid, "online", now.isoformat())
        logging.info(f"[Presence] User {uid} ONLINE (sid={sid})")

    def disconnect(self, user_id, sid):
        uid = str(user_id)
        now = datetime.utcnow()
        broadcast_offline = False
        with self._lock:
            entry = self._users.get(uid)
            if not entry:
                return
            entry["sids"].discard(sid)
            if not entry["sids"]:
                # Last session closed — user is truly offline
                entry["last_seen"] = now
                entry["status"]    = "offline"
                broadcast_offline  = True

        if broadcast_offline:
            # Persist last_seen in DB
            try:
                from app.models.user import User
                user = User.query.get(int(uid))
                if user and hasattr(user, "last_seen"):
                    user.last_seen = now
                    db.session.commit()
            except Exception as e:
                logging.warning(f"[Presence] Could not persist last_seen for {uid}: {e}")
            self._broadcast_presence(uid, "offline", now.isoformat())
            logging.info(f"[Presence] User {uid} OFFLINE")

    def record_activity(self, user_id):
        """Call when a user sends a message, heartbeat, or any interaction."""
        uid = str(user_id)
        now = datetime.utcnow()
        was_idle = False
        with self._lock:
            entry = self._users.get(uid)
            if not entry or not entry["sids"]:
                return   # user not connected, ignore
            was_idle           = entry["status"] == "idle"
            entry["last_active"] = now
            entry["status"]      = "online"

        # Broadcast activity timestamp to all clients so they update idle timers
        socketio.emit("user_activity", {
            "user_id": uid,
            "ts":      now.isoformat(),
        })
        # If recovering from idle — send an explicit online event
        if was_idle:
            self._broadcast_presence(uid, "online", now.isoformat())
            logging.info(f"[Presence] User {uid} recovered from IDLE")

    def get_online_user_ids(self):
        with self._lock:
            return [uid for uid, e in self._users.items() if e["sids"]]

    def is_online(self, user_id):
        with self._lock:
            entry = self._users.get(str(user_id))
            return bool(entry and entry["sids"])

    def get_sid_user(self, sid):
        """Reverse-lookup: which user_id owns this sid?"""
        with self._lock:
            for uid, entry in self._users.items():
                if sid in entry["sids"]:
                    return uid
        return None

    # ── Background idle checker ───────────────────────────────────────────────

    def _idle_check_loop(self):
        import time
        while True:
            time.sleep(self.CHECK_INTERVAL_SECS)
            try:
                now = datetime.utcnow()
                with self._lock:
                    snapshot = list(self._users.items())

                for uid, entry in snapshot:
                    if not entry["sids"]:
                        continue   # already offline
                    if entry["status"] == "idle":
                        continue   # already marked idle

                    gap = (now - entry["last_active"]).total_seconds()
                    if gap >= self.IDLE_THRESHOLD_SECS:
                        with self._lock:
                            # Re-check under lock to avoid race
                            e2 = self._users.get(uid)
                            if not e2 or not e2["sids"]:
                                continue
                            e2["status"] = "idle"
                        self._broadcast_presence(uid, "idle", None)
                        logging.info(f"[Presence] User {uid} IDLE after {gap:.0f}s")
            except Exception as e:
                logging.warning(f"[Presence] idle_check_loop error: {e}")

    def start_background_thread(self):
        t = threading.Thread(target=self._idle_check_loop, daemon=True)
        t.start()


# Module-level singleton
presence = PresenceManager()
presence.start_background_thread()

# ─── Session registry (sid → user_id) ─────────────────────────────────────────
# Kept separate so socket handlers can look up user_id from request.sid quickly.
socket_sessions = {}   # { sid: user_id_str }


# ─── Auth helper ──────────────────────────────────────────────────────────────

def _user_id_from_token(token):
    try:
        decoded = decode_token(token)
        return str(decoded.get("sub"))
    except Exception as e:
        logging.error(f"[Socket] JWT decode error: {e}")
        return None


# ─── Connect / disconnect ─────────────────────────────────────────────────────

@socketio.on("connect")
def handle_connect(auth):
    token = (auth or {}).get("token")
    if not token:
        logging.warning("[Socket] connect rejected — no token")
        return False

    user_id = _user_id_from_token(token)
    if not user_id:
        logging.warning("[Socket] connect rejected — bad token")
        return False

    sid = request.sid
    socket_sessions[sid] = user_id

    join_room(f"user_{user_id}")
    presence.connect(user_id, sid)

    # Send full online-user snapshot to the newly connected client
    emit("online_users", {"user_ids": presence.get_online_user_ids()})
    logging.info(f"[Socket] User {user_id} connected (sid={sid})")


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    sid     = request.sid
    user_id = socket_sessions.pop(sid, None)
    if not user_id:
        return
    presence.disconnect(user_id, sid)
    logging.info(f"[Socket] User {user_id} disconnected (sid={sid}, reason={reason})")


# ─── Heartbeat ────────────────────────────────────────────────────────────────

@socketio.on("heartbeat")
def handle_heartbeat(data):
    """Client sends this every 30 s to stay alive and reset idle timer."""
    sid     = request.sid
    user_id = socket_sessions.get(sid)
    if not user_id:
        return
    presence.record_activity(user_id)


# ─── User activity (messages, typing, etc.) ───────────────────────────────────

@socketio.on("user_activity")
def handle_user_activity(data):
    """
    Explicit activity ping — sent by client on message send / typing.
    Resets the idle clock and broadcasts the fresh timestamp.
    """
    sid     = request.sid
    user_id = socket_sessions.get(sid)
    if not user_id:
        return
    presence.record_activity(user_id)


# ─── Online-user snapshot ─────────────────────────────────────────────────────

@socketio.on("get_online_users")
def handle_get_online_users():
    emit("online_users", {"user_ids": presence.get_online_user_ids()})


# ─── Conversation rooms ───────────────────────────────────────────────────────

@socketio.on("join_conversation")
def handle_join_conversation(data):
    sid     = request.sid
    user_id = socket_sessions.get(sid)
    if not user_id:
        return
    conversation_id = data.get("conversation_id")
    room = f"conversation_{conversation_id}"
    join_room(room)
    emit("user_joined_conversation", {
        "user_id":         user_id,
        "conversation_id": conversation_id,
        "timestamp":       datetime.utcnow().isoformat(),
    }, room=room, include_self=False)


@socketio.on("leave_conversation")
def handle_leave_conversation(data):
    sid     = request.sid
    user_id = socket_sessions.get(sid)
    if not user_id:
        return
    conversation_id = data.get("conversation_id")
    room = f"conversation_{conversation_id}"
    leave_room(room)
    emit("user_left_conversation", {
        "user_id":         user_id,
        "conversation_id": conversation_id,
        "timestamp":       datetime.utcnow().isoformat(),
    }, room=room, include_self=False)


# ─── Messaging ────────────────────────────────────────────────────────────────

@socketio.on("send_message")
def handle_send_message(data):
    from app.models.chatConversation import ChatConversation
    from app.models.chatMessage import ChatMessage
    from app.models.user import User

    sid     = request.sid
    user_id = socket_sessions.get(sid)
    if not user_id:
        emit("error", {"message": "Not authenticated"})
        return

    conversation_id = data.get("conversation_id")
    content         = (data.get("content") or "").strip()
    file_url        = data.get("file_url")
    file_name       = data.get("file_name")
    file_type       = data.get("file_type")
    message_type    = str(data.get("message_type") or "text").lower()
    reply_to_id     = data.get("reply_to_id")

    has_file      = bool(file_url)
    is_image_type = isinstance(file_type, str) and file_type.startswith("image/")
    derived_image = message_type == "image" or is_image_type

    if not content and not has_file:
        emit("error", {"message": "Content or file_url required"})
        return
    if message_type in ("image", "file") and not has_file:
        emit("error", {"message": "file_url required for image/file messages"})
        return

    try:
        user         = User.query.get(int(user_id))
        conversation = ChatConversation.query.get(conversation_id)

        if not user or not conversation:
            emit("error", {"message": "User or conversation not found"})
            return
        if not conversation.is_user_participant(int(user_id)):
            emit("error", {"message": "Not a participant"})
            return

        message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=int(user_id),
            original_content=content,
            message_type=message_type,
            reply_to_id=reply_to_id,
            file_url=file_url,
            file_name=file_name,
            file_type=file_type,
            metadata_data={"is_image": derived_image} if (has_file or message_type in ("image", "file")) else {},
            sender_timezone=user.get_timezone() if hasattr(user, "get_timezone") else "UTC",
        )
        db.session.add(message)
        conversation.updated_at = datetime.utcnow()
        conversation.increment_unread_count(int(user_id))
        db.session.commit()

        # Un-hide conversation for other participants who hid it
        for participant in conversation.participants:
            if str(participant.id) != str(user_id):
                if conversation.is_hidden_for_user(participant.id):
                    conversation.unhide_for_user(participant.id)

        message_data = message.to_dict(for_user=user)
        message_data["sender"] = {
            "id":             user.id,
            "firstName":      user.first_name,
            "lastName":       user.last_name,
            "profilePicture": user.profile_picture,
        }

        room = f"conversation_{conversation_id}"
        emit("new_message", {
            "message":         message_data,
            "conversation_id": conversation_id,
            "conversation": {
                "id":                conversation_id,
                "conversation_type": conversation.conversation_type,
                "name":              conversation.name,
            },
        }, room=room)

        # Record activity so idle clock resets for the sender
        presence.record_activity(user_id)

    except Exception as e:
        logging.error(f"[Socket] send_message error: {e}", exc_info=True)
        db.session.rollback()
        emit("error", {"message": "Failed to send message"})


# ─── Mark as read ─────────────────────────────────────────────────────────────

@socketio.on("mark_as_read")
def handle_mark_as_read(data):
    from app.models.chatConversation import ChatConversation
    from app.models.chatMessage import ChatMessage

    sid     = request.sid
    user_id = socket_sessions.get(sid)
    if not user_id:
        return

    conversation_id = data.get("conversation_id")
    if not conversation_id:
        return

    try:
        conversation = ChatConversation.query.get(conversation_id)
        if not conversation or not conversation.is_user_participant(int(user_id)):
            return

        unread_messages = (
            ChatMessage.query
            .filter_by(conversation_id=conversation_id)
            .filter(ChatMessage.sender_id != int(user_id))
            .all()
        )

        conversation.mark_as_read(int(user_id))

        try:
            remaining = conversation.get_unread_message_count(int(user_id))
        except Exception:
            remaining = 0

        socketio.emit("unread_count_update", {
            "conversation_id": conversation_id,
            "unread_count":    remaining,
            "user_id":         user_id,
        }, room=f"user_{user_id}")

        now_iso = datetime.utcnow().isoformat()
        room    = f"conversation_{conversation_id}"
        emit("messages_read", {
            "user_id":         user_id,
            "conversation_id": conversation_id,
            "timestamp":       now_iso,
        }, room=room)

        notified = set()
        for msg in unread_messages:
            sender_id = str(msg.sender_id)
            socketio.emit("message_status_update", {
                "message_id":      msg.id,
                "conversation_id": conversation_id,
                "status":          "read",
                "read_at":         now_iso,
                "read_by":         user_id,
            }, room=f"user_{sender_id}")
            notified.add(sender_id)

    except Exception as e:
        logging.error(f"[Socket] mark_as_read error: {e}", exc_info=True)


# ─── Notifications room ───────────────────────────────────────────────────────

@socketio.on("join_notifications")
def handle_join_notifications(data):
    sid     = request.sid
    user_id = socket_sessions.get(sid)
    if not user_id:
        return
    requested = str((data or {}).get("user_id", ""))
    if requested and requested != str(user_id):
        logging.warning(f"[Socket] User {user_id} tried to join notifications room for {requested}")
        return
    join_room(f"user_{user_id}")
    emit("notifications_room_joined", {"user_id": user_id})


# ─── Helper functions (called from Flask routes) ───────────────────────────────

def emit_to_user(user_id, event, data):
    socketio.emit(event, data, room=f"user_{user_id}")

def emit_new_message(conversation_id, message_data):
    socketio.emit("new_message", {
        "message":         message_data,
        "conversation_id": conversation_id,
    }, room=f"conversation_{conversation_id}")

def emit_message_edited(conversation_id, message_data):
    socketio.emit("message_edited", {
        "message":         message_data,
        "conversation_id": conversation_id,
    }, room=f"conversation_{conversation_id}")

def emit_message_deleted(conversation_id, message_id):
    socketio.emit("message_deleted", {
        "message_id":      message_id,
        "conversation_id": conversation_id,
    }, room=f"conversation_{conversation_id}")

def emit_notification(user_id, notification_data):
    try:
        socketio.emit("new_notification", {
            "notification": notification_data,
            "timestamp":    datetime.utcnow().isoformat(),
        }, room=f"user_{user_id}")
    except Exception as e:
        logging.error(f"[Socket] emit_notification error: {e}")

def emit_user_left_conversation(conversation_id, user_id, user_name):
    socketio.emit("user_left_conversation", {
        "conversation_id": conversation_id,
        "user_id":         user_id,
        "user_name":       user_name,
    }, room=f"conversation_{conversation_id}")

def is_user_online(user_id):
    return presence.is_online(user_id)