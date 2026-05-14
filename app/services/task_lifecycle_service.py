from datetime import datetime
from app import db
from app.models.erp_task import ErpTask
from app.services.membership_audit_service import log_membership_action

ALLOWED_TRANSITIONS = {
    'to_do': ['in_progress'],
    'in_progress': ['to_do', 'done'],
    'done': ['approved', 'rejected'],
    'approved': [],
    'rejected': [],
}

VALID_STATUSES = list(ALLOWED_TRANSITIONS.keys())

def change_status(task_id, new_status, user_id):
    task = ErpTask.query.get(task_id)
    if not task:
        raise ValueError('Task not found.')

    if new_status not in VALID_STATUSES:
        raise ValueError(f'Invalid status. Must be one of: {", ".join(VALID_STATUSES)}.')

    if new_status not in ALLOWED_TRANSITIONS[task.status]:
        raise ValueError(
            f'Cannot change status from "{task.status}" to "{new_status}". '
            f'Allowed transitions: {ALLOWED_TRANSITIONS[task.status]}.'
        )

    old_status = task.status
    task.status = new_status

    # Mark completion timestamp for final states
    if new_status in ['done', 'approved', 'rejected'] and task.completed_at is None:
        task.completed_at = datetime.utcnow()

    db.session.commit()

    # Auto‑calculate execution points when approved
    if new_status == 'approved':
        from app.services.points_calculation_service import calculate_execution_points
        try:
            calculate_execution_points(task_id)
        except ValueError:
            # Ignore if calculation fails; admin can trigger manually later
            pass

    log_membership_action(
        'task_status_change',
        workspace_id=task.workspace_id,
        details={
            'task_id': task.id,
            'old_status': old_status,
            'new_status': new_status,
            'changed_by': user_id
        }
    )
    return task