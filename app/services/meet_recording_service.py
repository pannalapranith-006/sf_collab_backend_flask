"""
meet_recording_service.py — Daily.co video + OpenAI Whisper transcription

Environment variables required:
    DAILY_API_KEY       — from dashboard.daily.co → Developers → API keys
    OPENAI_API_KEY      — already in your config
    AWS_S3_BUCKET       — already in your config (for storing transcripts)
    AWS_ACCESS_KEY_ID   — already in your config
    AWS_SECRET_ACCESS_KEY — already in your config
    AWS_REGION          — already in your config

Flow:
    1. start_meeting()  → creates Daily.co room, returns join URL
    2. end_meeting()    → triggers Daily.co recording download
    3. process_recording() → downloads recording, transcribes with Whisper,
                             uploads transcript to S3, updates meeting record,
                             triggers post-meeting pipeline
"""

import os
import io
import json
import logging
import tempfile
import requests
from datetime import datetime
from app.extensions import db

DAILY_API_KEY  = os.getenv("DAILY_API_KEY", "")
DAILY_BASE_URL = "https://api.daily.co/v1"
DAILY_HEADERS  = {
    "Authorization": f"Bearer {DAILY_API_KEY}",
    "Content-Type":  "application/json",
}


# ══════════════════════════════════════════════════════════════════════════════
# DAILY.CO — ROOM MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def create_daily_room(meeting_id, recording_enabled=True):
    """
    Create a Daily.co room for a meeting.

    Returns:
        {
            "room_name":  str,   # Daily.co room name
            "room_url":   str,   # URL participants open to join
            "daily_room_id": str
        }
    or raises an exception on failure.
    """
    if not DAILY_API_KEY:
        raise ValueError("DAILY_API_KEY is not set in environment variables")

    room_name = f"sfmeet-{meeting_id}-{int(datetime.utcnow().timestamp())}"

    payload = {
        "name":       room_name,
        "privacy":    "private",   # participants need a token to join
        "properties": {
            "enable_recording":     "cloud" if recording_enabled else "off",
            "enable_transcription": False,   # we use Whisper instead
            "max_participants":     50,
            "enable_chat":          True,
            "enable_screenshare":   True,
            "exp":                  int(datetime.utcnow().timestamp()) + 86400,  # 24h expiry
        }
    }

    resp = requests.post(
        f"{DAILY_BASE_URL}/rooms",
        headers=DAILY_HEADERS,
        json=payload,
        timeout=15,
    )

    if not resp.ok:
        raise RuntimeError(f"Daily.co room creation failed: {resp.status_code} {resp.text}")

    data = resp.json()
    return {
        "room_name":     data["name"],
        "room_url":      data["url"],
        "daily_room_id": data.get("id", data["name"]),
    }


def create_participant_token(room_name, user_id, user_name, is_owner=False):
    """
    Create a Daily.co meeting token for a specific participant.
    Tokens are required for private rooms.

    Returns: { "token": str }
    """
    if not DAILY_API_KEY:
        raise ValueError("DAILY_API_KEY is not set")

    payload = {
        "properties": {
            "room_name":   room_name,
            "user_id":     str(user_id),
            "user_name":   user_name,
            "is_owner":    is_owner,
            "enable_recording": is_owner,   # only host can start/stop recording
            "exp": int(datetime.utcnow().timestamp()) + 86400,
        }
    }

    resp = requests.post(
        f"{DAILY_BASE_URL}/meeting-tokens",
        headers=DAILY_HEADERS,
        json=payload,
        timeout=15,
    )

    if not resp.ok:
        raise RuntimeError(f"Daily.co token creation failed: {resp.status_code} {resp.text}")

    return {"token": resp.json()["token"]}


def delete_daily_room(room_name):
    """Delete a Daily.co room (call after meeting is fully processed)."""
    if not DAILY_API_KEY or not room_name:
        return
    try:
        requests.delete(
            f"{DAILY_BASE_URL}/rooms/{room_name}",
            headers=DAILY_HEADERS,
            timeout=10,
        )
    except Exception as e:
        logging.warning(f"[Recording] Could not delete Daily.co room {room_name}: {e}")


