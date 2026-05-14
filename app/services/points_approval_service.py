from datetime import datetime
from app import db
from app.models.execution_point import ExecutionPoint
from app.services.membership_audit_service import log_membership_action

def approve_points(point_id, approver_id, comment=None):
    point = ExecutionPoint.query.get(point_id)
    if not point:
        raise ValueError('Execution point record not found')
    if point.status not in ['pending', 'held']:
        raise ValueError(f'Cannot approve points with status {point.status}')

    point.status = 'approved'
    point.approved_by = approver_id
    point.approved_at = datetime.utcnow()
    point.approval_comment = comment
    db.session.commit()

    log_membership_action(
        'points_approved',
        workspace_id=point.workspace_id,
        details={
            'point_id': point.id,
            'user_id': point.user_id,
            'final_points': point.final_points,
            'comment': comment
        }
    )
    return point

def reject_points(point_id, approver_id, comment=None):
    point = ExecutionPoint.query.get(point_id)
    if not point:
        raise ValueError('Execution point record not found')
    if point.status in ['approved', 'rejected']:
        raise ValueError(f'Cannot reject points with status {point.status}')

    point.status = 'rejected'
    point.approved_by = approver_id
    point.approved_at = datetime.utcnow()
    point.approval_comment = comment
    db.session.commit()

    log_membership_action(
        'points_rejected',
        workspace_id=point.workspace_id,
        details={
            'point_id': point.id,
            'user_id': point.user_id,
            'comment': comment
        }
    )
    return point

def hold_points(point_id, approver_id, comment=None):
    point = ExecutionPoint.query.get(point_id)
    if not point:
        raise ValueError('Execution point record not found')
    if point.status in ['approved', 'rejected']:
        raise ValueError(f'Cannot hold points already {point.status}')

    point.status = 'held'
    point.approved_by = approver_id
    point.approved_at = datetime.utcnow()
    point.approval_comment = comment
    db.session.commit()

    log_membership_action(
        'points_held',
        workspace_id=point.workspace_id,
        details={
            'point_id': point.id,
            'user_id': point.user_id,
            'comment': comment
        }
    )
    return point