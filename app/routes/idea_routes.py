from flask import Blueprint, request
from app.models.idea import Idea
from app.models.user import User
from app.services.achievement_service import AchievementService
from app.extensions import db
from app.utils.helper import error_response, success_response, paginate
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.ideaLike import IdeaLike
from app.models.waitlist import Waitlist
import datetime
import json
from app.utils.upload_to_s3 import upload_file_to_s3
from app.models.notification import Notification
# Import notification helpers
from app.notifications.helpers import (
    notify_idea_submitted,
    notify_idea_voted,
    notify_idea_status_changed,
    notify_idea_feedback
)

ideas_bp = Blueprint('ideas', __name__)


def get_user_full_name(user_id):
    """Helper to get user's full name"""
    user = User.query.get(user_id)
    if user:
        return f"{user.first_name or ''} {user.last_name or ''}".strip() or "Someone"
    return "Someone"


@ideas_bp.route('', methods=['GET'])
@jwt_required()
def get_ideas():
    """Get all ideas with filtering"""
    current_user_id = int(get_jwt_identity())
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    industry = request.args.get('industry', type=str)
    stage = request.args.get('stage', type=str)
    creator_id = request.args.get('creator_id', type=int)
    search = request.args.get('search', type=str)
    sort_by = request.args.get('sort_by', 'created_at', type=str)
    query = Idea.query
    
    if industry:
        query = query.filter(Idea.industry.ilike(f'%{industry}%'))
    if stage:
        query = query.filter(Idea.stage == stage)
    if creator_id:
        query = query.filter(Idea.creator_id == creator_id)
    if search:
        query = query.filter(
            (Idea.title.ilike(f'%{search}%')) |
            (Idea.description.ilike(f'%{search}%')) |
            (Idea.project_details.ilike(f'%{search}%'))
        )
    if sort_by in ['created_at', 'likes']:
        query = query.order_by(getattr(Idea, sort_by).desc())
    result = paginate(query, page, per_page)
    
    return success_response({
        'ideas': [idea.to_dict(current_user_id) for idea in result['items']],
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
            'pages': result['pages']
        }
    })