def get_daily_recordings(room_name):
    """
    Fetch all recordings for a Daily.co room.
    Returns list of recording objects from Daily.co API.
    """
    if not DAILY_API_KEY:
        raise ValueError("DAILY_API_KEY is not set")

    resp = requests.get(
        f"{DAILY_BASE_URL}/recordings",
        headers=DAILY_HEADERS,
        params={"room_name": room_name},
        timeout=15,
    )

    if not resp.ok:
        raise RuntimeError(f"Daily.co recordings fetch failed: {resp.status_code} {resp.text}")

    data = resp.json()
    return data.get("data", [])


def get_recording_download_link(recording_id):
    """
    Get a temporary download URL for a Daily.co recording.
    The link expires after ~1 hour.
    """
    if not DAILY_API_KEY:
        raise ValueError("DAILY_API_KEY is not set")

    resp = requests.get(
        f"{DAILY_BASE_URL}/recordings/{recording_id}/access-link",
        headers=DAILY_HEADERS,
        timeout=15,
    )

    if not resp.ok:
        raise RuntimeError(f"Daily.co download link failed: {resp.status_code} {resp.text}")

    return resp.json().get("download_link")


# ══════════════════════════════════════════════════════════════════════════════
# OPENAI WHISPER — TRANSCRIPTION
# ══════════════════════════════════════════════════════════════════════════════

