from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.drive import DriveFile, DriveFolder
from app.models.startup import Startup
from app.models.startUpMember import StartupMember

drive_bp = Blueprint('drive', __name__, url_prefix='/api/drive')

def _authorize_workspace(workspace_id, user_id):
    """
    Verifies if a user has access to a workspace.
    Returns (startup, error_response, status_code)
    """
    startup = Startup.query.get(workspace_id)
    if not startup:
        return None, jsonify({'error': 'Workspace not found'}), 404
        
    # Check if user is creator or an active member
    is_member = StartupMember.query.filter_by(
        startup_id=workspace_id, 
        user_id=user_id, 
        is_active=True
    ).first()
    
    is_creator = startup.creator_id == user_id
    
    if not is_member and not is_creator:
        return None, jsonify({'error': 'Unauthorized access to this workspace'}), 403
        
    return startup, None, None

@drive_bp.route('/files', methods=['GET'])
@jwt_required()
def list_files():
    workspace_id = request.args.get('workspace_id', type=int)
    if workspace_id is None:
        return jsonify({'error': 'workspace_id is required'}), 400
    
    current_user_id = get_jwt_identity()
    _, error_resp, status = _authorize_workspace(workspace_id, current_user_id)
    if error_resp:
        return error_resp, status
    
    files = DriveFile.query.filter_by(workspace_id=workspace_id).all()
    return jsonify([f.to_dict() for f in files])

@drive_bp.route('/folders', methods=['GET'])
@jwt_required()
def list_folders():
    workspace_id = request.args.get('workspace_id', type=int)
    if workspace_id is None:
        return jsonify({'error': 'workspace_id is required'}), 400
    
    current_user_id = get_jwt_identity()
    _, error_resp, status = _authorize_workspace(workspace_id, current_user_id)
    if error_resp:
        return error_resp, status
    
    folders = DriveFolder.query.filter_by(workspace_id=workspace_id).all()
    return jsonify([f.to_dict() for f in folders])
