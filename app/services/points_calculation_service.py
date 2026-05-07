from datetime import date, datetime
from app import db
from app.models.erp_task import ErpTask
from app.models.proof import Proof
from app.models.execution_point import ExecutionPoint
from app.services.membership_audit_service import log_membership_action

# Base points lookup
BASE_POINTS = {
    'small': 5,
    'medium': 15,
    'large': 35,
    'critical': 60,
}

def calculate_execution_points(task_id):
    """
    Compute execution points for a task's assignee.
    Only works if task is approved and assignee exists.
    Returns the ExecutionPoint record or raises ValueError.
    """
    task = ErpTask.query.get(task_id)
    if not task:
        raise ValueError('Task not found')
    if not task.assignee_id:
        raise ValueError('Task must have an assignee to earn points')
    if task.status != 'approved':
        raise ValueError('Task must be approved before points can be calculated')

    # Determine base points
    base = BASE_POINTS.get(task.complexity, 0) if task.complexity else 0
    if base == 0:
        raise ValueError('Invalid or missing task complexity')

    # Quality multiplier
    quality_map = {
        'rejected': 0.0,
        'poor': 0.5,
        'accepted': 1.0,
        'good': 1.2,
        'excellent': 1.5,
        'exceptional': 2.0,
    }
    quality_mult = quality_map.get(task.quality_rating, 1.0)   # default accepted if not set

    # Proof multiplier
    proofs = Proof.query.filter_by(task_id=task_id).all()
    requires_proof = task.requires_proof
    if requires_proof:
        # Check if there is an approved proof
        approved_proof = any(p.status == 'approved' for p in proofs)
        if not approved_proof:
            # Missing required proof – hold points
            proof_mult = 0.0   # will result in 0 final points, or we can set status 'held'
        else:
            proof_mult = 1.25
    else:
        proof_mult = 1.0

    # Deadline multiplier
    deadline_mult = 1.0
    if task.due_date and task.completed_at:
        due_date = task.due_date
        completed_date = task.completed_at.date()
        if completed_date < due_date:
            deadline_mult = 1.1   # early
        elif completed_date == due_date:
            deadline_mult = 1.0   # on time
        else:
            deadline_mult = 0.7   # late

    final_points = base * quality_mult * proof_mult * deadline_mult

    # Upsert ExecutionPoint record (unique per task+user)
    existing = ExecutionPoint.query.filter_by(task_id=task_id, user_id=task.assignee_id).first()
    if existing:
        # Update
        existing.base_points = base
        existing.quality_multiplier = quality_mult
        existing.proof_multiplier = proof_mult
        existing.deadline_multiplier = deadline_mult
        existing.final_points = final_points
        existing.status = 'pending'   # reset to pending; admin can later approve/reject
    else:
        point_rec = ExecutionPoint(
            workspace_id=task.workspace_id,
            user_id=task.assignee_id,
            task_id=task_id,
            base_points=base,
            quality_multiplier=quality_mult,
            proof_multiplier=proof_mult,
            deadline_multiplier=deadline_mult,
            final_points=final_points,
            status='pending'
        )
        db.session.add(point_rec)

    db.session.commit()

    log_membership_action(
        'points_calculated',
        workspace_id=task.workspace_id,
        details={
            'task_id': task_id,
            'user_id': task.assignee_id,
            'final_points': final_points
        }
    )
    return existing if existing else point_rec