@ideas_bp.route('/top', methods=['GET'])
def get_top_ideas():
    """Get top ideas based on likes"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    limit = request.args.get('limit', 10, type=int)
    query = Idea.query.order_by(Idea.likes.desc()).limit(limit)
    result = paginate(query, page, per_page)
    
    return success_response({
        'ideas': [idea.to_dict() for idea in result['items']],
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
            'pages': result['pages']
        }
    })

@ideas_bp.route('/<int:idea_id>', methods=['GET'])
@jwt_required()
def get_idea(idea_id):
    """Get single idea by ID"""
    current_user_id = int(get_jwt_identity())
    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)
    
    # Increment views
    idea.increment_views()
    
    include_comments = request.args.get('include_comments', 'false').lower() == 'true'
    
    return success_response({
        'idea': idea.to_dict(user_id=current_user_id, include_comments=include_comments)
    })


@ideas_bp.route('', methods=['POST'])
@jwt_required()
def create_idea():
    """Create new idea"""
    user_id = int(get_jwt_identity())
    
    # Get form data
    title = request.form.get('title')
    description = request.form.get('description')
    project_details = request.form.get('projectDetails')
    industry = request.form.get('industry')
    stage = request.form.get('stage')
    tags = request.form.get('tags')
    image_file = request.files.get('image')
    creator_first_name = request.form.get('creator_first_name')
    creator_last_name = request.form.get('creator_last_name')
    
    required_fields = {'title', 'description', 'projectDetails', 'industry', 'stage'}
    if not all(request.form.get(field) for field in required_fields):
        return error_response('Missing required fields')
    
    try:
        # Parse tags from JSON string
        tags_list = json.loads(tags) if tags else []
        
        idea = Idea(
            title=title,
            description=description,
            project_details=project_details,
            industry=industry,
            stage=stage,
            tags=tags_list,
            creator_id=user_id,
            creator_first_name=creator_first_name,
            creator_last_name=creator_last_name,
        )
        
        # Handle image upload if provided
        if image_file:
            image_url = upload_file_to_s3(image_file)
            idea.image_url = image_url 
        
        db.session.add(idea)
        db.session.flush()

        # Award points to waitlist user if they exist
        waitlist_user = Waitlist.query.filter_by(email=User.query.get(user_id).email).first()
        if waitlist_user:
            # Check if they already got points today
            today = datetime.datetime.utcnow().date()
            last_activity_date = waitlist_user.last_activity_at.date() if waitlist_user.last_activity_at else None
            
            if last_activity_date != today:
                waitlist_user.add_points(Waitlist.POINTS_PER_IDEA, 'idea')
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Idea Submitted (4.3)
        # ════════════════════════════════════════════════════════════
        try:
            notify_idea_submitted(
                user_id=user_id,
                idea_title=title,
                idea_id=idea.id
            )
        except Exception as e:
            print(f"⚠️ Idea submission notification failed: {e}")
        
        # Check achievements for idea creation
        AchievementService.check_achievements(user_id, 'ideas_created')
        
        return success_response({
            'idea': idea.to_dict()
        }, 'Idea created successfully', 201)
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to create idea: {str(e)}', 500)


@ideas_bp.route('/<int:idea_id>', methods=['PUT'])
@jwt_required()
def update_idea(idea_id):
    """Update idea"""
    current_user_id = int(get_jwt_identity())
    
    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)
    
    data = request.get_json()
    old_stage = idea.stage
    
    try:
        if 'title' in data:
            idea.title = data['title']
        if 'description' in data:
            idea.description = data['description']
        if 'project_details' in data:
            idea.project_details = data['project_details']
        if 'industry' in data:
            idea.industry = data['industry']
        if 'stage' in data:
            idea.update_stage(data['stage'])
        if 'tags' in data:
            idea.tags = data['tags']
        
        db.session.commit()

        # ── Recalculate readiness score when vision fields change ──────────
        vision_fields = {'title', 'description', 'problem_statement', 'outcome_goal',
                         'roadmap_items', 'required_roles', 'tags', 'stage'}
        if any(f in data for f in vision_fields):
            try:
                idea.compute_readiness_score()
            except Exception as e:
                print(f"⚠️ Readiness recalculation failed: {e}")

        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Idea Status Changed (4.3)
        # ════════════════════════════════════════════════════════════
        if 'stage' in data and old_stage != data['stage']:
            try:
                notify_idea_status_changed(
                    user_id=idea.creator_id,
                    idea_title=idea.title,
                    idea_id=idea.id,
                    old_status=old_stage or 'draft',
                    new_status=data['stage']
                )
            except Exception as e:
                print(f"⚠️ Idea status change notification failed: {e}")
        
        return success_response({
            'idea': idea.to_dict()
        }, 'Idea updated successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to update idea: {str(e)}', 500)


@ideas_bp.route('/<int:idea_id>/like', methods=['POST'])
@jwt_required()
def like_idea(idea_id):
    """Like/vote for an idea"""
    current_user_id = int(get_jwt_identity())
    
    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)
    liked = False
    try:
        ideas = IdeaLike.query.filter_by(user_id=current_user_id).all()
        if any(like.idea_id == idea_id for like in ideas):
            IdeaLike.query.filter_by(user_id=current_user_id, idea_id=idea_id).delete()
            idea.likes = IdeaLike.query.filter_by(idea_id=idea_id).count()
            liked = False
        else:
            new_like = IdeaLike(user_id=current_user_id, idea_id=idea_id)
            db.session.add(new_like)
            idea.likes = IdeaLike.query.filter_by(idea_id=idea_id).count()
            liked = True
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Idea Voted/Liked (4.3)
        # ════════════════════════════════════════════════════════════
        # Only notify if not self-like
        if idea.creator_id != current_user_id:
            try:
                voter_name = get_user_full_name(current_user_id)
                # Prevent SPAM: Only send notification if user hasn't already liked today
                last_like = IdeaLike.query.filter_by(user_id=current_user_id, idea_id=idea_id).first()
                today = datetime.datetime.utcnow().date()
                if last_like and last_like.created_at.date() == today:
                    print("User has already liked this idea today, skipping notification")
                elif liked:
                    notify_idea_voted(
                        user_id=idea.creator_id,
                        voter_id=current_user_id,
                        voter_name=voter_name,
                        idea_title=idea.title,
                        idea_id=idea.id
                    )
                else:
                    # Remove notification
                    Notification.query.filter_by(
                        user_id=idea.creator_id,
                        actor_id=current_user_id,
                        verb='liked',
                        target_id=idea.id
                    ).delete()
                    db.session.commit()
            except Exception as e:
                print(f"⚠️ Idea vote notification failed: {e}")
        
        # Check achievements for likes received
        AchievementService.check_achievements(idea.creator_id, 'likes_received')
        
        return success_response({
            'idea': idea.to_dict()
        }, 'Idea liked successfully')
    except Exception as e:
        return error_response(f'Failed to like idea: {str(e)}', 500)


@ideas_bp.route('/<int:idea_id>/feedback', methods=['POST'])
@jwt_required()
def add_idea_feedback(idea_id):
    """Add feedback to an idea"""
    current_user_id = int(get_jwt_identity())
    
    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)
    
    data = request.get_json()
    feedback_content = data.get('feedback')
    
    if not feedback_content:
        return error_response('Feedback content is required', 400)
    
    try:
        # Add feedback logic here (store in idea.feedback or separate model)
        # This is a placeholder - implement based on your model structure
        
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Idea Feedback Received (4.3)
        # ════════════════════════════════════════════════════════════
        if idea.creator_id != current_user_id:
            try:
                feedback_giver_name = get_user_full_name(current_user_id)
                notify_idea_feedback(
                    user_id=idea.creator_id,
                    feedback_giver_id=current_user_id,
                    feedback_giver_name=feedback_giver_name,
                    idea_title=idea.title,
                    idea_id=idea.id
                )
            except Exception as e:
                print(f"⚠️ Idea feedback notification failed: {e}")
        
        return success_response({
            'idea': idea.to_dict()
        }, 'Feedback added successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to add feedback: {str(e)}', 500)


@ideas_bp.route('/<int:idea_id>/team-members', methods=['POST'])
def add_team_member(idea_id):
    """Add team member to idea"""
    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)
    
    data = request.get_json()
    required_fields = ['name', 'position']
    if not all(field in data for field in required_fields):
        return error_response('Missing required fields: name, position')
    
    try:
        member = idea.add_team_member(
            name=data['name'],
            position=data['position'],
            skills=data.get('skills')
        )

        # ── Recalculate readiness — new collaborator joined ────────────────
        try:
            idea.compute_readiness_score()
        except Exception as e:
            print(f"⚠️ Readiness recalculation failed: {e}")

        return success_response({
            'team_member': {
                'name': member.name,
                'position': member.position,
                'skills': member.skills
            }
        }, 'Team member added successfully')
    except Exception as e:
        return error_response(f'Failed to add team member: {str(e)}', 500)


@ideas_bp.route('/<int:idea_id>', methods=['DELETE'])
@jwt_required()
def delete_idea(idea_id):
    """Delete idea"""
    current_user_id = int(get_jwt_identity())
    
    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)
    
    # Check ownership
    if int(idea.creator_id) != int(current_user_id):
        return error_response('Unauthorized to delete this idea', 403)
    
    try:
        db.session.delete(idea)
        db.session.commit()
        return success_response(message='Idea deleted successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to delete idea: {str(e)}', 500)


@ideas_bp.route('/images/<string:filename>', methods=['GET'])
def get_idea_image(filename):
    """Serve idea image files"""
    from flask import send_from_directory
    from app import UPLOAD_FOLDER
    print(UPLOAD_FOLDER, "filename:", filename)
    return send_from_directory(UPLOAD_FOLDER, filename)

# ════════════════════════════════════════════════════════════════════════════
# ✨ CO-DEVELOPER REQUEST ROUTES
# ════════════════════════════════════════════════════════════════════════════

@ideas_bp.route('/<int:idea_id>/collab-requests', methods=['POST'])
@jwt_required()
def request_to_collab(idea_id):
    """Send a co-developer request for an idea"""
    current_user_id = int(get_jwt_identity())

    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)

    if idea.creator_id == current_user_id:
        return error_response('You cannot request to join your own idea', 400)

    from app.models.ideaCollabRequest import IdeaCollabRequest
    from app.models.Enums import JoinRequestStatus

    existing = IdeaCollabRequest.query.filter_by(
        idea_id=idea_id,
        user_id=current_user_id,
        status=JoinRequestStatus.pending
    ).first()
    if existing:
        return error_response('You already have a pending request for this idea', 409)

    data = request.get_json() or {}
    user = User.query.get(current_user_id)

    collab_request = IdeaCollabRequest(
        idea_id=idea_id,
        idea_title=idea.title,
        user_id=current_user_id,
        first_name=user.first_name,
        last_name=user.last_name,
        message=data.get('message', ''),
        role=data.get('role', 'co-developer')
    )

    try:
        db.session.add(collab_request)
        db.session.commit()

        try:
            from app.notifications.helpers import notify_info
            notify_info(
                user_id=idea.creator_id,
                message=f"{user.first_name} {user.last_name} wants to join your idea '{idea.title}' as a co-developer."
            )
        except Exception as e:
            print(f"⚠️ Collab request notification failed: {e}")

        try:
            from app.extensions import socketio
            socketio.emit('new_collab_request', {
                'idea_id': idea_id,
                'request_id': collab_request.id,
                'requester_name': f"{user.first_name} {user.last_name}",
                'role': collab_request.role,
            }, room=f'user_{idea.creator_id}')
        except Exception as e:
            print(f"⚠️ Collab request socket emit failed: {e}")

        return success_response(
            {'collab_request': collab_request.to_dict()},
            'Request sent successfully',
            201
        )
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to send request: {str(e)}', 500)


@ideas_bp.route('/<int:idea_id>/collab-requests', methods=['GET'])
@jwt_required()
def get_collab_requests(idea_id):
    """Get all co-developer requests for an idea (creator only)"""
    current_user_id = int(get_jwt_identity())

    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)

    if idea.creator_id != current_user_id:
        return error_response('Only the idea creator can view requests', 403)

    from app.models.ideaCollabRequest import IdeaCollabRequest
    requests_list = IdeaCollabRequest.query.filter_by(idea_id=idea_id).order_by(
        IdeaCollabRequest.created_at.desc()
    ).all()

    return success_response({
        'collab_requests': [r.to_dict() for r in requests_list]
    })


@ideas_bp.route('/<int:idea_id>/collab-requests/my-status', methods=['GET'])
@jwt_required()
def get_my_collab_status(idea_id):
    """Check the current user's collab request status for an idea"""
    current_user_id = int(get_jwt_identity())

    from app.models.ideaCollabRequest import IdeaCollabRequest
    from app.models.Enums import JoinRequestStatus

    collab_request = IdeaCollabRequest.query.filter_by(
        idea_id=idea_id,
        user_id=current_user_id,
    ).filter(
        IdeaCollabRequest.status.in_([
            JoinRequestStatus.pending,
            JoinRequestStatus.approved,
            JoinRequestStatus.rejected
        ])
    ).order_by(IdeaCollabRequest.created_at.desc()).first()

    return success_response({
        'collab_request': collab_request.to_dict() if collab_request else None
    })


