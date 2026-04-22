"""
Profile Management Routes

Handles:
- POST /api/auth/setup-profile - Basic profile setup (ProfileSetup)
- POST /api/users/complete-profile - Multi-role profile completion (MultiRoleProfileForm)
- GET /api/users/profile - Retrieve user's complete profile
- PUT /api/users/profile - Update user profile (partial updates)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.extensions import db
from app.utils.helper import error_response, success_response
from werkzeug.utils import secure_filename
import os
from datetime import datetime

profile_bp = Blueprint('profiles', __name__, url_prefix='/api')

# Upload configurations
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
AVATAR_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'user_avatars')
os.makedirs(AVATAR_UPLOAD_FOLDER, exist_ok=True)

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_avatar(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


def validate_file_size(file, max_size=MAX_AVATAR_SIZE):
    """Validate file size"""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size <= max_size


def validate_basic_profile(data):
    """Validate basic profile fields"""
    errors = {}
    
    if not data.get('firstName') or not data.get('firstName').strip():
        errors['firstName'] = 'First name is required'
    
    if not data.get('lastName') or not data.get('lastName').strip():
        errors['lastName'] = 'Last name is required'
    
    if not data.get('country') or not data.get('country').strip():
        errors['country'] = 'Country is required'
    
    return errors


def validate_founder_profile(data):
    """Validate founder profile required fields"""
    errors = {}
    
    if not data.get('startupName') or not data.get('startupName').strip():
        errors['startupName'] = 'Startup name is required'
    
    if not data.get('description') or not data.get('description').strip():
        errors['description'] = 'Description is required'
    
    if not data.get('industry') or not data.get('industry').strip():
        errors['industry'] = 'Industry is required'
    
    if not data.get('stage') or not data.get('stage').strip():
        errors['stage'] = 'Stage is required'
    
    return errors


def validate_builder_profile(data):
    """Validate builder profile required fields"""
    errors = {}
    
    skills = data.get('skills', [])
    if not skills or len(skills) == 0:
        errors['skills'] = 'At least one skill is required'
    
    if not data.get('experienceLevel') or not data.get('experienceLevel').strip():
        errors['experienceLevel'] = 'Experience level is required'
    
    if not data.get('availability') or not data.get('availability').strip():
        errors['availability'] = 'Availability is required'
    
    return errors


def validate_influencer_profile(data):
    """Validate influencer profile required fields"""
    errors = {}
    
    platforms = data.get('platforms', [])
    if not platforms or len(platforms) == 0:
        errors['platforms'] = 'At least one platform is required'
    
    collabTypes = data.get('collabTypes', [])
    if not collabTypes or len(collabTypes) == 0:
        errors['collabTypes'] = 'At least one collaboration type is required'
    
    if not data.get('audienceDescription') or not data.get('audienceDescription').strip():
        errors['audienceDescription'] = 'Audience description is required'
    
    return errors


def validate_investor_profile(data):
    """Validate investor profile required fields"""
    errors = {}
    
    if not data.get('investorType') or not data.get('investorType').strip():
        errors['investorType'] = 'Investor type is required'
    
    industriesInvested = data.get('industriesInvested', [])
    if not industriesInvested or len(industriesInvested) == 0:
        errors['industriesInvested'] = 'At least one industry is required'
    
    return errors


# ============= ENDPOINT 1: Setup Basic Profile =============
@profile_bp.route('/auth/setup-profile', methods=['POST'])
@jwt_required()
def setup_profile():
    """
    Complete basic profile setup (Step 1 - ProfileSetup)
    
    Accepts multipart/form-data for file upload
    
    Form Fields:
    - firstName (required)
    - lastName (required)
    - company (optional)
    - country (required)
    - city (optional)
    - timezone (optional)
    - language (optional)
    - bio (optional)
    - profileImage (optional, file)
    
    Returns: Updated user object
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', 404)
        
        # Get form data
        data = request.form.to_dict()
        
        # Validate required fields
        validation_errors = validate_basic_profile(data)
        if validation_errors:
            return error_response('Validation failed', 422, validation_errors)
        
        # Update basic profile fields
        user.first_name = data.get('firstName').strip()
        user.last_name = data.get('lastName').strip()
        user.profile_company = data.get('company', '').strip() or None
        user.profile_country = data.get('country').strip()
        user.profile_city = data.get('city', '').strip() or None
        user.profile_timezone = data.get('timezone', 'UTC').strip()
        user.pref_language = data.get('language', 'English').strip()
        user.profile_bio = data.get('bio', '').strip() or None
        
        # Handle profile image upload
        if 'profileImage' in request.files:
            file = request.files['profileImage']
            
            if file and file.filename:
                # Validate file
                if not allowed_avatar(file.filename):
                    return error_response('Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WebP', 400)
                
                if not validate_file_size(file, MAX_AVATAR_SIZE):
                    return error_response('File size exceeds 5MB limit', 413)
                
                # Save file with secure name
                filename = secure_filename(f"profile_{user_id}_{datetime.utcnow().timestamp()}.{file.filename.rsplit('.', 1)[1].lower()}")
                filepath = os.path.join(AVATAR_UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                # Update profile picture URL
                user.profile_picture = f'/uploads/user_avatars/{filename}'
        
        # Mark basic profile as completed
        user.profile_setup_completed = True
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response(
            user.to_dict(),
            'Profile setup completed successfully',
            200
        )
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to setup profile: {str(e)}', 500)


# ============= ENDPOINT 2: Complete Multi-Role Profile =============
@profile_bp.route('/users/complete-profile', methods=['POST'])
@jwt_required()
def complete_profile():
    """
    Complete multi-role profile (Step 2 - MultiRoleProfileForm)
    
    Request body (JSON):
    {
        "roles": ["founder", "builder"],
        "founderProfile": { ... },
        "builderProfile": { ... },
        "influencerProfile": { ... },
        "investorProfile": { ... }
    }
    
    Returns: Updated user object with all role data
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', 404)
        
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', 400)
        
        # Validate roles array
        roles = data.get('roles', [])
        if not roles or len(roles) == 0:
            return error_response('At least one role must be selected', 422)
        
        # Validate role values
        valid_roles = ['founder', 'builder', 'influencer', 'investor']
        invalid_roles = [r for r in roles if r not in valid_roles]
        if invalid_roles:
            return error_response(f'Invalid roles: {", ".join(invalid_roles)}', 422)
        
        # Validate each role's profile data
        validation_errors = {}
        
        if 'founder' in roles:
            founder_profile = data.get('founderProfile', {})
            errors = validate_founder_profile(founder_profile)
            if errors:
                validation_errors['founderProfile'] = errors
        
        if 'builder' in roles:
            builder_profile = data.get('builderProfile', {})
            errors = validate_builder_profile(builder_profile)
            if errors:
                validation_errors['builderProfile'] = errors
        
        if 'influencer' in roles:
            influencer_profile = data.get('influencerProfile', {})
            errors = validate_influencer_profile(influencer_profile)
            if errors:
                validation_errors['influencerProfile'] = errors
        
        if 'investor' in roles:
            investor_profile = data.get('investorProfile', {})
            errors = validate_investor_profile(investor_profile)
            if errors:
                validation_errors['investorProfile'] = errors
        
        if validation_errors:
            return error_response('Validation failed', 422, validation_errors)
        
        # Store roles and profile data
        user.roles = roles
        
        # Store each role profile if provided
        if 'founderProfile' in data:
            user.founder_profile = data.get('founderProfile', {})
        
        if 'builderProfile' in data:
            user.builder_profile = data.get('builderProfile', {})
        
        if 'influencerProfile' in data:
            user.influencer_profile = data.get('influencerProfile', {})
        
        if 'investorProfile' in data:
            user.investor_profile = data.get('investorProfile', {})
        
        # Mark role profile as completed
        user.role_profile_completed = True
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response(
            user.to_dict(),
            'Multi-role profile saved successfully',
            200
        )
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to save profile: {str(e)}', 500)


# ============= ENDPOINT 3: Get User Profile =============
@profile_bp.route('/users/profile', methods=['GET'])
@jwt_required()
def get_user_profile():
    """
    Get current user's complete profile
    
    Returns: Full user object including all role profiles
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', 404)
        
        # Ensure wallet exists
        from app.services.wallet_service import WalletService
        WalletService.get_wallet(user.id)
        
        return success_response(user.to_dict(), 'Profile retrieved successfully', 200)
        
    except Exception as e:
        return error_response(f'Failed to retrieve profile: {str(e)}', 500)


# ============= ENDPOINT 5: Get Rich Profile Data (for ProfileStats / Profile page) =============
@profile_bp.route('/users/<int:user_id>/profile', methods=['GET'])
@jwt_required()
def get_rich_user_profile(user_id):
    """
    Get a user's complete profile including all stats, memberships, ideas,
    achievements, tasks, and activity data needed by ProfileStats.jsx and Profile.jsx.

    Returns a superset of user.to_dict() with all relational data joined in.
    """
    try:
        current_user_id = int(get_jwt_identity())
        user = User.query.get(user_id)

        if not user:
            return error_response('User not found', 404)

        is_own_profile = current_user_id == user_id

        # ── Base user dict ────────────────────────────────────────────────
        data = user.to_dict(
            include_statistics=True,
            public=not is_own_profile
        )

        # ── Founded startups ─────────────────────────────────────────────
        try:
            from app.models.startup import Startup
            founded = Startup.query.filter_by(
                creator_id=user_id, status='active'
            ).all()
            data['foundedStartups'] = [s.to_dict() for s in founded]
        except Exception:
            data['foundedStartups'] = []

        # ── Startup memberships (non-founder) ────────────────────────────
        try:
            from app.models.startUpMember import StartupMember
            memberships = StartupMember.query.filter_by(
                user_id=user_id, is_active=True
            ).all()
            data['startupMemberships'] = [
                {
                    'id': m.id,
                    'role': m.role.value if hasattr(m.role, 'value') else m.role,
                    'joinedAt': m.joined_at.isoformat() if m.joined_at else None,
                    'startup': m.member_startup.to_dict() if m.member_startup else None
                }
                for m in memberships
            ]
        except Exception:
            data['startupMemberships'] = []

        # ── Ideas ────────────────────────────────────────────────────────
        try:
            ideas = user.ideas.all()
            data['ideas'] = [
                {
                    'id': i.id,
                    'title': i.title,
                    'description': i.description,
                    'createdAt': i.created_at.isoformat() if i.created_at else None
                }
                for i in ideas
            ]
        except Exception:
            data['ideas'] = []

        # ── Achievements ─────────────────────────────────────────────────
        try:
            achievements = user.user_achievements.filter_by(is_completed=True).all()
            data['achievements'] = [
                {
                    'id': a.id,
                    'unlocked_at': a.unlocked_at.isoformat() if hasattr(a, 'unlocked_at') and a.unlocked_at else None,
                    'achievement': a.achievement.to_dict() if hasattr(a, 'achievement') and a.achievement else None
                }
                for a in achievements
            ]
        except Exception:
            data['achievements'] = []

        # ── Assigned tasks ───────────────────────────────────────────────
        try:
            assigned = user.assigned_tasks.all()
            completed = [t for t in assigned if t.status == 'completed']
            pending   = [t for t in assigned if t.status != 'completed']
            data['assignedTasks'] = {
                'total':     len(assigned),
                'completed': len(completed),
                'pending':   len(pending)
            }
        except Exception:
            data['assignedTasks'] = {'total': 0, 'completed': 0, 'pending': 0}

        # ── Knowledge posts ──────────────────────────────────────────────
        try:
            kposts = user.knowledge_posts.all()
            data['knowledgePosts'] = [
                {
                    'id': k.id,
                    'title': getattr(k, 'title', ''),
                    'titleDescription': getattr(k, 'title_description', ''),
                    'views': getattr(k, 'views', 0),
                    'likes': getattr(k, 'likes', 0),
                    'downloads': getattr(k, 'downloads', 0),
                    'createdAt': k.created_at.isoformat() if k.created_at else None
                }
                for k in kposts
            ]
        except Exception:
            data['knowledgePosts'] = []

        # ── Posts ────────────────────────────────────────────────────────
        try:
            posts = user.posts.all() if hasattr(user, 'posts') else []
            data['posts'] = [
                {
                    'id': p.id,
                    'content': getattr(p, 'content', ''),
                    'likes': getattr(p, 'likes', 0),
                    'commentsCount': getattr(p, 'comments_count', 0),
                    'shares': getattr(p, 'shares', 0),
                    'createdAt': p.created_at.isoformat() if p.created_at else None
                }
                for p in posts
            ]
        except Exception:
            data['posts'] = []

        # ── Friends count ────────────────────────────────────────────────
        try:
            from app.models.friendRequest import FriendRequest
            accepted_friends = FriendRequest.query.filter(
                FriendRequest.status == 'accepted',
                (FriendRequest.sender_id == user_id) |
                (FriendRequest.receiver_id == user_id)
            ).count()
            data['friendsCount'] = accepted_friends
        except Exception:
            data['friendsCount'] = 0

        # ── Transactions (own profile only) ──────────────────────────────
        if is_own_profile:
            try:
                txs = user.transactions.all() if hasattr(user, 'transactions') else []
                data['transactions'] = [
                    {
                        'id': t.id,
                        'type': getattr(t, 'type', 'payment'),
                        'amount': getattr(t, 'amount', 0),
                        'currency': getattr(t, 'currency', 'usd'),
                        'status': getattr(t, 'status', 'completed'),
                        'donation_message': getattr(t, 'donation_message', None),
                        'created_at': t.created_at.isoformat() if t.created_at else None
                    }
                    for t in txs
                ]
            except Exception:
                data['transactions'] = []
        else:
            data['transactions'] = []

        # ── Wallet / credits (own profile only) ──────────────────────────
        if not is_own_profile:
            data.pop('credits', None)
            data.pop('wallet', None)

        return success_response(data, 'Profile retrieved successfully', 200)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return error_response(f'Failed to retrieve profile: {str(e)}', 500)

@profile_bp.route('/users/profile', methods=['PUT', 'PATCH'])
@jwt_required()
def update_user_profile():
    """
    Update user profile (partial updates allowed)
    
    Request body (JSON):
    Any combination of fields from setup-profile and complete-profile endpoints
    
    Returns: Updated user object
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', 404)
        
        data = request.get_json()
        
        if not data:
            return error_response('Request body is required', 400)
        
        # Update basic profile fields if provided
        if 'firstName' in data and data['firstName']:
            user.first_name = data['firstName'].strip()
        
        if 'lastName' in data and data['lastName']:
            user.last_name = data['lastName'].strip()
        
        if 'company' in data:
            user.profile_company = data['company'].strip() or None
        
        if 'country' in data and data['country']:
            user.profile_country = data['country'].strip()
        
        if 'city' in data:
            user.profile_city = data['city'].strip() or None
        
        if 'timezone' in data:
            user.profile_timezone = data['timezone'].strip()
        
        if 'language' in data:
            user.pref_language = data['language'].strip()
        
        if 'bio' in data:
            user.profile_bio = data['bio'].strip() or None
        
        # Update roles if provided
        if 'roles' in data:
            roles = data.get('roles', [])
            if roles and len(roles) > 0:
                valid_roles = ['founder', 'builder', 'influencer', 'investor']
                invalid_roles = [r for r in roles if r not in valid_roles]
                if invalid_roles:
                    return error_response(f'Invalid roles: {", ".join(invalid_roles)}', 422)
                user.roles = roles
        
        # Update role profiles if provided
        if 'founderProfile' in data:
            user.founder_profile = data['founderProfile']
        
        if 'builderProfile' in data:
            user.builder_profile = data['builderProfile']
        
        if 'influencerProfile' in data:
            user.influencer_profile = data['influencerProfile']
        
        if 'investorProfile' in data:
            user.investor_profile = data['investorProfile']
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return success_response(user.to_dict(), 'Profile updated successfully', 200)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to update profile: {str(e)}', 500)