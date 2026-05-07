"""
app/utils/meet_validators.py

Request, datetime, meeting-type, and visibility validation for SF Meet.
All validators raise ValueError on failure so callers can catch and return
a consistent 400 response.
"""

from datetime import datetime, timezone, timedelta
from typing import Any

from app.models.meet_meeting import MeetingType, VisibilityScope, OwnerScopeType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require(payload: dict, *fields: str) -> None:
    missing = [f for f in fields if f not in payload or payload[f] is None]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def _parse_dt(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    raise ValueError(f"'{field_name}' must be a valid ISO-8601 datetime string.")


# ---------------------------------------------------------------------------
# Datetime validation
# ---------------------------------------------------------------------------

MIN_MEETING_MINUTES = 5
MAX_MEETING_HOURS   = 8


def validate_meeting_times(payload: dict) -> tuple[datetime, datetime]:
    """
    Parse and validate scheduled_start_at / scheduled_end_at.
    Returns (start_dt, end_dt) as timezone-aware datetimes.
    """
    _require(payload, "scheduled_start_at", "scheduled_end_at")

    start = _parse_dt(payload["scheduled_start_at"], "scheduled_start_at")
    end   = _parse_dt(payload["scheduled_end_at"],   "scheduled_end_at")

    now = datetime.now(tz=timezone.utc)

    if start < now - timedelta(minutes=5):
        raise ValueError("scheduled_start_at cannot be in the past.")

    if end <= start:
        raise ValueError("scheduled_end_at must be after scheduled_start_at.")

    duration = end - start
    if duration < timedelta(minutes=MIN_MEETING_MINUTES):
        raise ValueError(f"Meeting duration must be at least {MIN_MEETING_MINUTES} minutes.")

    if duration > timedelta(hours=MAX_MEETING_HOURS):
        raise ValueError(f"Meeting duration cannot exceed {MAX_MEETING_HOURS} hours.")

    return start, end


# ---------------------------------------------------------------------------
# Meeting-type validation
# ---------------------------------------------------------------------------

VALID_MEETING_TYPES = {t.value for t in MeetingType}


def validate_meeting_type(value: Any) -> MeetingType:
    if value not in VALID_MEETING_TYPES:
        raise ValueError(
            f"Invalid meeting_type '{value}'. "
            f"Must be one of: {', '.join(sorted(VALID_MEETING_TYPES))}."
        )
    return MeetingType(value)


# ---------------------------------------------------------------------------
# Visibility validation
# ---------------------------------------------------------------------------

VALID_VISIBILITY_SCOPES = {v.value for v in VisibilityScope}


def validate_visibility_scope(value: Any) -> VisibilityScope:
    if value not in VALID_VISIBILITY_SCOPES:
        raise ValueError(
            f"Invalid visibility_scope '{value}'. "
            f"Must be one of: {', '.join(sorted(VALID_VISIBILITY_SCOPES))}."
        )
    return VisibilityScope(value)


# ---------------------------------------------------------------------------
# Owner scope validation
# ---------------------------------------------------------------------------

VALID_OWNER_SCOPE_TYPES = {s.value for s in OwnerScopeType}


def validate_owner_scope(payload: dict) -> tuple[OwnerScopeType, str]:
    _require(payload, "owner_scope_type", "owner_scope_id")

    scope_type = payload["owner_scope_type"]
    if scope_type not in VALID_OWNER_SCOPE_TYPES:
        raise ValueError(
            f"Invalid owner_scope_type '{scope_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_OWNER_SCOPE_TYPES))}."
        )

    scope_id = str(payload["owner_scope_id"]).strip()
    if not scope_id:
        raise ValueError("owner_scope_id cannot be empty.")

    return OwnerScopeType(scope_type), scope_id


# ---------------------------------------------------------------------------
# Linked entity lists validation
# ---------------------------------------------------------------------------

def validate_id_list(value: Any, field_name: str) -> list:
    """Ensure a field, if present, is a list of non-empty strings."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"'{field_name}' must be a list.")
    cleaned = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"'{field_name}[{i}]' must be a non-empty string ID.")
        cleaned.append(item.strip())
    return cleaned


# ---------------------------------------------------------------------------
# Full create-request validation
# ---------------------------------------------------------------------------

def validate_create_meeting_request(payload: dict) -> dict:
    """
    Validate the full create-meeting payload.
    Returns a cleaned dict ready for MeetService.create_meeting().
    Raises ValueError with a human-readable message on any failure.
    """
    _require(payload, "title", "meeting_type", "owner_user_id",
             "owner_scope_type", "owner_scope_id",
             "scheduled_start_at", "scheduled_end_at")

    title = str(payload["title"]).strip()
    if not title:
        raise ValueError("title cannot be blank.")
    if len(title) > 255:
        raise ValueError("title cannot exceed 255 characters.")

    meeting_type                 = validate_meeting_type(payload["meeting_type"])
    owner_scope_type, owner_scope_id = validate_owner_scope(payload)
    start, end                   = validate_meeting_times(payload)

    visibility_raw = payload.get("visibility_scope", VisibilityScope.INVITED_ONLY.value)
    visibility     = validate_visibility_scope(visibility_raw)

    linked_milestone_ids  = validate_id_list(payload.get("linked_milestone_ids"),  "linked_milestone_ids")
    linked_task_ids       = validate_id_list(payload.get("linked_task_ids"),        "linked_task_ids")
    linked_crm_entity_ids = validate_id_list(payload.get("linked_crm_entity_ids"), "linked_crm_entity_ids")

    return {
        "title":                  title,
        "meeting_type":           meeting_type,
        "owner_user_id":          str(payload["owner_user_id"]),
        "owner_scope_type":       owner_scope_type,
        "owner_scope_id":         owner_scope_id,
        "workspace_id":           payload.get("workspace_id"),
        "startup_id":             payload.get("startup_id"),
        "organization_id":        payload.get("organization_id"),
        "vision_id":              payload.get("vision_id"),
        "scheduled_start_at":     start,
        "scheduled_end_at":       end,
        "timezone":               str(payload.get("timezone", "UTC")),
        "visibility_scope":       visibility,
        "recording_enabled":      bool(payload.get("recording_enabled", False)),
        "transcription_enabled":  bool(payload.get("transcription_enabled", False)),
        "live_notes_enabled":     bool(payload.get("live_notes_enabled", True)),
        "annotation_enabled":     bool(payload.get("annotation_enabled", False)),
        "waiting_room_enabled":   bool(payload.get("waiting_room_enabled", False)),
        "linked_milestone_ids":   linked_milestone_ids,
        "linked_task_ids":        linked_task_ids,
        "linked_crm_entity_ids":  linked_crm_entity_ids,
        "agenda_doc_id":          payload.get("agenda_doc_id"),
        "external_guest_policy":  payload.get("external_guest_policy"),
        "metadata_json":          payload.get("metadata_json", {}),
    }


# ---------------------------------------------------------------------------
# Full update-request validation
# ---------------------------------------------------------------------------

UPDATABLE_FIELDS = {
    "title", "meeting_type", "visibility_scope",
    "scheduled_start_at", "scheduled_end_at", "timezone",
    "recording_enabled", "transcription_enabled",
    "live_notes_enabled", "annotation_enabled", "waiting_room_enabled",
    "linked_milestone_ids", "linked_task_ids", "linked_crm_entity_ids",
    "agenda_doc_id", "live_notes_doc_id", "external_guest_policy", "metadata_json",
}


def validate_update_meeting_request(payload: dict) -> dict:
    """
    Validate a partial update payload.
    Only keys present in UPDATABLE_FIELDS are accepted and validated.
    """
    unknown = set(payload.keys()) - UPDATABLE_FIELDS
    if unknown:
        raise ValueError(f"Unknown or non-updatable fields: {', '.join(sorted(unknown))}.")

    cleaned: dict = {}

    if "title" in payload:
        title = str(payload["title"]).strip()
        if not title:
            raise ValueError("title cannot be blank.")
        if len(title) > 255:
            raise ValueError("title cannot exceed 255 characters.")
        cleaned["title"] = title

    if "meeting_type" in payload:
        cleaned["meeting_type"] = validate_meeting_type(payload["meeting_type"])

    if "visibility_scope" in payload:
        cleaned["visibility_scope"] = validate_visibility_scope(payload["visibility_scope"])

    has_start = "scheduled_start_at" in payload
    has_end   = "scheduled_end_at"   in payload
    if has_start or has_end:
        if not (has_start and has_end):
            raise ValueError("Provide both scheduled_start_at and scheduled_end_at when updating times.")
        start, end = validate_meeting_times(payload)
        cleaned["scheduled_start_at"] = start
        cleaned["scheduled_end_at"]   = end

    for bool_field in ("recording_enabled", "transcription_enabled",
                       "live_notes_enabled", "annotation_enabled", "waiting_room_enabled"):
        if bool_field in payload:
            cleaned[bool_field] = bool(payload[bool_field])

    for list_field in ("linked_milestone_ids", "linked_task_ids", "linked_crm_entity_ids"):
        if list_field in payload:
            cleaned[list_field] = validate_id_list(payload[list_field], list_field)

    for passthrough in ("timezone", "agenda_doc_id", "live_notes_doc_id",
                        "external_guest_policy", "metadata_json"):
        if passthrough in payload:
            cleaned[passthrough] = payload[passthrough]

    if not cleaned:
        raise ValueError("No valid fields provided for update.")

    return cleaned
