"""
Central event emitter for all Drive-related actions.
Currently synchronously writes to the audit log.
Built to be extended with async queues later.
"""

from app.services.audit_service import log_action


def emit_event(event_type: str, file_id: int, actor_id: int, metadata: dict = None):
    """
    Single entry point for every Drive event.
    Handles mapping from event_type to audit action and extra data.
    """
    # Keep mapping of event_type to log_action's action string
    action_map = {
        "file_uploaded": "upload",
        "file_deleted": "delete",
        "file_updated": "update",
        "file_state_changed": "state_change",
        "file_marked_canonical": "mark_canonical",
        "file_linked_to_meeting": "linked_to_meeting",
        "file_unlinked_from_meeting": "unlinked_from_meeting",
        "file_linked_to_entity": "linked",   # will be customised below
    }

    action = action_map.get(event_type, event_type)  # fallback to raw type

    # custom handling for generic entity linking
    if event_type == "file_linked_to_entity":
        if metadata and "relation_type" in metadata:
            action = f"linked_to_{metadata['relation_type']}"
        # metadata already contains entity info

    log_action(file_id=file_id, action=action, performed_by=actor_id, metadata=metadata)