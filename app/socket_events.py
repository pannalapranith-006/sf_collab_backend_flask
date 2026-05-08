"""
socket_events.py  —  Refactored with centralized PresenceManager.

Key changes from original:
- PresenceManager is the single source of truth for online/idle/offline state.
- Broadcasts a unified `presence_update` event on every state change.
- Heartbeat handler refreshes last_active without a reconnect cycle.
- last_seen is stamped in UTC only on disconnect — never on activity.
- Away detection uses IDLE_THRESHOLD_SECS = 300 (5 minutes), matching the frontend.
- Background thread checks every 30 s and emits presence_update for idle users.
- SF Meet real-time collaboration events appended at the bottom.
"""

from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio, db
from flask_jwt_extended import decode_token
from flask import request
from datetime import datetime, timedelta
import threading
import logging

print("✅ socket_events.py loaded")

# ── SF Meet room state ────────────────────────────────────────────────────────
_meeting_rooms  = {}   # { mid_str: { uid_str: {sid,name,avatar,joined_at,cursor} } }
_sid_to_meeting = {}   # { sid: (mid_str, uid_str) }

def _meet_room(mid):  return f"meeting_{mid}"
def _meet_participants(mid):
    return [
        {"user_id": uid, "name": p["name"], "avatar": p["avatar"],
         "joined_at": p["joined_at"], "cursor": p.get("cursor")}
        for uid, p in _meeting_rooms.get(str(mid), {}).items()
    ]

# ─── Presence Manager ─────────────────────────────────────────────────────────

class PresenceManager:
    IDLE_THRESHOLD_SECS = 300
    CHECK_INTERVAL_SECS = 30

    def __init__(self):
        self._lock  = threading.Lock()
        self._users = {}

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
        socketio.emit("presence_update", {
            "user_id":   str(user_id),
            "status":    status,
            "last_seen": last_seen_iso,
        })
        socketio.emit("user_status", {
            "user_id":   str(user_id),
            "status":    status,
            "last_seen": last_seen_iso,
            "timestamp": last_seen_iso or datetime.utcnow().isoformat(),
        })

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
                entry["last_seen"] = now
                entry["status"]    = "offline"
                broadcast_offline  = True
        if broadcast_offline:
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
        uid = str(user_id)
        now = datetime.utcnow()
        was_idle = False
        with self._lock:
            entry = self._users.get(uid)
            if not entry or not entry["sids"]:
                return
            was_idle             = entry["status"] == "idle"
            entry["last_active"] = now
            entry["status"]      = "online"
        socketio.emit("user_activity", {"user_id": uid, "ts": now.isoformat()})
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
        with self._lock:
            for uid, entry in self._users.items():
                if sid in entry["sids"]:
                    return uid
        return None

    def _idle_check_loop(self):
        import time
        while True:
            time.sleep(self.CHECK_INTERVAL_SECS)
            try:
                now = datetime.utcnow()
                with self._lock:
                    snapshot = list(self._users.items())
                for uid, entry in snapshot:
                    if not entry["sids"] or entry["status"] == "idle":
                        continue
                    gap = (now - entry["last_active"]).total_seconds()
                    if gap >= self.IDLE_THRESHOLD_SECS:
                        with self._lock:
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


presence = PresenceManager()
presence.start_background_thread()

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
    emit("online_users", {"user_ids": presence.get_online_user_ids()})
    logging.info(f"[Socket] User {user_id} connected (sid={sid})")


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    sid     = request.sid
    user_id = socket_sessions.pop(sid, None)
    if user_id:
        presence.disconnect(user_id, sid)
        logging.info(f"[Socket] User {user_id} disconnected (sid={sid}, reason={reason})")

    # ── SF Meet cleanup ───────────────────────────────────────────────────────
    if sid in _sid_to_meeting:
        meeting_id, meet_user_id = _sid_to_meeting.pop(sid)
        room_data   = _meeting_rooms.get(meeting_id, {})
        participant = room_data.pop(meet_user_id, None)
        if not room_data:
            _meeting_rooms.pop(meeting_id, None)
        if participant:
            leave_room(_meet_room(meeting_id))
            socketio.emit("meet_participant_left", {
                "meeting_id": meeting_id,
                "user_id":    meet_user_id,
                "name":       participant["name"],
                "reason":     "disconnected",
                "left_at":    datetime.utcnow().isoformat(),
            }, room=_meet_room(meeting_id))
            try:
                from app.models.meet_participant import MeetParticipant
                p = MeetParticipant.query.filter_by(
                    meeting_id=int(meeting_id), user_id=int(meet_user_id)).first()
                if p:
                    p.left_at = datetime.utcnow()
                    db.session.commit()
            except Exception as e:
                logging.warning(f"[MeetSocket] left_at update failed: {e}")


