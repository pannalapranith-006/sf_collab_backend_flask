from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.helper import success_response, error_response
from app.services.task_lifecycle_service import change_status
from app.middleware import workspace_member_required
from app.models.erp_task import ErpTask

task_lifecycle_bp = Blueprint('task_lifecycle', __name__)

@task_lifecycle_bp.route('/workspaces/<int:workspace_id>/tasks/<int:task_id>/status', methods=['PUT'])
@jwt_required()
@workspace_member_required
def update_task_status(workspace_id, task_id):
    data = request.get_json()
    new_status = data.get('status')
    comment = data.get('comment')

    if not new_status:
        return error_response(message='status is required', status=400)

    user_id = int(get_jwt_identity())

    # Verify task belongs to workspace
    task = ErpTask.query.get(task_id)
    if not task or task.workspace_id != workspace_id:
        return error_response(message='Task not found', status=404)

    # Admin only for approval/rejection
    if new_status in ['approved', 'rejected']:
        from app.services.membership_service import is_admin
        if not is_admin(workspace_id, user_id):
            return error_response(message='Only admins can approve or reject tasks.', status=403)

    try:
        change_status(task_id, new_status, user_id)

        # If approval/rejection, record it (you may already have this in service)
        if new_status in ['approved', 'rejected']:
            from app.services.task_approval_service import record_approval
            record_approval(task_id, user_id, new_status, comment)

        return success_response(message='Task status updated', data={
            'id': task.id,
            'status': task.status
        })
    except ValueError as e:
        return error_response(message=str(e), status=400)