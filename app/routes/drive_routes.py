from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.drive_file import DriveFile
from app.models.drive_folder import DriveFolder
from app.models.startup import Startup
from app.models.startUpMember import StartupMember
from app.utils.response_helpers import success_response, error_response

drive_bp = Blueprint('drive', __name__, url_prefix='/api/drive')

def _authorize_workspace(workspace_id, user_id):
    startup = Startup.query.get(workspace_id)
    if not startup:
        return None, error_response('Workspace not found', 404)
    is_member = StartupMember.query.filter_by(
        startup_id=workspace_id, user_id=user_id, is_active=True).first()
    is_creator = startup.creator_id == user_id
    if not is_member and not is_creator:
        return None, error_response('Unauthorized access to this workspace', 403)
    return startup, None

# Folders
@drive_bp.route('/folders', methods=['GET'])
@jwt_required()
def list_folders():
    workspace_id = request.args.get('workspace_id', type=int)
    if workspace_id is None:
        return error_response('workspace_id is required', 400)
    current_user_id = int(get_jwt_identity())
    _, err = _authorize_workspace(workspace_id, current_user_id)
    if err:
        return err
    folders = DriveFolder.query.filter_by(workspace_id=workspace_id).all()
    return success_response([f.to_dict() for f in folders])

@drive_bp.route('/folders', methods=['POST'])
@jwt_required()
def create_folder():
    data = request.get_json(silent=True) or {}
    workspace_id = data.get('workspace_id')
    name = data.get('name')
    if not workspace_id or not name:
        return error_response('workspace_id and name are required', 400)
    current_user_id = int(get_jwt_identity())
    _, err = _authorize_workspace(workspace_id, current_user_id)
    if err:
        return err
    folder = DriveFolder(
        name=name,
        workspace_id=workspace_id,
        created_by=current_user_id,
        parent_id=data.get('parent_folder_id')
    )
    db.session.add(folder)
    db.session.commit()
    return success_response(folder.to_dict(), 201)

@drive_bp.route('/folders/<int:folder_id>', methods=['PUT'])
@jwt_required()
def update_folder(folder_id):
    folder = DriveFolder.query.get_or_404(folder_id)
    current_user_id = int(get_jwt_identity())
    _, err = _authorize_workspace(folder.workspace_id, current_user_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        folder.name = data['name']
    if 'parent_folder_id' in data:
        folder.parent_id = data['parent_folder_id']
    db.session.commit()
    return success_response(folder.to_dict())

@drive_bp.route('/folders/<int:folder_id>', methods=['DELETE'])
@jwt_required()
def delete_folder(folder_id):
    folder = DriveFolder.query.get_or_404(folder_id)
    current_user_id = int(get_jwt_identity())
    _, err = _authorize_workspace(folder.workspace_id, current_user_id)
    if err:
        return err
    db.session.delete(folder)
    db.session.commit()
    return success_response({'message': 'Folder deleted'}, 200)

# Files (lightweight metadata CRUD)
@drive_bp.route('/files', methods=['GET'])
@jwt_required()
def list_files():
    workspace_id = request.args.get('workspace_id', type=int)
    if workspace_id is None:
        return error_response('workspace_id is required', 400)
    current_user_id = int(get_jwt_identity())
    _, err = _authorize_workspace(workspace_id, current_user_id)
    if err:
        return err
    folder_id = request.args.get('folder_id', type=int)
    query = DriveFile.query.filter_by(workspace_id=workspace_id, state='active')
    if folder_id is not None:
        query = query.filter_by(folder_id=folder_id)
    files = query.all()
    return success_response([f.to_dict() for f in files])

@drive_bp.route('/files', methods=['POST'])
@jwt_required()
def create_file_metadata():
    data = request.get_json(silent=True) or {}
    workspace_id = data.get('workspace_id')
    filename = data.get('filename')
    if not workspace_id or not filename:
        return error_response('workspace_id and filename are required', 400)
    current_user_id = int(get_jwt_identity())
    _, err = _authorize_workspace(workspace_id, current_user_id)
    if err:
        return err
    file = DriveFile(
        filename=filename,
        workspace_id=workspace_id,
        created_by=current_user_id,
        folder_id=data.get('folder_id'),
        mime_type=data.get('mime_type', 'application/octet-stream'),
        size_bytes=data.get('size_bytes', 0),
        owner_scope_type=data.get('owner_scope_type', 'startup'),
        owner_scope_id=data.get('owner_scope_id', workspace_id),
        owner_user_id=current_user_id,
        visibility_scope=data.get('visibility_scope', 'private'),
        sensitivity_level=data.get('sensitivity_level', 'internal'),
        state='active',
        uploaded_at=db.func.now(),
    )
    db.session.add(file)
    db.session.commit()
    return success_response(file.to_dict(), 201)

@drive_bp.route('/files/<int:file_id>', methods=['PUT'])
@jwt_required()
def update_file_metadata(file_id):
    file = DriveFile.query.get_or_404(file_id)
    current_user_id = int(get_jwt_identity())
    _, err = _authorize_workspace(file.workspace_id, current_user_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    for field in ['filename', 'folder_id', 'visibility_scope', 'sensitivity_level']:
        if field in data:
            setattr(file, field, data[field])
    db.session.commit()
    return success_response(file.to_dict())

@drive_bp.route('/files/<int:file_id>', methods=['DELETE'])
@jwt_required()
def delete_file(file_id):
    file = DriveFile.query.get_or_404(file_id)
    current_user_id = int(get_jwt_identity())
    _, err = _authorize_workspace(file.workspace_id, current_user_id)
    if err:
        return err
    file.state = 'deleted'
    db.session.commit()
    return success_response({'message': 'File deleted'}, 200)