# ─── Heartbeat ────────────────────────────────────────────────────────────────

@socketio.on("heartbeat")
def handle_heartbeat(data):
    user_id = socket_sessions.get(request.sid)
    if user_id:
        presence.record_activity(user_id)


@socketio.on("user_activity")
def handle_user_activity(data):
    user_id = socket_sessions.get(request.sid)
    if user_id:
        presence.record_activity(user_id)


@socketio.on("get_online_users")
def handle_get_online_users():
    emit("online_users", {"user_ids": presence.get_online_user_ids()})


# ─── Conversation rooms ───────────────────────────────────────────────────────

@socketio.on("join_conversation")
def handle_join_conversation(data):
    user_id = socket_sessions.get(request.sid)
    if not user_id:
        return
    conversation_id = data.get("conversation_id")
    room = f"conversation_{conversation_id}"
    join_room(room)
    emit("user_joined_conversation", {
        "user_id": user_id, "conversation_id": conversation_id,
        "timestamp": datetime.utcnow().isoformat(),
    }, room=room, include_self=False)


@socketio.on("leave_conversation")
def handle_leave_conversation(data):
    user_id = socket_sessions.get(request.sid)
    if not user_id:
        return
    conversation_id = data.get("conversation_id")
    room = f"conversation_{conversation_id}"
    leave_room(room)
    emit("user_left_conversation", {
        "user_id": user_id, "conversation_id": conversation_id,
        "timestamp": datetime.utcnow().isoformat(),
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

    
    user_id = socket_sessions[sid]['user_id']
    conversation_id = data.get('conversation_id')
    content = data.get('content', '').strip()
    file_url = data.get('file_url')
    file_name = data.get('file_name')
    file_type = data.get('file_type')
    message_type = str(data.get('message_type', 'text') or 'text').lower()
    reply_to_id = data.get('reply_to_id')
    skip_persist = bool(data.get('skip_persist'))
    persisted_message_id = data.get('persisted_message_id')

    has_file_url = bool(file_url)
    file_type_is_image = isinstance(file_type, str) and file_type.startswith('image/')
    derived_is_image = message_type == 'image' or file_type_is_image
    
    if not skip_persist and not content and not has_file_url:
        emit('error', {'message': 'Message content or file URL is required'})
        return

    if not skip_persist and message_type in ('image', 'file') and not has_file_url:
        emit('error', {'message': 'file_url is required for image/file messages'})
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
            conversation_id  = conversation_id,
            sender_id        = int(user_id),
            original_content = content,
            message_type     = message_type,
            reply_to_id      = reply_to_id,
            file_url         = file_url,
            file_name        = file_name,
            file_type        = file_type,
            metadata_data    = {"is_image": derived_image} if (has_file or message_type in ("image", "file")) else {},
            sender_timezone  = user.get_timezone() if hasattr(user, "get_timezone") else "UTC",
        )
        db.session.add(message)
        conversation.updated_at = datetime.utcnow()
        conversation.increment_unread_count(int(user_id))
        db.session.commit()
        
        if skip_persist:
            # Broadcast an already-persisted REST message to user rooms only.
            if not persisted_message_id:
                emit('error', {'message': 'persisted_message_id is required when skip_persist is true'})
                return

            message = ChatMessage.query.get(persisted_message_id)
            if not message:
                emit('error', {'message': 'Persisted message not found'})
                return

            if str(message.conversation_id) != str(conversation_id) or str(message.sender_id) != str(user_id):
                emit('error', {'message': 'Persisted message does not match sender/conversation'})
                return

            message_data = message.to_dict(for_user=user)
            message_data['sender'] = {
                'id': user.id,
                'firstName': user.first_name,
                'lastName': user.last_name,
                'profilePicture': user.profile_picture
            }
        else:
            # Create message - Now including file fields
            message = ChatMessage(
                conversation_id=conversation_id,
                sender_id=user_id,
                original_content=content,
                message_type=message_type,
                reply_to_id=reply_to_id,
                file_url=file_url,
                file_name=file_name,
                file_type=file_type,
                metadata_data={'is_image': derived_is_image} if (has_file_url or message_type in ('image', 'file')) else {},
                sender_timezone=user.get_timezone() if hasattr(user, 'get_timezone') else 'UTC'
            )

            db.session.add(message)
            conversation.updated_at = datetime.utcnow()
            conversation.increment_unread_count(user_id)
            db.session.commit()

            # Prepare message data
            message_data = message.to_dict(for_user=user)
            message_data['sender'] = {
                'id': user.id,
                'firstName': user.first_name,
                'lastName': user.last_name,
                'profilePicture': user.profile_picture
            }

        for participant in conversation.participants:
            if str(participant.id) != str(user_id):
                if conversation.is_hidden_for_user(participant.id):
                    conversation.unhide_for_user(participant.id)

        message_data = message.to_dict(for_user=user)
        message_data["sender"] = {
            "id": user.id, "firstName": user.first_name,
            "lastName": user.last_name, "profilePicture": user.profile_picture,
        }

        emit("new_message", {
            "message": message_data, "conversation_id": conversation_id,
            "conversation": {
                "id": conversation_id,
                "conversation_type": conversation.conversation_type,
                "name": conversation.name,
            },
        }, room=room)
        
        # Broadcast to active room only when this path created the message.
        if not skip_persist:
            emit('new_message', {
                'message': message_data,
                'conversation_id': conversation_id,
                'conversation': conversation_meta,
            }, room=room)

        # Emit to each participant's user room (GLOBAL updates)
        for participant in conversation.participants:
            emit('conversation_message', {
                'conversation_id': conversation_id,
                'message': message_data,
                'conversation': conversation_meta,
            }, room=f"user_{participant.id}")

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
        emit("messages_read", {
            "user_id": user_id, "conversation_id": conversation_id,
            "timestamp": now_iso,
        }, room=f"conversation_{conversation_id}")

        for msg in unread_messages:
            sender_id = str(msg.sender_id)
            socketio.emit("message_status_update", {
                "message_id": msg.id, "conversation_id": conversation_id,
                "status": "read", "read_at": now_iso, "read_by": user_id,
            }, room=f"user_{sender_id}")

    except Exception as e:
        logging.error(f"[Socket] mark_as_read error: {e}", exc_info=True)


# ─── Notifications room ───────────────────────────────────────────────────────

@socketio.on("join_notifications")
def handle_join_notifications(data):
    user_id = socket_sessions.get(request.sid)
    if not user_id:
        return
    requested = str((data or {}).get("user_id", ""))
    if requested and requested != str(user_id):
        logging.warning(f"[Socket] User {user_id} tried to join notifications for {requested}")
        return
    join_room(f"user_{user_id}")
    emit("notifications_room_joined", {"user_id": user_id})


# ══════════════════════════════════════════════════════════════════════════════
# SF MEET — REAL-TIME COLLABORATION
# ══════════════════════════════════════════════════════════════════════════════

@socketio.on("meet_join")
def handle_meet_join(data):
    """
    Client: { token, meeting_id }
    Validates JWT + participant status, joins socket room,
    broadcasts meet_participant_joined, sends meet_participant_list to joiner.
    """
    sid        = request.sid
    token      = (data or {}).get("token")
    meeting_id = str((data or {}).get("meeting_id", ""))

    if not token or not meeting_id:
        emit("meet_error", {"message": "token and meeting_id required"})
        return

    user_id = _user_id_from_token(token)
    if not user_id:
        emit("meet_error", {"message": "Invalid token"})
        return

    # Resolve name + avatar
    try:
        from app.models.user import User
        u = User.query.get(int(user_id))
        name   = f"{u.first_name} {u.last_name}".strip() if u else "Unknown"
        avatar = getattr(u, "profile_picture", None) if u else None
    except Exception:
        name, avatar = "Unknown", None

    # Verify participant
    try:
        from app.models.meet_meeting import MeetMeeting
        from app.models.meet_participant import MeetParticipant
        meeting = MeetMeeting.query.get(int(meeting_id))
        if not meeting:
            emit("meet_error", {"message": "Meeting not found"})
            return
        authorized = (
            str(meeting.owner_user_id) == user_id or
            MeetParticipant.query.filter_by(
                meeting_id=int(meeting_id), user_id=int(user_id)).first()
        )
        if not authorized:
            emit("meet_error", {"message": "Not a participant"})
            return
    except Exception as e:
        logging.error(f"[MeetSocket] join DB error: {e}")
        emit("meet_error", {"message": "Server error"})
        return

    joined_at = datetime.utcnow().isoformat()
    _meeting_rooms.setdefault(meeting_id, {})[user_id] = {
        "sid": sid, "name": name, "avatar": avatar,
        "joined_at": joined_at, "cursor": None,
    }
    _sid_to_meeting[sid] = (meeting_id, user_id)
    join_room(_meet_room(meeting_id))

    # Notify others
    emit("meet_participant_joined", {
        "meeting_id": meeting_id, "user_id": user_id,
        "name": name, "avatar": avatar, "joined_at": joined_at,
    }, room=_meet_room(meeting_id), include_self=False)

    # Send full list to joiner
    emit("meet_participant_list", {
        "meeting_id": meeting_id,
        "participants": _meet_participants(meeting_id),
    })

    # Update DB attendance
    try:
        from app.models.meet_participant import MeetParticipant, AttendanceStatus
        p = MeetParticipant.query.filter_by(
            meeting_id=int(meeting_id), user_id=int(user_id)).first()
        if p:
            p.joined_at         = datetime.utcnow()
            p.attendance_status = AttendanceStatus.attended
            db.session.commit()
    except Exception as e:
        logging.warning(f"[MeetSocket] attendance update failed: {e}")

    logging.info(f"[MeetSocket] {user_id} joined meeting {meeting_id}")


@socketio.on("meet_leave")
def handle_meet_leave(data):
    """Client: { meeting_id }"""
    sid        = request.sid
    meeting_id = str((data or {}).get("meeting_id", ""))
    lookup     = _sid_to_meeting.pop(sid, None)
    if not lookup:
        return
    meeting_id, user_id = lookup
    room_data   = _meeting_rooms.get(meeting_id, {})
    participant = room_data.pop(user_id, None)
    if not room_data:
        _meeting_rooms.pop(meeting_id, None)
    if participant:
        leave_room(_meet_room(meeting_id))
        socketio.emit("meet_participant_left", {
            "meeting_id": meeting_id, "user_id": user_id,
            "name": participant["name"], "reason": "left",
            "left_at": datetime.utcnow().isoformat(),
        }, room=_meet_room(meeting_id))
        try:
            from app.models.meet_participant import MeetParticipant
            p = MeetParticipant.query.filter_by(
                meeting_id=int(meeting_id), user_id=int(user_id)).first()
            if p:
                p.left_at = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            logging.warning(f"[MeetSocket] left_at update failed: {e}")


@socketio.on("meet_cursor_move")
def handle_meet_cursor_move(data):
    """
    Client: { meeting_id, x, y, page?, element_id? }
    Throttle to ~10 events/sec on the client side.
    """
    lookup = _sid_to_meeting.get(request.sid)
    if not lookup:
        return
    meeting_id, user_id = lookup
    p = _meeting_rooms.get(meeting_id, {}).get(user_id)
    if not p:
        return
    cursor = {
        "x": data.get("x"), "y": data.get("y"),
        "page": data.get("page"), "element_id": data.get("element_id"),
    }
    p["cursor"] = cursor
    emit("meet_cursor_moved", {
        "meeting_id": meeting_id, "user_id": user_id,
        "name": p["name"], "avatar": p["avatar"], **cursor,
    }, room=_meet_room(meeting_id), include_self=False)


@socketio.on("meet_notes_change")
def handle_meet_notes_change(data):
    """
    Client: { meeting_id, delta:{ops:[...]}, version:int, doc_id:str|null }
    Last-write-wins. Clients use version to discard stale deltas.
    """
    lookup = _sid_to_meeting.get(request.sid)
    if not lookup:
        return
    meeting_id, user_id = lookup
    p = _meeting_rooms.get(meeting_id, {}).get(user_id)
    if not p:
        return
    emit("meet_notes_delta", {
        "meeting_id": meeting_id, "user_id": user_id, "name": p["name"],
        "delta": data.get("delta"), "version": data.get("version"),
        "doc_id": data.get("doc_id"), "ts": datetime.utcnow().isoformat(),
    }, room=_meet_room(meeting_id), include_self=False)


@socketio.on("meet_annotate")
def handle_meet_annotate(data):
    """
    Client: { meeting_id, annotation_type, payload,
              target_artifact_id?, source_timestamp? }
    Saves to DB then broadcasts to ALL (including sender) with the DB id.
    """
    lookup = _sid_to_meeting.get(request.sid)
    if not lookup:
        return
    meeting_id, user_id = lookup
    ann_type = data.get("annotation_type")
    if not ann_type:
        emit("meet_error", {"message": "annotation_type required"})
        return

    payload = data.get("payload", {})
    target  = data.get("target_artifact_id")
    ts      = data.get("source_timestamp")
    ann_id  = None

    try:
        from app.models.meet_annotation import MeetAnnotation, AnnotationType
        ann = MeetAnnotation(
            meeting_id         = int(meeting_id),
            target_artifact_id = target,
            annotation_type    = AnnotationType(ann_type),
            payload_json       = payload,
            source_timestamp   = ts,
            created_by_user_id = int(user_id),
        )
        db.session.add(ann)
        db.session.commit()
        ann_id = ann.id
    except Exception as e:
        logging.error(f"[MeetSocket] annotation save error: {e}")
        db.session.rollback()

    p = _meeting_rooms.get(meeting_id, {}).get(user_id, {})
    socketio.emit("meet_annotation_added", {
        "meeting_id": meeting_id, "annotation_id": ann_id,
        "annotation_type": ann_type, "payload": payload,
        "target_artifact_id": target, "source_timestamp": ts,
        "user_id": user_id, "name": p.get("name"),
        "ts": datetime.utcnow().isoformat(),
    }, room=_meet_room(meeting_id))


@socketio.on("meet_annotation_delete")
def handle_meet_annotation_delete(data):
    """Client: { meeting_id, annotation_id }"""
    lookup = _sid_to_meeting.get(request.sid)
    if not lookup:
        return
    meeting_id, user_id = lookup
    ann_id = data.get("annotation_id")
    if not ann_id:
        return
    try:
        from app.models.meet_annotation import MeetAnnotation
        from app.models.meet_meeting import MeetMeeting
        ann     = MeetAnnotation.query.filter_by(id=ann_id, meeting_id=int(meeting_id)).first()
        meeting = MeetMeeting.query.get(int(meeting_id))
        if not ann:
            return
        if str(ann.created_by_user_id) != user_id and str(meeting.owner_user_id) != user_id:
            emit("meet_error", {"message": "Cannot delete another user's annotation"})
            return
        db.session.delete(ann)
        db.session.commit()
        socketio.emit("meet_annotation_deleted", {
            "meeting_id": meeting_id, "annotation_id": ann_id,
            "deleted_by": user_id,
        }, room=_meet_room(meeting_id))
    except Exception as e:
        logging.error(f"[MeetSocket] annotation delete error: {e}")
        db.session.rollback()


@socketio.on("meet_heartbeat")
def handle_meet_heartbeat(data):
    """Client: { meeting_id } — send every 30s to stay in the room."""
    lookup = _sid_to_meeting.get(request.sid)
    if not lookup:
        return
    meeting_id, _ = lookup
    emit("meet_heartbeat_ack", {
        "meeting_id": meeting_id,
        "ts": datetime.utcnow().isoformat(),
    })


# ── Meet helper — callable from Flask HTTP routes ──────────────────────────────

def emit_meeting_event(meeting_id, event, data):
    """Push any event to all live participants from a Flask route."""
    socketio.emit(event, data, room=_meet_room(str(meeting_id)))


def get_live_participants(meeting_id):
    """Return currently connected participants for a meeting."""
    return _meet_participants(str(meeting_id))


# ─── General helper functions (called from Flask routes) ──────────────────────

def emit_to_user(user_id, event, data):
    socketio.emit(event, data, room=f"user_{user_id}")

def emit_new_message(conversation_id, message_data):
    socketio.emit("new_message", {
        "message": message_data, "conversation_id": conversation_id,
    }, room=f"conversation_{conversation_id}")

def emit_message_edited(conversation_id, message_data):
    socketio.emit("message_edited", {
        "message": message_data, "conversation_id": conversation_id,
    }, room=f"conversation_{conversation_id}")

def emit_message_deleted(conversation_id, message_id):
    socketio.emit("message_deleted", {
        "message_id": message_id, "conversation_id": conversation_id,
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