def transcribe_audio(audio_file_path=None, audio_url=None, language="en"):
    """
    Transcribe audio using OpenAI Whisper API.

    Pass either:
        audio_file_path — local file path (mp3, mp4, wav, m4a, webm)
        audio_url       — URL to download audio from first

    Returns:
        {
            "text":     str,   # full transcript
            "segments": list,  # timestamped segments (if available)
            "language": str,
            "duration": float,
        }
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY is not set")

    # If URL provided, download to temp file first
    tmp_file = None
    if audio_url and not audio_file_path:
        logging.info(f"[Whisper] Downloading audio from URL...")
        audio_resp = requests.get(audio_url, timeout=120, stream=True)
        if not audio_resp.ok:
            raise RuntimeError(f"Failed to download audio: {audio_resp.status_code}")

        suffix = ".mp4"
        content_type = audio_resp.headers.get("Content-Type", "")
        if "webm" in content_type:
            suffix = ".webm"
        elif "wav" in content_type:
            suffix = ".wav"
        elif "mp3" in content_type or "mpeg" in content_type:
            suffix = ".mp3"

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        for chunk in audio_resp.iter_content(chunk_size=8192):
            tmp_file.write(chunk)
        tmp_file.close()
        audio_file_path = tmp_file.name
        logging.info(f"[Whisper] Audio downloaded to {audio_file_path}")

    if not audio_file_path or not os.path.exists(audio_file_path):
        raise ValueError("No valid audio file path provided")

    file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
    logging.info(f"[Whisper] Transcribing {file_size_mb:.1f}MB audio file...")

    # Whisper API has a 25MB limit — log a warning if exceeded
    if file_size_mb > 25:
        logging.warning(f"[Whisper] File is {file_size_mb:.1f}MB, exceeds 25MB Whisper limit. Consider chunking.")

    with open(audio_file_path, "rb") as f:
        whisper_resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {openai_key}"},
            files={"file": (os.path.basename(audio_file_path), f)},
            data={
                "model":           "whisper-1",
                "language":        language,
                "response_format": "verbose_json",  # includes segments + timestamps
                "timestamp_granularities[]": "segment",
            },
            timeout=300,   # transcription can take time for long recordings
        )

    # Clean up temp file
    if tmp_file:
        try:
            os.unlink(audio_file_path)
        except Exception:
            pass

    if not whisper_resp.ok:
        raise RuntimeError(f"Whisper transcription failed: {whisper_resp.status_code} {whisper_resp.text}")

    result = whisper_resp.json()
    return {
        "text":     result.get("text", ""),
        "segments": result.get("segments", []),
        "language": result.get("language", language),
        "duration": result.get("duration", 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# S3 STORAGE — TRANSCRIPT UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def upload_transcript_to_s3(meeting_id, transcript_data):
    """
    Upload transcript JSON to S3 and return the S3 key (used as drive_file_id).

    transcript_data: the dict returned by transcribe_audio()
    Returns: S3 key string
    """
    try:
        import boto3
        bucket = os.getenv("AWS_S3_BUCKET")
        region = os.getenv("AWS_REGION", "us-east-1")
        if not bucket:
            raise ValueError("AWS_S3_BUCKET not set")

        s3 = boto3.client(
            "s3",
            region_name            = region,
            aws_access_key_id      = os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key  = os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        key     = f"meet-transcripts/meeting_{meeting_id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_transcript.json"
        content = json.dumps(transcript_data, ensure_ascii=False, indent=2)

        s3.put_object(
            Bucket      = bucket,
            Key         = key,
            Body        = content.encode("utf-8"),
            ContentType = "application/json",
        )

        logging.info(f"[Recording] Transcript uploaded to s3://{bucket}/{key}")
        return key

    except ImportError:
        # boto3 not installed — store transcript as local JSON path placeholder
        logging.warning("[Recording] boto3 not installed. Storing transcript text only.")
        return f"local:meeting_{meeting_id}_transcript"
    except Exception as e:
        logging.error(f"[Recording] S3 upload failed: {e}")
        raise


# ══════════════════════════════════════════════════════════════════════════════
# HIGH-LEVEL ORCHESTRATION
# ══════════════════════════════════════════════════════════════════════════════

def setup_meeting_room(meeting):
    """
    Call when a meeting is about to start.
    Creates the Daily.co room and stores room info in meeting.metadata_json.

    Returns: { room_url, room_name, daily_room_id }
    """
    room_info = create_daily_room(
        meeting_id        = meeting.id,
        recording_enabled = meeting.recording_enabled,
    )

    # Store Daily room info in meeting metadata for later use
    meta = meeting.metadata_json or {}
    meta["daily_room_name"]  = room_info["room_name"]
    meta["daily_room_id"]    = room_info["daily_room_id"]
    meta["daily_room_url"]   = room_info["room_url"]
    meta["room_created_at"]  = datetime.utcnow().isoformat()
    meeting.metadata_json = meta
    db.session.commit()

    logging.info(f"[Recording] Daily.co room created for meeting {meeting.id}: {room_info['room_name']}")
    return room_info


def get_participant_join_token(meeting, user_id, user_name, is_owner=False):
    """
    Generate a Daily.co join token for a participant.
    Call this when a user is about to join the live meeting.

    Returns: { token, room_url }
    """
    meta      = meeting.metadata_json or {}
    room_name = meta.get("daily_room_name")

    if not room_name:
        raise RuntimeError(f"No Daily.co room found for meeting {meeting.id}. Call setup_meeting_room first.")

    token_data = create_participant_token(
        room_name  = room_name,
        user_id    = user_id,
        user_name  = user_name,
        is_owner   = is_owner,
    )

    return {
        "token":    token_data["token"],
        "room_url": meta.get("daily_room_url"),
        "room_name": room_name,
    }


def process_meeting_recording(meeting):
    """
    Full post-meeting recording pipeline:
      1. Fetch recordings from Daily.co
      2. Get download link for latest recording
      3. Transcribe with Whisper
      4. Upload transcript to S3
      5. Store recording_file_id + transcript_file_id on meeting
      6. Save artifacts to meet_artifact table
      7. Trigger post-meeting processing pipeline

    Call this after meeting.status = processing.
    This can take several minutes — run in a background thread or task queue.

    Returns: { recording_file_id, transcript_file_id, transcript_text }
    """
    from app.models.meet_meeting import MeetingStatus
    from app.models.meet_artifact import MeetArtifact, ArtifactType

    meta      = meeting.metadata_json or {}
    room_name = meta.get("daily_room_name")

    if not room_name:
        logging.warning(f"[Recording] No Daily room found for meeting {meeting.id} — skipping recording fetch")
        return {}

    result = {}

    # ── Step 1: Fetch recordings ───────────────────────────────────────────────
    logging.info(f"[Recording] Fetching recordings for room {room_name}...")
    recordings = get_daily_recordings(room_name)

    if not recordings:
        logging.warning(f"[Recording] No recordings found for room {room_name}")
        return {}

    # Use the most recent recording
    latest = sorted(recordings, key=lambda r: r.get("start_ts", 0), reverse=True)[0]
    recording_id  = latest["id"]
    recording_url = latest.get("download_url")

    # ── Step 2: Get download link if needed ────────────────────────────────────
    if not recording_url:
        logging.info(f"[Recording] Getting download link for recording {recording_id}...")
        recording_url = get_recording_download_link(recording_id)

    # Store Daily recording ID as the recording_file_id
    recording_file_id = f"daily:{recording_id}"
    meeting.recording_file_id = recording_file_id
    result["recording_file_id"] = recording_file_id
    result["recording_url"]     = recording_url

    # Save recording artifact
    recording_artifact = MeetArtifact(
        meeting_id         = meeting.id,
        artifact_type      = ArtifactType.recording,
        drive_file_id      = recording_file_id,
        startup_id         = meeting.startup_id,
        ai_generated       = False,
        created_by_user_id = meeting.owner_user_id,
    )
    db.session.add(recording_artifact)

    # ── Step 3: Transcribe with Whisper ────────────────────────────────────────
    if meeting.transcription_enabled:
        logging.info(f"[Recording] Transcribing recording {recording_id} with Whisper...")
        try:
            transcript_data = transcribe_audio(audio_url=recording_url)
            transcript_text = transcript_data["text"]
            result["transcript_text"] = transcript_text

            # ── Step 4: Upload transcript to S3 ───────────────────────────────
            transcript_file_id = upload_transcript_to_s3(meeting.id, transcript_data)
            meeting.transcript_file_id = transcript_file_id
            result["transcript_file_id"] = transcript_file_id

            # Save transcript artifact
            transcript_artifact = MeetArtifact(
                meeting_id         = meeting.id,
                artifact_type      = ArtifactType.transcript,
                drive_file_id      = transcript_file_id,
                startup_id         = meeting.startup_id,
                ai_generated       = False,
                created_by_user_id = meeting.owner_user_id,
            )
            db.session.add(transcript_artifact)

            logging.info(f"[Recording] Transcription complete. {len(transcript_text)} chars.")

        except Exception as e:
            logging.error(f"[Recording] Transcription failed for meeting {meeting.id}: {e}")
            result["transcript_error"] = str(e)

    # ── Step 5: Update meeting status ──────────────────────────────────────────
    # Auto-advance to indexed if both recording and transcript are saved
    if meeting.recording_file_id and meeting.transcript_file_id:
        meeting.status = MeetingStatus.indexed
    
    db.session.commit()

    # ── Step 6: Emit socket event to notify participants ───────────────────────
    try:
        from app.socket_events import emit_meeting_event
        emit_meeting_event(meeting.id, "meet_recording_ready", {
            "meeting_id":        meeting.id,
            "recording_file_id": recording_file_id,
            "transcript_ready":  bool(meeting.transcript_file_id),
        })
    except Exception as e:
        logging.warning(f"[Recording] Could not emit socket event: {e}")

    logging.info(f"[Recording] Pipeline complete for meeting {meeting.id}")
    return result


def process_recording_async(app, meeting_id):
    """
    Run process_meeting_recording in a background thread.
    Call this from your end_meeting route so it doesn't block the response.

    Usage in meet_routes.py end_meeting():
        from app.services.meet_recording_service import process_recording_async
        process_recording_async(current_app._get_current_object(), meeting.id)
    """
    import threading
    from app.models.meet_meeting import MeetMeeting

    def _run():
        with app.app_context():
            try:
                meeting = MeetMeeting.query.get(meeting_id)
                if meeting:
                    process_meeting_recording(meeting)
            except Exception as e:
                logging.error(f"[Recording] Async pipeline error for meeting {meeting_id}: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    logging.info(f"[Recording] Background processing started for meeting {meeting_id}")