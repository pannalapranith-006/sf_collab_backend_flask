"""
Centralised permission evaluation for Drive files & folders.
All access checks should go through these functions so that
rules (owner, explicit grant, workspace membership) stay in one place.
"""

from app.models.drive_file import DriveFile
from app.models.drive_folder import DriveFolder
from app.models.drive_permission import DriveFilePermission
from app.models.startUpMember import StartupMember


def check_file_access(file_id: int, user_id: int, required_role: str = 'viewer') -> bool:
    """
    Return True if the user has at least `required_role` on the file.
    Roles hierarchy: viewer < editor < owner
    """
    file = DriveFile.query.get(file_id)
    if not file or file.state == 'deleted':
        return False

    # Owner of the file (creator)
    if file.created_by == user_id:
        return True

    # Explicit permission on the file
    perm = DriveFilePermission.query.filter_by(file_id=file_id, user_id=user_id).first()
    if perm:
        return _role_is_sufficient(perm.role, required_role)

    # If file belongs to a workspace, check workspace membership
    if file.workspace_id:
        member = StartupMember.query.filter_by(
            startup_id=file.workspace_id, user_id=user_id, is_active=True
        ).first()
        if member:
            # Workspace members get at least viewer access; founder/creator can be considered owner
            if member.role in ('admin', 'creator', 'owner'):
                return True
            if required_role == 'viewer':
                return True

    return False


def check_folder_access(folder_id: int, user_id: int, required_role: str = 'viewer') -> bool:
    """
    Return True if the user has at least `required_role` on the folder.
    """
    folder = DriveFolder.query.get(folder_id)
    if not folder:
        return False

    # Folder creator
    if folder.created_by == user_id:
        return True

    # Explicit permission on the folder
    perm = DriveFilePermission.query.filter_by(folder_id=folder_id, user_id=user_id).first()
    if perm:
        return _role_is_sufficient(perm.role, required_role)

    # Workspace membership
    if folder.workspace_id:
        member = StartupMember.query.filter_by(
            startup_id=folder.workspace_id, user_id=user_id, is_active=True
        ).first()
        if member:
            if member.role in ('admin', 'creator', 'owner'):
                return True
            if required_role == 'viewer':
                return True

    return False


def _role_is_sufficient(current: str, required: str) -> bool:
    order = {'viewer': 0, 'editor': 1, 'owner': 2}
    return order.get(current, 0) >= order.get(required, 0)


def grant_permission(file_id: int = None, folder_id: int = None, user_id: int = None, role: str = 'viewer'):
    """Create or update a direct permission record."""
    if file_id:
        perm = DriveFilePermission.query.filter_by(file_id=file_id, user_id=user_id).first()
        if perm:
            perm.role = role
        else:
            perm = DriveFilePermission(file_id=file_id, user_id=user_id, role=role)
    elif folder_id:
        perm = DriveFilePermission.query.filter_by(folder_id=folder_id, user_id=user_id).first()
        if perm:
            perm.role = role
        else:
            perm = DriveFilePermission(folder_id=folder_id, user_id=user_id, role=role)
    else:
        raise ValueError("Either file_id or folder_id must be provided")
    return perm


def revoke_permission(file_id: int = None, folder_id: int = None, user_id: int = None):
    """Delete a direct permission record."""
    if file_id:
        DriveFilePermission.query.filter_by(file_id=file_id, user_id=user_id).delete()
    elif folder_id:
        DriveFilePermission.query.filter_by(folder_id=folder_id, user_id=user_id).delete()