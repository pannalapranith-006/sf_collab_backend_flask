from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.contributionIdeas import ContributionIdea
from app.models.user import User
# app.models.activity (old audit log) removed — no workspace_id context here
from app.utils.helper import success_response, error_response, paginate, utc_now_str
from app.models.userRole import UserRole

bp = Blueprint('contribution_ideas', __name__)


# ========================== CREATE IDEA ==========================
@bp.route('', methods=['POST'])
@jwt_required()
def create_idea():
    """Create a new contribution idea"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        data    = request.get_json()

        user = User.query.get(user_id)
        if not user:
            return error_response('User not found', status=404)

        required_fields = ['title', 'description', 'impact', 'area', 'status']
        if not all(field in data for field in required_fields):
            return error_response('Missing required fields: title, description, impact, area, status', status=400)

        valid_impacts = ['small', 'medium', 'large']
        if data.get('impact') not in valid_impacts:
            return error_response(f'Invalid impact. Must be one of: {", ".join(valid_impacts)}', status=400)

        idea = ContributionIdea(
            title=data.get('title'),
            description=data.get('description'),
            impact=data.get('impact'),
            area=data.get('area'),
            status=data.get('status'),
            user_id=user_id,
        )

        db.session.add(idea)
        db.session.commit()

        print(f"[activity] contribution_idea_created | user_id={user_id} | idea={idea.title}")
        # FIX: Activity.log removed — no workspace_id context here
        print(f"[contribution_ideas] contribution_idea_created: user_id={user_id} title={idea.title!r}")

        return success_response(
            data=idea.to_dict(),
            message='Contribution idea created successfully',
            status=201,
        )

    except Exception as e:
        db.session.rollback()
        print(f"Create idea error: {str(e)}")
        return error_response('Failed to create contribution idea', status=500)


# ========================== GET ALL IDEAS ==========================
@bp.route('', methods=['GET'])
@jwt_required()
def get_ideas():
    """Get all contribution ideas with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        area = request.args.get('area')
        impact = request.args.get('impact')
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        user_roles = UserRole.query.filter_by(user_id=user_id).all()

        if not any(role.is_admin for role in user_roles) and not user.is_admin():
            return error_response('Unauthorized to view ideas', status=403)

        query = ContributionIdea.query

        if area:
            query = query.filter_by(area=area)
        if impact:
            query = query.filter_by(impact=impact)

        query     = query.order_by(ContributionIdea.created_at.desc())
        paginated = paginate(query, page=page, per_page=per_page)

        return success_response(
            data={
                'ideas': [idea.to_dict() for idea in paginated['items']],
                'pagination': {
                    'page':     paginated['page'],
                    'per_page': paginated['per_page'],
                    'total':    paginated['total'],
                    'pages':    paginated['pages'],
                },
            },
            message='Ideas retrieved successfully',
        )

    except Exception as e:
        print(f"Get ideas error: {str(e)}")
        return error_response('Failed to fetch ideas', status=500)


# ========================== GET IDEA BY ID ==========================
@bp.route('/<int:idea_id>', methods=['GET'])
def get_idea(idea_id):
    """Get a specific contribution idea"""
    try:
        idea = ContributionIdea.query.get(idea_id)
        if not idea:
            return error_response('Idea not found', status=404)

        return success_response(
            data=idea.to_dict(include_comments=True),
            message='Idea retrieved successfully',
        )

    except Exception as e:
        print(f"Get idea error: {str(e)}")
        return error_response('Failed to fetch idea', status=500)


# ========================== UPDATE IDEA ==========================
@bp.route('/<int:idea_id>', methods=['PUT'])
@jwt_required()
def update_idea(idea_id):
    """Update a contribution idea"""
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json()

        idea = ContributionIdea.query.get(idea_id)
        if not idea:
            return error_response('Idea not found', status=404)

        if idea.user_id != user_id:
            return error_response('Unauthorized to update this idea', status=403)

        if 'title' in data:
            idea.title = data.get('title')
        if 'description' in data:
            idea.description = data.get('description')
        if 'impact' in data:
            valid_impacts = ['small', 'medium', 'large']
            if data.get('impact') not in valid_impacts:
                return error_response(f'Invalid impact. Must be one of: {", ".join(valid_impacts)}', status=400)
            idea.impact = data.get('impact')
        if 'status' in data:
            valid_statuses = ['pending', 'approved', 'rejected']
            if data.get('status') not in valid_statuses:
                return error_response(f'Invalid status. Must be one of: {", ".join(valid_statuses)}', status=400)
            idea.status = data.get('status')
        if 'area' in data:
            idea.area = data.get('area')

        db.session.commit()

        # FIX: Activity.log removed — no workspace_id context here
        print(f"[contribution_ideas] contribution_idea_updated: user_id={user_id} title={idea.title!r}")

        return success_response(
            data=idea.to_dict(),
            message='Idea updated successfully',
        )

    except Exception as e:
        db.session.rollback()
        print(f"Update idea error: {str(e)}")
        return error_response('Failed to update idea', status=500)


# ========================== DELETE IDEA ==========================
@bp.route('/<int:idea_id>', methods=['DELETE'])
@jwt_required()
def delete_idea(idea_id):
    """Delete a contribution idea"""
    try:
        user_id = int(get_jwt_identity())

        idea = ContributionIdea.query.get(idea_id)
        if not idea:
            return error_response('Idea not found', status=404)

        if idea.user_id != user_id:
            return error_response('Unauthorized to delete this idea', status=403)

        title = idea.title
        db.session.delete(idea)
        db.session.commit()

        # FIX: Activity.log removed — no workspace_id context here
        print(f"[contribution_ideas] contribution_idea_deleted: user_id={user_id} title={title!r}")

        return success_response(message='Idea deleted successfully')

    except Exception as e:
        db.session.rollback()
        print(f"Delete idea error: {str(e)}")
        return error_response('Failed to delete idea', status=500)


# ========================== GET USER IDEAS ==========================
@bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_ideas(user_id):
    """Get all ideas from a specific user"""
    try:
        page     = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        user = User.query.get(user_id)
        if not user:
            return error_response('User not found', status=404)

        query     = ContributionIdea.query.filter_by(user_id=user_id).order_by(
            ContributionIdea.created_at.desc()
        )
        paginated = paginate(query, page=page, per_page=per_page)

        return success_response(
            data={
                'ideas': [idea.to_dict() for idea in paginated['items']],
                'pagination': {
                    'page':     paginated['page'],
                    'per_page': paginated['per_page'],
                    'total':    paginated['total'],
                    'pages':    paginated['pages'],
                },
            },
            message='User ideas retrieved successfully',
        )

    except Exception as e:
        print(f"Get user ideas error: {str(e)}")
        return error_response('Failed to fetch user ideas', status=500)