"""
Activation Routes — SF Collab
================================
Handles the Vision → Startup activation flow and Startup → Vision demotion.

Blueprint mounted at /api/activation

Endpoints:
  GET  /api/activation/ideas/<id>/eligibility    — check if vision can be activated
  POST /api/activation/ideas/<id>/activate       — activate vision as startup
  POST /api/activation/startups/<id>/demote      — demote solo startup → vision
  GET  /api/activation/startups/<id>/solo-check  — check if startup should be demoted

Activation Rules:
  - Readiness score ≥ 70
  - At least 2 collaborators (team members)
  - Roadmap defined (at least 1 roadmap item)
  - Only the creator can activate

Demotion Rules:
  - Startup has team size = 1 (solo founder only)
  - Can be triggered manually or by admin
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.idea import Idea
from app.models.startup import Startup, StartupStage
from app.models.user import User
from app.models.teamMember import TeamMember

activation_bp = Blueprint('activation', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def success_response(data, message='', status=200):
    return jsonify({'success': True, 'message': message, **data}), status

def error_response(message, status=400):
    return jsonify({'success': False, 'error': message}), status

def _check_activation_eligibility(idea: Idea) -> dict:
    """
    Returns a dict describing whether the vision can be activated.
    Used by both the eligibility endpoint and the activation endpoint.
    """
    team_size   = idea.get_team_size()
    has_roadmap = bool(idea.roadmap_items and len(idea.roadmap_items) >= 1)
    score       = idea.readiness_score or 0.0

    checks = {
        'readiness_score': {
            'passed': score >= 70,
            'value': score,
            'required': 70,
            'message': f'Readiness score is {round(score)}% — needs 70%' if score < 70 else None,
        },
        'collaborators': {
            'passed': team_size >= 2,
            'value': team_size,
            'required': 2,
            'message': f'Need {2 - team_size} more collaborator{"s" if 2 - team_size > 1 else ""}' if team_size < 2 else None,
        },
        'roadmap': {
            'passed': has_roadmap,
            'value': len(idea.roadmap_items) if idea.roadmap_items else 0,
            'required': 1,
            'message': 'Define at least one roadmap item' if not has_roadmap else None,
        },
    }

    eligible = all(c['passed'] for c in checks.values())
    blocking_reasons = [c['message'] for c in checks.values() if not c['passed']]

    return {
        'eligible': eligible,
        'checks': checks,
        'blocking_reasons': blocking_reasons,
        'readiness_score': score,
        'team_size': team_size,
    }


def _convert_roadmap_to_milestones(startup: Startup, roadmap_items: list):
    """
    Convert vision roadmap items into startup goal milestones.
    Each roadmap item becomes a GoalMilestone on the startup.
    """
    try:
        from app.models.goalMilestone import GoalMilestone
        from app.models.projectGoal import ProjectGoal

        # Create a single "Roadmap" project goal to hold migrated milestones
        goal = ProjectGoal(
            startup_id=startup.id,
            title='Vision Roadmap',
            description='Milestones migrated from vision activation',
            status='active',
            created_at=datetime.utcnow(),
        )
        db.session.add(goal)
        db.session.flush()

        for i, item in enumerate(roadmap_items):
            title = item if isinstance(item, str) else item.get('title', f'Milestone {i+1}')
            milestone = GoalMilestone(
                goal_id=goal.id,
                title=title,
                description=item.get('description', '') if isinstance(item, dict) else '',
                status='pending',
                order=i + 1,
            )
            db.session.add(milestone)

        startup.milestones_total = len(roadmap_items)
        db.session.flush()
        return True

    except Exception as e:
        # Milestone migration is best-effort — don't block activation
        print(f'⚠ Roadmap → milestone migration failed: {e}')
        return False


# ── ELIGIBILITY CHECK ─────────────────────────────────────────────────────────

@activation_bp.route('/ideas/<int:idea_id>/eligibility', methods=['GET'])
@jwt_required()
def check_eligibility(idea_id):
    """
    Check whether a vision meets all activation requirements.
    Also recalculates the readiness score so the result is always fresh.
    """
    try:
        user_id = int(get_jwt_identity())
        idea    = Idea.query.get(idea_id)
        if not idea:
            return error_response('Vision not found', 404)

        # Recalculate readiness score before checking
        idea.compute_readiness_score()

        result = _check_activation_eligibility(idea)
        result['vision'] = {
            'id': idea.id,
            'title': idea.title,
            'vision_state': idea.vision_state,
            'readiness_score': idea.readiness_score,
        }
        result['is_creator'] = (idea.creator_id == user_id)

        return success_response(result)

    except Exception as e:
        return error_response(str(e), 500)


# ── ACTIVATE VISION → STARTUP ─────────────────────────────────────────────────

@activation_bp.route('/ideas/<int:idea_id>/activate', methods=['POST'])
@jwt_required()
def activate_vision(idea_id):
    """
    Activate a vision as a startup.

    Steps:
    1. Validate eligibility (score ≥ 70, 2+ collaborators, roadmap defined)
    2. Create Startup from vision data
    3. Transfer team members to startup
    4. Convert roadmap items → milestones
    5. Archive the vision (set vision_state = 'archived')
    6. Emit startup_activated event
    7. Notify team members

    Body (optional):
      startup_name  — override name (defaults to vision title)
    """
    try:
        user_id = int(get_jwt_identity())
        idea    = Idea.query.get(idea_id)

        if not idea:
            return error_response('Vision not found', 404)

        if idea.creator_id != user_id:
            return error_response('Only the vision creator can activate it as a startup', 403)

        if idea.vision_state == 'archived':
            return error_response('This vision has already been activated or archived', 400)

        # Recalculate score first
        idea.compute_readiness_score()

        # Check eligibility
        eligibility = _check_activation_eligibility(idea)
        if not eligibility['eligible']:
            return jsonify({
                'success': False,
                'error': 'Vision does not meet activation requirements',
                'blocking_reasons': eligibility['blocking_reasons'],
                'checks': eligibility['checks'],
            }), 422

        data         = request.get_json() or {}
        creator      = User.query.get(user_id)
        startup_name = data.get('startup_name', idea.title).strip()

        # Check startup name uniqueness
        existing = Startup.query.filter_by(name=startup_name).first()
        if existing:
            startup_name = f"{startup_name} (Startup)"

        # ── Create Startup ────────────────────────────────────────────────────
        startup = Startup(
            name=startup_name,
            industry=idea.industry or 'Technology',
            description=idea.description,
            stage=StartupStage.idea,
            creator_id=user_id,
            creator_first_name=creator.first_name if creator else '',
            creator_last_name=creator.last_name if creator else '',
            lifecycle_state='active',
            # Copy vision structured fields where applicable
            positions=len(idea.required_roles or []),
        )
        db.session.add(startup)
        db.session.flush()  # get startup.id

        # ── Transfer team members ─────────────────────────────────────────────
        transferred = 0
        team_members = idea.team_members.all()

        # Add creator first
        try:
            startup.add_member(
                user_id=user_id,
                first_name=creator.first_name if creator else '',
                last_name=creator.last_name if creator else '',
                role='founder',
            )
        except Exception:
            pass

        for tm in team_members:
            # Skip if this is the creator's own TeamMember record
            try:
                if tm.user_id and tm.user_id != user_id:
                    member_user = User.query.get(tm.user_id)
                    startup.add_member(
                        user_id=tm.user_id,
                        first_name=member_user.first_name if member_user else tm.name.split()[0],
                        last_name=member_user.last_name if member_user else '',
                        role=tm.position or 'member',
                    )
                    transferred += 1
            except Exception as e:
                print(f'⚠ Failed to transfer team member {tm.id}: {e}')

        # ── Convert roadmap → milestones ──────────────────────────────────────
        milestone_migrated = False
        if idea.roadmap_items:
            milestone_migrated = _convert_roadmap_to_milestones(startup, idea.roadmap_items)

        # ── Archive the vision ────────────────────────────────────────────────
        idea.vision_state = 'archived'
        idea.updated_at   = datetime.utcnow()

        db.session.commit()

        # ── Emit startup_activated socket event ───────────────────────────────
        try:
            from app.extensions import socketio
            socketio.emit('startup_activated', {
                'startup_id': startup.id,
                'startup_name': startup.name,
                'idea_id': idea_id,
                'activated_by': user_id,
            })
        except Exception as e:
            print(f'⚠ Socket emit failed: {e}')

        # ── Notify team members ───────────────────────────────────────────────
        try:
            from app.notifications.service import notification_service
            for tm in team_members:
                if tm.user_id and tm.user_id != user_id:
                    notification_service.create_notification(
                        user_id=tm.user_id,
                        template_key='STARTUP_CREATED',
                        actor_id=user_id,
                        entity_type='startup',
                        entity_id=startup.id,
                        variables={
                            'name': startup.name,
                        },
                        link_url=f'/startup-details/{startup.id}',
                    )
        except Exception as e:
            print(f'⚠ Notification dispatch failed: {e}')

        return success_response({
            'startup': startup.to_dict(),
            'transferred_members': transferred,
            'milestone_migrated': milestone_migrated,
            'roadmap_items_count': len(idea.roadmap_items or []),
        }, message=f'Vision activated as startup "{startup.name}"!', status=201)

    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)


# ── DEMOTE STARTUP → VISION ───────────────────────────────────────────────────

@activation_bp.route('/startups/<int:startup_id>/solo-check', methods=['GET'])
@jwt_required()
def check_solo_startup(startup_id):
    """
    Check if a startup is solo (only the founder) and eligible for demotion.
    """
    try:
        user_id = int(get_jwt_identity())
        startup = Startup.query.get(startup_id)
        if not startup:
            return error_response('Startup not found', 404)

        from app.models.startUpMember import StartupMember
        active_members = StartupMember.query.filter_by(
            startup_id=startup_id, is_active=True
        ).count()

        is_solo    = active_members <= 1
        is_creator = startup.creator_id == user_id

        return success_response({
            'is_solo': is_solo,
            'active_members': active_members,
            'is_creator': is_creator,
            'should_demote': is_solo,
            'startup': {
                'id': startup.id,
                'name': startup.name,
                'lifecycle_state': startup.lifecycle_state,
            }
        })

    except Exception as e:
        return error_response(str(e), 500)


@activation_bp.route('/startups/<int:startup_id>/demote', methods=['POST'])
@jwt_required()
def demote_startup_to_vision(startup_id):
    """
    Demote a solo startup back to a Vision (Idea).

    Only triggered when:
    - Startup has team_size = 1 (solo founder)
    - Creator requests demotion OR admin triggers it

    Preserves: description, industry, sector, founder, tags
    Adds: label "Converted Vision", sets vision_state = 'public'
    """
    try:
        user_id = int(get_jwt_identity())
        startup = Startup.query.get(startup_id)

        if not startup:
            return error_response('Startup not found', 404)

        if startup.creator_id != user_id:
            user = User.query.get(user_id)
            if not user or not user.is_admin():
                return error_response('Only the startup creator or admin can demote a startup', 403)

        # Check team size
        from app.models.startUpMember import StartupMember
        active_members = StartupMember.query.filter_by(
            startup_id=startup_id, is_active=True
        ).count()

        if active_members > 1:
            return error_response(
                f'This startup has {active_members} active members and cannot be demoted. '
                'Demotion is only for solo startups.',
                400
            )

        creator = User.query.get(user_id)

        # ── Create Vision (Idea) from startup ─────────────────────────────────
        idea = Idea(
            title=startup.name,
            description=startup.description or '',
            project_details=startup.description or '',
            industry=startup.industry or 'Technology',
            stage='idea',
            creator_id=user_id,
            creator_first_name=creator.first_name if creator else '',
            creator_last_name=creator.last_name if creator else '',
            vision_state='public',
            readiness_score=0.0,
            tags=['Converted Vision'],
            # Preserve roadmap if startup had milestones stored
        )
        db.session.add(idea)
        db.session.flush()

        # Recalculate readiness for the new vision
        idea.compute_readiness_score()

        # ── Archive the startup ───────────────────────────────────────────────
        startup.lifecycle_state = 'archived'
        startup.status          = 'archived'

        db.session.commit()

        # ── Notify the founder ────────────────────────────────────────────────
        try:
            from app.notifications.service import notification_service
            notification_service.create_simple_notification(
                user_id=user_id,
                title='Project Converted to Vision',
                message=(
                    f'Your project "{startup.name}" was converted to a Vision so you can '
                    'attract collaborators before activation.'
                ),
                notification_type='info',
                category='startup',
                entity_type='idea',
                entity_id=idea.id,
                link_url=f'/ideation/{idea.id}',
            )
        except Exception as e:
            print(f'⚠ Demotion notification failed: {e}')

        return success_response({
            'idea': idea.to_dict(user_id=user_id),
            'archived_startup_id': startup_id,
            'message_to_display': (
                'Your project was converted to a Vision so you can '
                'attract collaborators before activation.'
            ),
        }, message='Startup demoted to Vision successfully')

    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)