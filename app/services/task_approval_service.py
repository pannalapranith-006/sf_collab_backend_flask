"""
Task Approval Service
---------------------
Handles approve / reject logic for tasks.

Rules (from ERP spec):
  - Only admins can approve or reject.
  - A task must be in DONE status to be approved/rejected.
  - Task workspace_id must match admin's workspace_id (isolation).
  - Approval triggers execution point calculation.
  - Rejection sets points to 0 and records reason.
  - Every action is audit-logged.
"""
import logging
from datetime import datetime, timezone
from dataclasses import dataclass

from app.models.task import TaskStatus, QualityRating
from app.services.execution_points_service import compute_task_points, PointsInput

logger = logging.getLogger(__name__)

# FIX: cap rejection reason to prevent oversized DB writes.
MAX_REJECTION_REASON_LENGTH = 1000
ENTITY_TYPE_TASK = "task"


def _now():
    return datetime.now(timezone.utc)


def _require_admin(membership):
    if membership.get("role") != "admin":
        raise PermissionError("Only admins can approve or reject tasks.")


def _task_get(task, field, default=None):
    if isinstance(task, dict):
        return task.get(field, default)
    return getattr(task, field, default)


def _require_task_field(task, field):
    """Raise ValueError (not KeyError) when a required task key is absent."""
    if _task_get(task, field) is None:
        raise ValueError(f"Task record is missing required field '{field}'.")


def _require_membership_fields(membership):
    """Raise PermissionError when membership is missing critical keys."""
    if not membership.get("user_id"):
        raise PermissionError("Membership record is missing 'user_id'.")
    if not membership.get("workspace_id"):
        raise PermissionError("Membership record is missing 'workspace_id'.")


def _require_status(task, expected, force=False):
    try:
        current = TaskStatus(task["status"])
    except ValueError:
        raise ValueError(f"Task has unrecognised status: '{task['status']}'")

    if current == expected:
        return

    if not force:
        if current == TaskStatus.APPROVED:
            raise ValueError("Task is already approved.")
        if current == TaskStatus.REJECTED:
            raise ValueError("Task is already rejected.")

    raise ValueError(
        f"Task must be in '{expected}' status to be actioned. "
        f"Current status: '{current}'"
    )


def _require_workspace_match(task, membership):
    """Enforce workspace isolation at the service layer."""
    if _task_get(task, "workspace_id") != membership.get("workspace_id"):
        raise PermissionError(
            "Task does not belong to the admin's workspace."
        )


def _require_task_id(task):
    """
    Guard against missing 'id' key, which would otherwise surface as an
    unhandled KeyError inside _build_audit and leak into the 500 handler.
    """
    if not _task_get(task, "id"):
        raise ValueError("Task record is missing a required 'id' field.")


@dataclass
class AuditPayload:
    """Groups audit fields to keep _build_audit under the argument limit."""
    workspace_id: str
    actor_user_id: str
    action: str
    entity_type: str
    entity_id: str
    before: dict
    after: dict
    reason: str


def _build_audit(payload: AuditPayload) -> dict:
    return {
        "workspace_id": payload.workspace_id,
        "actor_user_id": payload.actor_user_id,
        "action": payload.action,
        "entity_type": payload.entity_type,
        "entity_id": payload.entity_id,
        "before_value": payload.before,
        "after_value": payload.after,
        "reason": payload.reason,
        "created_at": _now().isoformat(),
    }