@ideas_bp.route('/collab-requests/<int:request_id>/approve', methods=['POST'])
@jwt_required()
def approve_collab_request(request_id):
    """Approve a co-developer request"""
    current_user_id = int(get_jwt_identity())

    from app.models.ideaCollabRequest import IdeaCollabRequest
    from app.models.Enums import JoinRequestStatus

    collab_request = IdeaCollabRequest.query.get(request_id)
    if not collab_request:
        return error_response('Request not found', 404)

    idea = Idea.query.get(collab_request.idea_id)
    if idea.creator_id != current_user_id:
        return error_response('Only the idea creator can approve requests', 403)

    try:
        collab_request.approve()
        user = User.query.get(collab_request.user_id)
        if user:
            idea.add_team_member(
                name=f"{user.first_name} {user.last_name}",
                position=collab_request.role,
                skills=None
            )
        db.session.commit()

        # ── Recalculate readiness score — collaborator joined ──────────────
        try:
            idea.compute_readiness_score()
        except Exception as e:
            print(f"⚠️ Readiness recalculation failed: {e}")

        try:
            from app.notifications.helpers import notify_info
            notify_info(
                user_id=collab_request.user_id,
                message=f"Your request to join '{idea.title}' as co-developer has been approved! 🎉"
            )
        except Exception as e:
            print(f"⚠️ Approval notification failed: {e}")

        return success_response(
            {'collab_request': collab_request.to_dict()},
            'Request approved successfully'
        )
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to approve request: {str(e)}', 500)


