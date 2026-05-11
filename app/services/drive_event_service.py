from app.extensions import db
from app.models.drive_audit_log import DriveAuditLog
from datetime import datetime

def log_action(file_id: int, action: str, performed_by: int = None, metadata: dict = None):
    """Directly write an audit log entry."""
    entry = DriveAuditLog(
        file_id=file_id,
        action=action,
        performed_by=performed_by,
        event_metadata=metadata,
        created_at=datetime.utcnow()
    )
    db.session.add(entry)

def emit_event(event_type: str, file_id: int, actor_id: int, metadata: dict = None):
    action_map = {
        "file_uploaded": "upload",
        "file_deleted": "delete",
        "file_updated": "update",
        "file_state_changed": "state_change",
        "file_marked_canonical": "mark_canonical",
        "file_linked_to_meeting": "linked_to_meeting",
        "file_unlinked_from_meeting": "unlinked_from_meeting",
        "file_linked_to_entity": "linked",
    }

    action = action_map.get(event_type, event_type)

    if event_type == "file_linked_to_entity" and metadata and "relation_type" in metadata:
        action = f"linked_to_{metadata['relation_type']}"

    audit = DriveAuditLog(
        file_id=file_id,
        action=action,
        performed_by=actor_id,
        event_metadata=metadata or {}
    )

    db.session.add(audit)
    db.session.commit()
