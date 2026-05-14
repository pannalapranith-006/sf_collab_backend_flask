from flask import Blueprint, request, jsonify
from app.models.joinRequest import JoinRequest
from app.extensions import db
from app.utils.helper import error_response, success_response, paginate
from app.models.startUpMember import StartupMember
from flask_jwt_extended import jwt_required, get_jwt_identity
join_requests_bp = Blueprint('join_requests', __name__)

@join_requests_bp.route('', methods=['GET'])
@jwt_required()
def get_join_requests():
    """Get all join requests for a user with filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    startup_id = request.args.get('startup_id', type=int)
    search = request.args.get('search', type=str)
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status', type=str)

    if not user_id:
        user_id = get_jwt_identity()

    query = JoinRequest.query.filter(JoinRequest.user_id == user_id)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                JoinRequest.first_name.ilike(search_pattern),
                JoinRequest.last_name.ilike(search_pattern),
                JoinRequest.startup_name.ilike(search_pattern)
            )
        )
    if startup_id:
        query = query.filter(JoinRequest.startup_id == startup_id)
    if status:
        from app.models.Enums import JoinRequestStatus
        query = query.filter(JoinRequest.status == JoinRequestStatus(status))
    
    result = paginate(query.order_by(JoinRequest.created_at.desc()), page, per_page)
    
    return success_response({
        'join_requests': [request.to_dict() for request in result['items']],
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
            'pages': result['pages']
        }
    })

@join_requests_bp.route('/<int:request_id>', methods=['GET'])
@jwt_required()
def get_join_request(request_id):
    """Get single join request by ID"""
    join_request = JoinRequest.query.get(request_id)
    if not join_request:
        return error_response('Join request not found', 404)
    
    return success_response({'join_request': join_request.to_dict()})

@join_requests_bp.route('', methods=['POST'])
@jwt_required()
def create_join_request():
    """Create new join request"""
    data = request.get_json()
    
    required_fields = ['startup_id', 'user_id', 'first_name', 'last_name']
    if not all(field in data for field in required_fields):
        return error_response('Missing required fields: startup_id, user_id, first_name, last_name')
    
    # Check if pending request already exists
    existing = JoinRequest.query.filter_by(
        startup_id=data['startup_id'],
        user_id=data['user_id'],
        status='pending'
    ).first()
    
    if existing:
        return error_response('You already have a pending request for this startup', 409)
    
    try:
        # Get startup name
        from app.models.startup import Startup
        startup = Startup.query.get(data['startup_id'])
        if not startup:
            return error_response('Startup not found', 404)
        
        join_request = JoinRequest(
            startup_id=data['startup_id'],
            startup_name=startup.name,
            user_id=data['user_id'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            message=data.get('message'),
            role=data.get('role', 'member')
        )
        
        db.session.add(join_request)
        db.session.commit()
        try:
            # Notify user about bulk creation
            from app.notifications.helpers import notify_info
            current_user_id = get_jwt_identity()
            notify_info(
                user_id=current_user_id,
                message=f"Join request submitted successfully for startup {startup.name}."
            )
            notify_info(
                user_id=startup.creator_id,
                message=f"New join request submitted for your startup {startup.name}."
            )
        except Exception as e:
            print(f"⚠️ Bulk event notification failed: {e}")
        return success_response({
            'join_request': join_request.to_dict()
        }, 'Join request submitted successfully', 201)
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to create join request: {str(e)}', 500)

@join_requests_bp.route('/<int:request_id>/approve', methods=['POST'])
@jwt_required()
def approve_join_request(request_id):
    """Approve join request"""
    join_request = JoinRequest.query.get(request_id)
    if not join_request:
        return error_response('Join request not found', 404)
    
    if join_request.status != 'pending':
        return error_response('Join request is not pending', 400)
    
    try:
        member = join_request.approve()

        # ── If this join request is for an idea (vision), recalculate readiness
        try:
            from app.models.idea import Idea
            if hasattr(join_request, 'idea_id') and join_request.idea_id:
                idea = Idea.query.get(join_request.idea_id)
                if idea:
                    idea.compute_readiness_score()
        except Exception as e:
            print(f"⚠️ Readiness recalculation on join approval failed: {e}")

        return success_response({
            'join_request': join_request.to_dict(),
            'new_member': member.to_dict() if hasattr(member, 'to_dict') else {
                'startup_id': member.startup_id,
                'user_id': member.user_id,
                'role': member.role
            }
        }, 'Join request approved successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to approve join request: {str(e)}', 500)

@join_requests_bp.route('/<int:request_id>/reject', methods=['POST'])
@jwt_required()
def reject_join_request(request_id):
    """Reject join request"""
    join_request = JoinRequest.query.get(request_id)
    if not join_request:
        return error_response('Join request not found', 404)
    
    if join_request.status != 'pending':
        return error_response('Join request is not pending', 400)
    
    try:
        join_request.reject()
        return success_response({
            'join_request': join_request.to_dict()
        }, 'Join request rejected successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to reject join request: {str(e)}', 500)

@join_requests_bp.route('/<int:request_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_join_request(request_id):
    """Cancel join request (by user)"""
    join_request = JoinRequest.query.get(request_id)
    if not join_request:
        return error_response('Join request not found', 404)
    
    if join_request.status != 'pending':
        return error_response('Only pending requests can be cancelled', 400)
    
    try:
        join_request.cancel()
        return success_response({
            'join_request': join_request.to_dict()
        }, 'Join request cancelled successfully')
    except Exception as e:
        return error_response(f'Failed to cancel join request: {str(e)}', 500)

@join_requests_bp.route('/<int:request_id>', methods=['DELETE'])
@jwt_required()
def delete_join_request(request_id):
    """Delete join request"""
    join_request = JoinRequest.query.get(request_id)
    if not join_request:
        return error_response('Join request not found', 404)
    
    try:
        db.session.delete(join_request)
        db.session.commit()
        return success_response(message='Join request deleted successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to delete join request: {str(e)}', 500)