@ideas_bp.route('/collab-requests/<int:request_id>/reject', methods=['POST'])
@jwt_required()
def reject_collab_request(request_id):
    """Reject a co-developer request"""
    current_user_id = int(get_jwt_identity())

    from app.models.ideaCollabRequest import IdeaCollabRequest

    collab_request = IdeaCollabRequest.query.get(request_id)
    if not collab_request:
        return error_response('Request not found', 404)

    idea = Idea.query.get(collab_request.idea_id)
    if idea.creator_id != current_user_id:
        return error_response('Only the idea creator can reject requests', 403)

    try:
        collab_request.reject()
        db.session.commit()

        try:
            from app.notifications.helpers import notify_info
            notify_info(
                user_id=collab_request.user_id,
                message=f"Your request to join '{idea.title}' was not approved at this time."
            )
        except Exception as e:
            print(f"⚠️ Rejection notification failed: {e}")

        return success_response(
            {'collab_request': collab_request.to_dict()},
            'Request rejected'
        )
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to reject request: {str(e)}', 500)


@ideas_bp.route('/collab-requests/<int:request_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_collab_request(request_id):
    """Cancel a co-developer request (by requester)"""
    current_user_id = int(get_jwt_identity())

    from app.models.ideaCollabRequest import IdeaCollabRequest
    from app.models.Enums import JoinRequestStatus

    collab_request = IdeaCollabRequest.query.get(request_id)
    if not collab_request:
        return error_response('Request not found', 404)

    if collab_request.user_id != current_user_id:
        return error_response('You can only cancel your own requests', 403)

    if collab_request.status != JoinRequestStatus.pending:
        return success_response(
            {'collab_request': collab_request.to_dict()},
            'Request already processed'
        )

    try:
        collab_request.cancel()
        db.session.commit()
        return success_response(
            {'collab_request': collab_request.to_dict()},
            'Request cancelled'
        )
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to cancel: {str(e)}', 500)

@ideas_bp.route('/<int:idea_id>/leave', methods=['POST'])
@jwt_required()
def leave_idea_team(idea_id):
    """Leave an idea team (remove yourself as a co-developer)"""
    current_user_id = int(get_jwt_identity())

    from app.models.ideaCollabRequest import IdeaCollabRequest
    from app.models.Enums import JoinRequestStatus
    from app.models.teamMember import TeamMember

    idea = Idea.query.get(idea_id)
    if not idea:
        return error_response('Idea not found', 404)

    if idea.creator_id == current_user_id:
        return error_response('Creators cannot leave their own idea', 400)

    user = User.query.get(current_user_id)

    collab_request = IdeaCollabRequest.query.filter_by(
        idea_id=idea_id,
        user_id=current_user_id,
        status=JoinRequestStatus.approved
    ).first()

    try:
        if collab_request:
            collab_request.status = JoinRequestStatus.cancelled
            collab_request.updated_at = datetime.datetime.utcnow()

        if user:
            full_name = f"{user.first_name} {user.last_name}"
            team_member = TeamMember.query.filter_by(
                idea_id=idea_id,
                name=full_name
            ).first()
            if team_member:
                db.session.delete(team_member)

        db.session.commit()

        try:
            from app.notifications.helpers import notify_info
            notify_info(
                user_id=idea.creator_id,
                message=f"{user.first_name} {user.last_name} has left your idea '{idea.title}'."
            )
        except Exception as e:
            print(f"⚠️ Leave notification failed: {e}")

        return success_response({}, 'You have left the team')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to leave team: {str(e)}', 500)