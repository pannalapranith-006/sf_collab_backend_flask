from datetime import datetime
from app.extensions import db
from app.models.rp_work_milestone import WorkMilestone
from app.services.rp_event_emitter import emit_event
from flask import abort

class MilestoneService:

    @staticmethod
    def create_milestone(workspace_id, data):
        milestone = WorkMilestone(
            workspace_id=workspace_id,
            name=data['name'],
            description=data.get('description', ''),
            target_date=data.get('target_date'),
            completion_criteria=data.get('completion_criteria', '')
        )
        db.session.add(milestone)
        db.session.commit()
        return milestone

    @staticmethod
    def complete_milestone(milestone):
        if milestone.status == 'completed':
            raise ValueError("Milestone already completed")
        milestone.status = 'completed'
        db.session.commit()

        emit_event('milestone_completed', {
            'milestone_id': milestone.id,
            'workspace_id': milestone.workspace_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        return milestone

    @staticmethod
    def get_milestone_or_404(milestone_id, workspace_id):
        milestone = WorkMilestone.query.filter_by(
            id=milestone_id, workspace_id=workspace_id
        ).first()
        if not milestone:
            abort(404, description="Milestone not found")
        return milestone