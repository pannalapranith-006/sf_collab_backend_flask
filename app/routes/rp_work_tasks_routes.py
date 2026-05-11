from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.rp_task_service import TaskService

work_tasks_bp = Blueprint('work_tasks', __name__)

@work_tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task(workspace_id):
    user_id = get_jwt_identity()
    data = request.get_json()
    task = TaskService.create_task(workspace_id, user_id, data)
    return jsonify({'id': task.id, 'title': task.title}), 201

@work_tasks_bp.route('', methods=['GET'])
@jwt_required()
def list_tasks(workspace_id):
    tasks = TaskService.get_workspace_tasks(workspace_id)
    return jsonify([{
        'id': t.id, 'title': t.title, 'status': t.status,
        'assignee_id': t.assignee_id, 'approver_id': t.approver_id
    } for t in tasks])

@work_tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(workspace_id, task_id):
    task = TaskService.get_task_or_404(task_id, workspace_id)
    return jsonify({
        'id': task.id, 'title': task.title, 'description': task.description,
        'status': task.status, 'created_by': task.created_by,
        'assignee_id': task.assignee_id, 'approver_id': task.approver_id,
        'proof_required': task.proof_required, 'proof_url': task.proof_url,
        'milestone_id': task.milestone_id
    })

@work_tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(workspace_id, task_id):
    task = TaskService.get_task_or_404(task_id, workspace_id)
    data = request.get_json()
    task = TaskService.update_task(task, data)
    return jsonify({'message': 'updated'})

@work_tasks_bp.route('/<int:task_id>/status', methods=['PATCH'])
@jwt_required()
def change_task_status(workspace_id, task_id):
    task = TaskService.get_task_or_404(task_id, workspace_id)
    data = request.get_json()
    new_status = data.get('status')
    if not new_status:
        abort(400, "status is required")
    actor_id = get_jwt_identity()
    task = TaskService.change_status(task, new_status, actor_id)
    return jsonify({'status': task.status})

@work_tasks_bp.route('/<int:task_id>/proof', methods=['POST'])
@jwt_required()
def submit_proof(workspace_id, task_id):
    task = TaskService.get_task_or_404(task_id, workspace_id)
    data = request.get_json()
    proof_url = data.get('proof_url')
    if not proof_url:
        abort(400, "proof_url is required")
    task = TaskService.submit_proof(task, proof_url)
    return jsonify({'status': 'submitted', 'proof_url': task.proof_url})