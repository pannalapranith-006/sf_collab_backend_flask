from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required
from app.models.rp_work_milestone import WorkMilestone
from app.services.rp_milestone_service import MilestoneService

work_milestones_bp = Blueprint('work_milestones', __name__)

@work_milestones_bp.route('', methods=['GET'])
@jwt_required()
def list_milestones(workspace_id):
    milestones = WorkMilestone.query.filter_by(workspace_id=workspace_id).all()
    return jsonify([{
        'id': m.id, 'name': m.name, 'status': m.status,
        'target_date': str(m.target_date) if m.target_date else None
    } for m in milestones])

@work_milestones_bp.route('', methods=['POST'])
@jwt_required()
def create_milestone(workspace_id):
    data = request.get_json()
    milestone = MilestoneService.create_milestone(workspace_id, data)
    return jsonify({'id': milestone.id, 'name': milestone.name}), 201

@work_milestones_bp.route('/<int:milestone_id>/complete', methods=['POST'])
@jwt_required()
def complete_milestone(workspace_id, milestone_id):
    milestone = MilestoneService.get_milestone_or_404(milestone_id, workspace_id)
    milestone = MilestoneService.complete_milestone(milestone)
    return jsonify({'status': milestone.status})