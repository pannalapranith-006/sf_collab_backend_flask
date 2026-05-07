from app import db
from app.models.workspace_membership import WorkspaceMembership
from app.services.membership_audit_service import log_membership_action

def add_member(workspace_id, user_id, role='member', admin_user_id=None):
    if role not in ['admin', 'member']:
        raise ValueError('Invalid role. Must be "admin" or "member".')

    existing = WorkspaceMembership.query.filter_by(
        workspace_id=workspace_id, user_id=user_id
    ).first()
    if existing:
        raise ValueError('User is already a member of this workspace.')

    membership = WorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role
    )
    db.session.add(membership)
    db.session.commit()

    log_membership_action(
        'add_member',
        workspace_id=workspace_id,
        details={'added_user_id': user_id, 'role': role}
    )
    return membership

def remove_member(workspace_id, user_id):
    membership = WorkspaceMembership.query.filter_by(
        workspace_id=workspace_id, user_id=user_id
    ).first()
    if not membership:
        raise ValueError('Membership not found.')

    # Prevent removal of the last admin
    if membership.role == 'admin':
        admin_count = WorkspaceMembership.query.filter_by(
            workspace_id=workspace_id,
            role='admin'
        ).count()
        if admin_count <= 1:
            raise ValueError('Cannot remove the last admin.')

    db.session.delete(membership)
    db.session.commit()

    log_membership_action(
        'remove_member',
        workspace_id=workspace_id,
        details={'removed_user_id': user_id}
    )

def update_role(workspace_id, user_id, new_role):
    if new_role not in ['admin', 'member']:
        raise ValueError('Invalid role. Must be "admin" or "member".')

    membership = WorkspaceMembership.query.filter_by(
        workspace_id=workspace_id, user_id=user_id
    ).first()
    if not membership:
        raise ValueError('Membership not found.')

    # Prevent demoting the last admin
    if membership.role == 'admin' and new_role != 'admin':
        admin_count = WorkspaceMembership.query.filter_by(
            workspace_id=workspace_id,
            role='admin'
        ).count()
        if admin_count <= 1:
            raise ValueError('Workspace must have at least one admin.')

    old_role = membership.role
    membership.role = new_role
    db.session.commit()

    log_membership_action(
        'update_role',
        workspace_id=workspace_id,
        details={'user_id': user_id, 'old_role': old_role, 'new_role': new_role}
    )
    return membership

def is_admin(workspace_id, user_id):
    membership = WorkspaceMembership.query.filter_by(
        workspace_id=workspace_id, user_id=user_id
    ).first()
    return membership is not None and membership.role == 'admin'

def is_any_admin(user_id):
    """Return True if the user is admin of at least one workspace."""
    return WorkspaceMembership.query.filter_by(
        user_id=user_id, role='admin'
    ).first() is not None