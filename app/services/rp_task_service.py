from datetime import datetime
from app.extensions import db
from app.models.rp_work_task import WorkTask
from app.services.rp_event_emitter import emit_event
from flask import abort

class TaskService:

    @staticmethod
    def create_task(workspace_id, creator_id, data):
        task = WorkTask(
            workspace_id=workspace_id,
            title=data['title'],
            description=data.get('description', ''),
            created_by=creator_id,
            assignee_id=data.get('assignee_id'),
            approver_id=data.get('approver_id'),
            proof_required=data.get('proof_required', False),
            proof_description=data.get('proof_description', ''),
            milestone_id=data.get('milestone_id')
        )
        db.session.add(task)
        db.session.commit()

        emit_event('task_created', {
            'task_id': task.id,
            'workspace_id': workspace_id,
            'created_by': creator_id,
            'assignee_id': task.assignee_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        return task

    @staticmethod
    def update_task(task, data):
        for field in ['title', 'description', 'assignee_id', 'approver_id',
                       'proof_required', 'proof_description', 'milestone_id']:
            if field in data:
                setattr(task, field, data[field])
        db.session.commit()
        return task

    @staticmethod
    def change_status(task, new_status, actor_id):
        if not task.can_transition_to(new_status):
            raise ValueError(f"Cannot transition from {task.status} to {new_status}")
        task.status = new_status
        db.session.commit()

        if new_status == 'approved':
            emit_event('task_approved', {
                'task_id': task.id,
                'workspace_id': task.workspace_id,
                'approved_by': actor_id,
                'assignee_id': task.assignee_id,
                'timestamp': datetime.utcnow().isoformat()
            })
            emit_event('task_completed', {
                'task_id': task.id,
                'workspace_id': task.workspace_id,
                'completed_by': task.assignee_id,
                'timestamp': datetime.utcnow().isoformat()
            })
        return task

    @staticmethod
    def submit_proof(task, proof_url):
        if not task.proof_required:
            raise ValueError("This task does not require proof")
        if task.status != 'in_progress':
            raise ValueError("Only in-progress tasks can submit proof")
        task.proof_url = proof_url
        task.status = 'submitted'
        db.session.commit()
        emit_event('task_completed', {
            'task_id': task.id,
            'workspace_id': task.workspace_id,
            'completed_by': task.assignee_id,
            'proof_url': proof_url,
            'timestamp': datetime.utcnow().isoformat()
        })
        return task

    @staticmethod
    def get_workspace_tasks(workspace_id):
        return WorkTask.query.filter_by(workspace_id=workspace_id).all()

    @staticmethod
    def get_task_or_404(task_id, workspace_id):
        task = WorkTask.query.filter_by(id=task_id, workspace_id=workspace_id).first()
        if not task:
            abort(404, description="Task not found")
        return task