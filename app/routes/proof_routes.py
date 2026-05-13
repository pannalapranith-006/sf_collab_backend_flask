from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.helper import success_response, error_response
from app.services.proof_service import upload_proof, get_proofs_for_task, review_proof
from app.middleware import workspace_member_required, workspace_admin_required
from app.models.erp_task import ErpTask
from app.models.proof import Proof

proof_bp = Blueprint('proof', __name__)

@proof_bp.route('/workspaces/<int:workspace_id>/tasks/<int:task_id>/proofs', methods=['POST'])
@jwt_required()
@workspace_member_required
def upload_proof_route(workspace_id, task_id):
    task = ErpTask.query.get(task_id)
    if not task or task.workspace_id != workspace_id:
        return error_response(message='Task not found in this workspace', status=404)

    user_id = int(get_jwt_identity())
    if 'file' not in request.files:
        return error_response(message='No file part in the request.', status=400)
    file = request.files['file']
    try:
        proof = upload_proof(task_id, user_id, file)
        return success_response(message='Proof uploaded successfully', data={
            'id': proof.id,
            'filename': proof.original_filename,
            'size': proof.file_size,
            'uploaded_at': proof.created_at.isoformat()
        }, status=201)
    except ValueError as e:
        return error_response(message=str(e), status=400)

@proof_bp.route('/workspaces/<int:workspace_id>/tasks/<int:task_id>/proofs', methods=['GET'])
@jwt_required()
@workspace_member_required
def list_proofs_route(workspace_id, task_id):
    task = ErpTask.query.get(task_id)
    if not task or task.workspace_id != workspace_id:
        return error_response(message='Task not found', status=404)
    proofs = get_proofs_for_task(task_id)
    return success_response(message='Proofs retrieved', data=[{
        'id': p.id,
        'user_id': p.user_id,
        'original_filename': p.original_filename,
        'file_path': p.file_path,
        'file_size': p.file_size,
        'mime_type': p.mime_type,
        'status': p.status,
        'reviewed_by': p.reviewed_by,
        'reviewed_at': p.reviewed_at.isoformat() if p.reviewed_at else None,
        'review_comment': p.review_comment,
        'created_at': p.created_at.isoformat()
    } for p in proofs])

@proof_bp.route('/workspaces/<int:workspace_id>/tasks/<int:task_id>/proofs/<int:proof_id>/review', methods=['PUT'])
@jwt_required()
@workspace_admin_required
def review_proof_route(workspace_id, task_id, proof_id):
    proof = Proof.query.get(proof_id)
    if not proof or proof.task_id != task_id or proof.task.workspace_id != workspace_id:
        return error_response(message='Proof not found', status=404)

    data = request.get_json()
    status = data.get('status')
    comment = data.get('comment')
    if not status:
        return error_response(message='status is required', status=400)
    user_id = int(get_jwt_identity())
    try:
        proof = review_proof(proof_id, user_id, status, comment)
        return success_response(message=f'Proof {status}', data={
            'id': proof.id,
            'status': proof.status,
            'reviewed_by': proof.reviewed_by,
            'reviewed_at': proof.reviewed_at.isoformat() if proof.reviewed_at else None,
            'comment': proof.review_comment
        })
    except ValueError as e:
        return error_response(message=str(e), status=400)