def approve_task(task, admin_membership, quality_rating, force=False):
    """
    Approve a completed task and generate execution points.

    Parameters
    ----------
    task             : dict-like task record (must include 'id', 'status',
                       'complexity', 'workspace_id')
    admin_membership : dict with 'role', 'user_id', 'workspace_id'
    quality_rating   : 'accepted' | 'good' | 'excellent'

    Returns
    -------
    {
        "task_updates"  : { status, quality_rating, approved_points, ... },
        "point_breakdown": { base_points, quality_multiplier, ... final_points },
        "audit_entry"   : { ... }
    }

    NOTE: concurrent approvals for the same task must be prevented at the
    DB layer. DB-layer optimistic locking (e.g. version column or SELECT FOR UPDATE) is still required to prevent concurrent re-reviews. This service layer check is not atomic.
    """
    _require_task_id(task)
    _require_task_field(task, "complexity")
    _require_admin(admin_membership)
    _require_membership_fields(admin_membership)
    _require_workspace_match(task, admin_membership)
    _require_status(task, TaskStatus.DONE, force=force)

    if quality_rating == QualityRating.REJECTED:
        raise ValueError(
            "Use reject_task() to reject a task. "
            "approve_task() requires a non-rejected quality rating."
        )

    point_breakdown = compute_task_points(PointsInput(
        complexity=task["complexity"],
        quality_rating=quality_rating,
        requires_proof=_task_get(task, "requires_proof", False),
        proof_status=_task_get(task, "proof_status"),
        task_deadline=_task_get(task, "deadline"),
        completed_at=_task_get(task, "completed_at"),
    ))

    now = _now()
    updates = {
        "status": TaskStatus.APPROVED,
        "quality_rating": quality_rating,
        "approved_points": point_breakdown["final_points"],
        "reviewed_by_user_id": admin_membership["user_id"],  # renamed from approved_by_user_id
        # FIX: renamed from 'approved_at' to 'reviewed_at' so the field is
        # semantically correct on both approval and rejection paths.
        "reviewed_at": now.isoformat(),
        "rejection_reason": None,
    }

    audit = _build_audit(AuditPayload(
        workspace_id=admin_membership["workspace_id"],
        actor_user_id=admin_membership["user_id"],
        action="task_approved",
        entity_type=ENTITY_TYPE_TASK,
        entity_id=task["id"],
        # FIX: capture the task's actual prior approved_points, not a
        # hardcoded None, so the audit trail is accurate for re-reviews.
        before={"status": task["status"], "approved_points": _task_get(task, "approved_points")},
        after=updates,
        reason=f"Quality: {quality_rating}",
    ))

    return {
        "task_updates": updates,
        "point_breakdown": point_breakdown,
        "audit_entry": audit,
    }


def reject_task(task, admin_membership, rejection_reason, force=False):
    """
    Reject a completed task. Points are zeroed out.

    Parameters
    ----------
    task              : dict-like task record (must include 'id', 'status',
                        'workspace_id')
    admin_membership  : dict with 'role', 'user_id', 'workspace_id'
    rejection_reason  : non-empty string explaining the rejection
                        (max {MAX_REJECTION_REASON_LENGTH} characters)

    Returns
    -------
    {
        "task_updates"   : { status, quality_rating, approved_points=0,
                             rejection_reason, reviewed_at, ... },
        "point_breakdown": None,   # symmetric with approve_task
        "audit_entry"    : { ... }
    }

    NOTE: concurrent rejections for the same task must be prevented at the
    DB layer. DB-layer optimistic locking (e.g. version column or SELECT FOR UPDATE) is still required to prevent concurrent re-reviews. This service layer check is not atomic.
    """
    _require_task_id(task)
    _require_admin(admin_membership)
    _require_membership_fields(admin_membership)
    _require_workspace_match(task, admin_membership)
    _require_status(task, TaskStatus.DONE, force=force)

    if not rejection_reason or not rejection_reason.strip():
        raise ValueError("A rejection reason is required.")

    rejection_reason = rejection_reason.strip()

    # FIX: cap length to prevent oversized DB writes.
    if len(rejection_reason) > MAX_REJECTION_REASON_LENGTH:
        raise ValueError(
            f"rejection_reason must be {MAX_REJECTION_REASON_LENGTH} characters or fewer "
            f"(got {len(rejection_reason)})."
        )

    now = _now()
    updates = {
        "status": TaskStatus.REJECTED,
        "quality_rating": QualityRating.REJECTED,
        "approved_points": 0,
        "reviewed_by_user_id": admin_membership["user_id"],  # renamed
        # FIX: use 'reviewed_at' consistently (was 'approved_at' — wrong for a rejection).
        "reviewed_at": now.isoformat(),
        "rejection_reason": rejection_reason,
    }

    audit = _build_audit(AuditPayload(
        workspace_id=admin_membership["workspace_id"],
        actor_user_id=admin_membership["user_id"],
        action="task_rejected",
        entity_type=ENTITY_TYPE_TASK,
        entity_id=task["id"],
        # FIX: capture actual prior approved_points, not hardcoded None.
        before={"status": task["status"], "approved_points": _task_get(task, "approved_points")},
        after=updates,
        reason=rejection_reason,
    ))

    return {
        "task_updates": updates,
        # FIX: return point_breakdown key for symmetry with approve_task.
        # Callers can check `if result["point_breakdown"] is None` to
        # distinguish the rejection path without inspecting status.
        "point_breakdown": None,
        "audit_entry": audit,
    }
