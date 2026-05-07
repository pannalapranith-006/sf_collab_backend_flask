from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from app.models.startup import Startup
from app.models.startup_document import StartupDocument
from app.models.startUpMember import StartupMember
from app.models.user import User
from app.models.joinRequest import JoinRequest
from app.models.Enums import JoinRequestStatus, UserRoles
from app.extensions import db
from app.utils.helper import error_response, success_response, paginate
from app.models.userRole import UserRole
from app.notifications.helpers import notify_access_request_pending
from app.utils.plans_utils import can_create_project, can_add_collaborator, can_upload_file
from app.models.startUpMember import StartupMember
from app.models.chatConversation import ChatConversation
from app.models.startupInvitation import StartupInvitation, InvitationStatus
from app.models.waitlist import Waitlist
import os 
from sqlalchemy import func
from io import BytesIO
import json
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import uuid
import shutil
from sqlalchemy.orm.attributes import flag_modified
from app.utils.startup_permissions import (
    get_current_user_startup_role,
    can_view_full_details,
    can_manage_documents,
    can_manage_members,
    can_edit_startup_core_info
)
from app.notifications.helpers import (
    notify_startup_created,
    notify_added_to_startup,
    notify_removed_from_startup,
    notify_startup_role_assigned,
    notify_startup_milestone,
    notify_access_granted,
    notify_info
)


startups_bp = Blueprint('startups', __name__)

# Upload configurations
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'startups')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'md', 'xlsx', 'pptx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def has_startup_document_visibility_access(user_id, startup_document):
    """Check if user has visibility access to startup document based on visibility settings"""
    # Owner always has access
    print("Has startup document visibility access check:", user_id, startup_document.parent_startup.creator_id)
    print("Type checks:", type(user_id), type(startup_document.parent_startup.creator_id))
    if startup_document.parent_startup and int(startup_document.parent_startup.creator_id) == int(user_id):
        return True
    # Check visibility settings
    if startup_document.visible_by == 'private':
        return False
    
    if startup_document.visible_by == 'team' and startup_document.parent_startup.id:
        # Check if user is part of the startup team
        return is_user_on_startup_team(user_id, startup_document.parent_startup.id)
    
    if startup_document.visible_by == 'all' or startup_document.visible_by == 'public':
        return True
    
    return False
def is_user_on_startup_team(user_id, startup_id):
    """Check if user is a member of the startup team"""
    membership = StartupMember.query.filter_by(
        user_id=user_id,
        startup_id=startup_id
    ).first()
    return membership is not None
def validate_file_size(file, max_size=MAX_FILE_SIZE):
    """Validate file size"""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size <= max_size

def generate_unique_filename(original_filename):
    """Generate unique filename to avoid conflicts"""
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    random_str = os.urandom(4).hex()
    file_extension = os.path.splitext(original_filename)[1]
    return f"{timestamp}_{random_str}{file_extension}"

def get_startup_member_ids(startup_id, exclude_user_id=None):
    """Get list of user IDs who are members of a startup"""
    from app.models.startUpMember import StartupMember
    members = StartupMember.query.filter_by(startup_id=startup_id, is_active=True).all()
    user_ids = [m.user_id for m in members if m.user_id]
    if exclude_user_id:
        user_ids = [uid for uid in user_ids if uid != exclude_user_id]
    return user_ids
def parse_json_field(value, default):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if value is not None else default

def calculate_total_positions(roles_data, fallback_positions=0):
    total = 0
    if roles_data:
        for _, role in roles_data.items():
            if isinstance(role, dict) and 'positionsNumber' in role:
                total += int(role.get('positionsNumber', 0))
            else:
                total += 1
    return total if total > 0 else int(fallback_positions)

#! FOR EVERYONE (Public - no auth required)
@startups_bp.route('', methods=['GET'])
@jwt_required()
def get_startups():
    """Get all startups with filtering, or user's startups if requested"""
    try:
        current_user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        industry = request.args.get('industry', type=str)
        stage = request.args.get('stage', type=str)
        search = request.args.get('search', type=str)
        my_startups = request.args.get('my_startups', 'false').lower() == 'true'
        min_funding = request.args.get('min_funding', type=float)
        max_funding = request.args.get('max_funding', type=float)
        builder = request.args.get('builder', 'false').lower() == 'true'
        sort_by = request.args.get('sort_by', 'date', type=str)  # 'date', 'views', 'rating'
        query = Startup.query.filter(Startup.status != 'deleted')  # Exclude deleted startups

        if builder:
            print("Builder filter applied - showing startups where user is a member but not creator")
            query = query.join(StartupMember, StartupMember.startup_id == Startup.id).filter(
                StartupMember.user_id == current_user_id,
                StartupMember.is_active == True,
                Startup.creator_id != current_user_id
            )

        # Apply sorting based on sort_by parameter
        if sort_by == 'views':
            query = query.order_by(Startup.views.desc())
        elif sort_by == 'rating':
            from app.models.startup_rating import StartupRating
            avg_rating_subquery = db.session.query(
                StartupRating.startup_id,
                func.avg(StartupRating.rating).label('avg_rating')
            ).group_by(StartupRating.startup_id).subquery()

            query = query.outerjoin(avg_rating_subquery, Startup.id == avg_rating_subquery.c.startup_id).order_by(
                func.coalesce(avg_rating_subquery.c.avg_rating, 0).desc()
            )
        else:  # Default to 'date'
            query = query.order_by(Startup.created_at.desc())

        # Apply filters
        if industry:
            query = query.filter(Startup.industry.ilike(f'%{industry}%'))
        if stage:
            query = query.filter(Startup.stage == stage)
        if search:
            query = query.filter(
                (Startup.name.ilike(f'%{search}%')) |
                (Startup.description.ilike(f'%{search}%'))
            )
        if min_funding is not None:
            query = query.filter(Startup.funding_amount >= min_funding)
        if max_funding is not None:
            query = query.filter(Startup.funding_amount <= max_funding)
        if my_startups:
            query = query.filter(Startup.creator_id == current_user_id)

        result = paginate(query, page, per_page)

        return success_response({
            'startups': [startup.to_dict() for startup in result['items']],
            'pagination': {
                'page': result['page'],
                'per_page': result['per_page'],
                'total': result['total'],
                'pages': result['pages']
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"🔥 GET_STARTUPS ERROR: {type(e).__name__}: {e}")
        db.session.rollback()
        return error_response(f'Failed to load startups: {str(e)}', 500)

@startups_bp.route('/top', methods=['GET'])
def get_top_startups():
    """Get top startups by views"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 3, type=int)
    
    query = Startup.query.filter(Startup.views > 0)
    
    # Order by views descending
    query = query.order_by(Startup.views.desc())
    
    result = paginate(query, page, per_page)
    
    return success_response({
        'startups': [startup.to_dict() for startup in result['items']],
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
            'pages': result['pages']
        }
    })
#! GET SINGLE STARTUP (Public - no auth required)
@startups_bp.route('/<int:startup_id>', methods=['GET'])
def get_startup(startup_id):
    current_user_id = request.args.get('user_id', type=int)  # Optional user_id for access level determination
    startup = Startup.query.get_or_404(startup_id)
    if startup.status == 'deleted':
        return error_response('Startup not found', 404)
    if current_user_id:
        startup.increment_views(current_user_id)

    # get_current_user_startup_role calls get_jwt_identity() internally.
    # This route has no @jwt_required, so we must set up the JWT context
    # manually as optional — no token = identity stays None, no crash.
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        pass

    role = get_current_user_startup_role(startup_id)

    if role == 'none' or not role:
        # Very limited view for normal logged-in users
        data = {
            'id': startup.id,
            'name': startup.name,
            'industry': startup.industry,
            'stage': startup._enum_to_value(startup.stage),
            'description': (startup.description or '')[:350] + '...',
            'logo_url': startup.logo_url,
            'banner_url': startup.banner_url,
            'member_count': startup.member_count,
            'views': startup.views,
            'average_rating': startup._get_average_rating(),
            'rating_count': startup._get_rating_count(),
            'createdAt': startup.created_at.isoformat() if startup.created_at else None,
            'access_level': 'public_limited',
            'roles': startup.roles,
            'tech_stack': startup.tech_stack
        }
    else:
        # Full view for anyone related to the startup
        data = startup.to_dict()
        data['access_level'] = role

    return success_response({'startup': data})

#! REGISTER NEW STARTUP
@startups_bp.route('/register', methods=['POST'])
@jwt_required()
def register_startup():
    """Register new startup with file uploads to file system"""
    current_user_id = get_jwt_identity()
    startup = Startup()
    startup_upload_dir = None
    
    try:
        # Check if request has form data
        if not request.form:
            return error_response('Form data required', 400)
        
        data = request.form
        files = request.files
        
        required_fields = ['name', 'industry']
        if not all(field in data for field in required_fields):
            return error_response('Missing required fields')
        
        # Check if startup name already exists
        if Startup.query.filter_by(name=data['name']).first():
            return error_response('Startup name already exists', 409)

        # Get current user info
        try:
            current_user = User.query.get(current_user_id)
            if not current_user:
                return error_response('User not found', 404)
            if not current_user.is_email_verified:
                return error_response('User email not verified', 403)
            if current_user.is_banned():
                return error_response('User is banned', 403)
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] User validation error: {str(e)}")
            return error_response(f'User validation failed: {str(e)}', 500)

        # Parse roles data
        try:
            roles_data = data.get('roles', {})
            if isinstance(roles_data, str):
                try:
                    roles_data = json.loads(roles_data)
                except json.JSONDecodeError:
                    roles_data = {}
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] Roles parsing error: {str(e)}")
            roles_data = {}
        
        # Parse tech stack if provided
        try:
            tech_stack_data = data.get('tech_stack', [])
            if isinstance(tech_stack_data, str):
                try:
                    tech_stack_data = json.loads(tech_stack_data)
                except json.JSONDecodeError:
                    tech_stack_data = []
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] Tech stack parsing error: {str(e)}")
            tech_stack_data = []
        
        # Calculate total positions from roles data
        try:
            total_positions = calculate_total_positions(roles_data, data.get('positions', 0))
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] Position calculation error: {str(e)}")
            total_positions = int(data.get('positions', 0))
        
        # Create startup first to get ID
        try:
            startup = Startup(
                name=data['name'],
                industry=data['industry'],
                location=data.get('location'),
                description=data.get('description'),
                stage=data.get('stage', 'idea'),
                positions=total_positions,
                roles=roles_data,
                tech_stack=tech_stack_data,
                revenue=float(data.get('revenue', 0)),
                funding_amount=float(data.get('funding_amount', 0)),
                funding_round=data.get('funding_round', 'pre-seed'),
                burn_rate=float(data.get('burn_rate', 0)),
                runway_months=int(data.get('runway_months', 0)),
                valuation=float(data.get('valuation', 0)),
                financial_notes=data.get('financial_notes', ''),
                creator_id=current_user_id,
                creator_first_name=current_user.first_name,
                creator_last_name=current_user.last_name
            )
            
            db.session.add(startup)
            db.session.flush()  # Get startup ID without committing
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] Startup creation error: {str(e)}")
            db.session.rollback()
            return error_response(f'Failed to create startup object: {str(e)}', 500)
        
        # Create startup upload directory
        try:
            startup_upload_dir = os.path.join(UPLOAD_FOLDER, str(startup.id))
            os.makedirs(startup_upload_dir, exist_ok=True)
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] Directory creation error: {str(e)}")
            db.session.rollback()
            return error_response(f'Failed to create upload directory: {str(e)}', 500)

        # Create startup Chatroom
        try:
            print("Creating chat conversation for new startup...:", startup.to_dict())
            ChatConversation.add_to_startup_chat(current_user, startup)
            print("Chat conversation created for startup:", startup)
        except Exception as e:
            print(f"⚠️ [REGISTER_STARTUP] Chat creation error: {str(e)}")
            # Don't fail the entire request for chat creation
        
        try:
            db.session.commit()
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] Database commit error: {str(e)}")
            db.session.rollback()
            return error_response(f'Failed to save startup: {str(e)}', 500)
        
        # Send startup creation notification
        try:
            notify_startup_created(
                user_id=current_user_id,
                startup_name=startup.name,
                startup_id=startup.id
            )
        except Exception as e:
            print(f"⚠️ [REGISTER_STARTUP] Startup creation notification failed: {e}")
        
        # Handle logo upload to file system
        try:
            if 'logo' in files:
                logo_file = files['logo']
                if logo_file and logo_file.filename != '' and allowed_file(logo_file.filename):
                    if validate_file_size(logo_file):
                        filename = secure_filename(logo_file.filename)
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{filename}"
                        logo_path = os.path.join(startup_upload_dir, unique_filename)
                        logo_file.save(logo_path)
                        
                        startup.logo_path = logo_path
                        startup.logo_url = f"/startups/{startup.id}/logo"
                        startup.logo_content_type = logo_file.content_type
        except Exception as e:
            print(f"⚠️ [REGISTER_STARTUP] Logo upload error: {str(e)}")
        
        # Handle banner upload to file system
        try:
            if 'banner' in files:
                banner_file = files['banner']
                if banner_file and banner_file.filename != '' and allowed_file(banner_file.filename):
                    if validate_file_size(banner_file):
                        filename = secure_filename(banner_file.filename)
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{filename}"
                        banner_path = os.path.join(startup_upload_dir, unique_filename)
                        banner_file.save(banner_path)
                        
                        startup.banner_path = banner_path
                        startup.banner_url = f"/startups/{startup.id}/banner"
                        startup.banner_content_type = banner_file.content_type
        except Exception as e:
            print(f"⚠️ [REGISTER_STARTUP] Banner upload error: {str(e)}")

        # Handle document uploads to file system
        try:
            user = User.query.get(current_user_id)
            document_files = files.getlist('documents')
            for doc_file in document_files:
                try:
                    if doc_file and doc_file.filename != '' and allowed_file(doc_file.filename):
                        filename = secure_filename(doc_file.filename)
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{filename}"
                        doc_path = os.path.join(startup_upload_dir, unique_filename)
                        doc_file.save(doc_path)

                        # Check storage limit after saving
                        file_size_mb = (os.path.getsize(doc_path) / (1024 * 1024)) if os.path.exists(doc_path) else 0
                        can_upload, error_message = can_upload_file(current_user_id, file_size_mb)
                        if not can_upload:
                            if os.path.exists(doc_path):
                                os.remove(doc_path)
                            return error_response(error_message, 403)
                        
                        file_url = f"/startups/{startup.id}/documents/{unique_filename}"

                        if user:
                            user.increase_storage_used(file_size_mb)
                                                
                        startup.add_document(
                            filename=doc_file.filename,
                            file_path=doc_path,
                            file_url=file_url,
                            content_type=doc_file.content_type,
                            document_type=data.get('document_type', 'general')
                        )

                except Exception as e:
                    print(f"⚠️ [REGISTER_STARTUP] Individual document upload error: {str(e)}")
                    # Continue with other documents
        except Exception as e:
            print(f"⚠️ [REGISTER_STARTUP] Documents upload error: {str(e)}")
        
        # Add user to userRoles as founder
        try:
            existing_role = UserRole.query.filter_by(
                user_id=current_user_id,
                role="founder"
            ).first()

            if not existing_role:
                db.session.add(UserRole(user_id=current_user_id, role="founder"))
            current_user.active_startups_count += 1
        except Exception as e:
            print(f"⚠️ [REGISTER_STARTUP] User role assignment error: {str(e)}")
        
        # Add creator as first member
        try:
            startup.add_member(
                current_user_id,
                current_user.first_name,
                current_user.last_name,
                'founder'
            )
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] Failed to add creator as member: {str(e)}")
            db.session.rollback()
            return error_response(f'Failed to add creator as member: {str(e)}', 500)
        
        # Award startup creation points
        try:
            waitlist_user = Waitlist.query.filter_by(email=current_user.email).first()
            if waitlist_user:
                today = datetime.utcnow().date()
                last_activity_date = waitlist_user.last_activity_at.date() if waitlist_user.last_activity_at else None
                
                if last_activity_date != today:
                    waitlist_user.add_points(points=Waitlist.POINTS_PER_STARTUP, category='new_startup')
        except Exception as e:
            print(f"⚠️ [REGISTER_STARTUP] Failed to award startup creation points: {e}")
        
        # Final commit
        try:
            db.session.commit()
        except Exception as e:
            print(f"❌ [REGISTER_STARTUP] Final commit error: {str(e)}")
            db.session.rollback()
            return error_response(f'Failed to finalize startup: {str(e)}', 500)
        
        return success_response({
            'startup': startup.to_dict(),
            'role': 'founder'
            }, 'Startup created successfully', 201)
        
    except Exception as e:
        print(f"❌ [REGISTER_STARTUP] Critical error: {str(e)}")
        db.session.rollback()
        # Clean up uploaded files if registration fails
        if startup_upload_dir and os.path.exists(startup_upload_dir):
            try:
                shutil.rmtree(startup_upload_dir)
            except Exception as cleanup_error:
                print(f"⚠️ [REGISTER_STARTUP] Cleanup error: {str(cleanup_error)}")
        return error_response(f'Failed to create startup: {str(e)}', 500)

#! UPDATE STARTUP
@startups_bp.route('/<int:startup_id>', methods=['PUT'])
@jwt_required()
def update_startup(startup_id):
    """Update startup"""
    current_user_id = get_jwt_identity()
    
    startup = Startup.query.get(startup_id)
    if not startup:
        return error_response('Startup not found', 404)
    
    if int(current_user_id) != int(startup.creator_id):
        return error_response('Only the startup creator can update the startup', 403)
    
    data = request.form
    
    try:
        # Basic startup info
        if 'name' in data:
            if data['name'] != startup.name and Startup.query.filter_by(name=data['name']).first():
                return error_response('Startup name already exists', 409)
            startup.name = data['name']
        
        if 'industry' in data:
            startup.industry = data['industry']
        
        if 'location' in data:
            startup.location = data['location']
        
        if 'description' in data:
            startup.description = data['description']
        
        if 'stage' in data:
            startup.update_stage(data['stage'])
        
        if 'positions' in data:
            startup.positions = data['positions']
        
        if 'roles' in data:
            roles_data = json.loads(data['roles']) if isinstance(data['roles'], str) else data['roles']
            total_positions = calculate_total_positions(roles_data)
            startup.roles = roles_data
            flag_modified(startup, "roles")
            startup.positions = total_positions
        
        # Financial fields
        if 'revenue' in data:
            startup.revenue = float(data['revenue']) if data['revenue'] is not None else 0.0
        
        if 'funding_amount' in data:
            startup.funding_amount = float(data['funding_amount']) if data['funding_amount'] is not None else 0.0
        
        if 'funding_round' in data:
            startup.funding_round = data['funding_round']
        
        if 'burn_rate' in data:
            startup.burn_rate = float(data['burn_rate']) if data['burn_rate'] is not None else 0.0
        
        if 'runway_months' in data:
            startup.runway_months = int(data['runway_months']) if data['runway_months'] is not None else 0
        
        if 'valuation' in data:
            startup.valuation = float(data['valuation']) if data['valuation'] is not None else 0.0
        
        if 'financial_notes' in data:
            startup.financial_notes = data['financial_notes']
        
        if 'tech_stack' in data:
            startup.tech_stack = json.loads(data['tech_stack'])
            flag_modified(startup, "tech_stack")

        
        # Handle file uploads
        files = request.files
        startup_upload_dir = os.path.join(UPLOAD_FOLDER, str(startup.id))
        
        # Handle logo upload
        if 'logo' in files:
            logo_file = files['logo']
            if logo_file and allowed_file(logo_file.filename):
                if validate_file_size(logo_file):
                    logo_path = os.path.join(startup_upload_dir, secure_filename(logo_file.filename))
                    logo_file.save(logo_path)
                    startup.logo_path = logo_path
                    startup.logo_url = f"/startups/{startup.id}/logo"
        
        # Handle banner upload
        if 'banner' in files:
            banner_file = files['banner']
            if banner_file and allowed_file(banner_file.filename):
                if validate_file_size(banner_file):
                    banner_path = os.path.join(startup_upload_dir, secure_filename(banner_file.filename))
                    banner_file.save(banner_path)
                    startup.banner_path = banner_path
                    startup.banner_url = f"/startups/{startup.id}/banner"
        
        removed_docs = request.form.get("removed_documents")

        if removed_docs:
            removed_ids = json.loads(removed_docs)

            for doc_id in removed_ids:
                doc = StartupDocument.query.get(doc_id)
                if doc and doc.startup_id == startup.id:
                    if os.path.exists(doc.file_path):
                        os.remove(doc.file_path)
                    db.session.delete(doc)

        user = User.query.get(current_user_id)
        document_files = files.getlist('documents')
        
        for doc_file in document_files:
            if doc_file and doc_file.filename != '' and allowed_file(doc_file.filename):
                filename = secure_filename(doc_file.filename)
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{filename}"
                doc_path = os.path.join(startup_upload_dir, unique_filename)
                doc_file.save(doc_path)

                # Check storage limit after saving so file size is accurate
                file_size_mb = (os.path.getsize(doc_path) / (1024 * 1024)) if os.path.exists(doc_path) else 0
                can_upload, error_message = can_upload_file(current_user_id, file_size_mb)
                if not can_upload:
                    if os.path.exists(doc_path):
                        os.remove(doc_path)
                    return error_response(error_message, 403)
                
                file_url = f"/startups/{startup.id}/documents/{unique_filename}"
                
                if user:
                    user.increase_storage_used(file_size_mb)
                startup.add_document(
                    filename=doc_file.filename,
                    file_path=doc_path,
                    file_url=file_url,
                    content_type=doc_file.content_type,
                    document_type=data.get('document_type', 'general')
                )
        
        db.session.commit()
        return success_response({'startup': startup.to_dict()}, 'Startup updated successfully')
        
    except ValueError as e:
        print(f"❌ [UPDATE_STARTUP] ValueError: {str(e)}")
        db.session.rollback()
        return error_response(f'Invalid data format: {str(e)}', 400)
    except Exception as e:
        print(f"❌ [UPDATE_STARTUP] Exception: {str(e)}")
        db.session.rollback()
        return error_response(f'Failed to update startup: {str(e)}', 500)
@startups_bp.route('/<int:startup_id>/members', methods=['GET'])
@jwt_required()
def get_startup_members(startup_id):
    """Get startup members"""
    current_user_id = get_jwt_identity()
    
    startup = Startup.query.get(startup_id)
    if not startup:
        return error_response('Startup not found', 404)
    
    members = StartupMember.query.filter_by(startup_id=startup_id).all()
    return success_response({
        'members': [member.to_dict() for member in members]
    })

#! ADD STARTUP MEMBER
@startups_bp.route('/<int:startup_id>/members', methods=['POST'])
@jwt_required()
def add_startup_member(startup_id):
    """Add member to startup"""
    
    current_user_id = get_jwt_identity()
    
    startup = Startup.query.get(startup_id)
    if not startup:
        return error_response('Startup not found', 404)
    
    # Check if user is authorized to add members
    if not can_manage_members(startup_id, current_user_id):
        return error_response("Only owner or founder can add members", 403)
    current_user = User.query.get(current_user_id)
    if not can_add_collaborator(current_user):
        return error_response('Collaborator addition limit reached for your plan', 403)
    data = request.get_json()
    required_fields = ['user_id', 'first_name', 'last_name', 'role']
    for field in required_fields:
        if field not in data:
            return error_response(f'Missing required field: {field}', 400)
    try:
        member = startup.add_member(
            data['user_id'],
            data['first_name'],
            data['last_name'],
            data.get('role', 'member')
        )
        ChatConversation.add_to_startup_chat(member.member_user, startup)
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Added to Startup (4.4)
        # ════════════════════════════════════════════════════════════
        try:
            role = data.get('role', 'member')
            notify_added_to_startup(
                user_id=data['user_id'],
                startup_name=startup.name,
                startup_id=startup.id,
                role=role
            )
        except Exception as e:
            print(f"⚠️ Added to startup notification failed: {e}")
        db.session.commit()
        return success_response({'member': member.to_dict()}, 'Member added successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to add member: {str(e)}', 500)


#! DELETE STARTUP
@startups_bp.route('/<int:startup_id>', methods=['DELETE'])
@jwt_required()
def delete_startup(startup_id):
    """Delete startup and all associated files"""
    current_user_id = get_jwt_identity()
    
    startup = Startup.query.get(startup_id)
    if not startup:
        return error_response('Startup not found', 404)
    
    # Check if user is authorized to delete this startup
    role = get_current_user_startup_role(startup_id)
    if role == 'none' or not role:
        print(f"❌ AUTHORIZATION FAILED - User {current_user_id} has role '{role}' for startup {startup_id}")
        return error_response('Unauthorized to delete this startup', 403)
    
    try:
        # Delete associated files from file system
        startup_upload_dir = os.path.join(UPLOAD_FOLDER, str(startup_id))
        if os.path.exists(startup_upload_dir):
            shutil.rmtree(startup_upload_dir)
        # Delete from database
        # StartupDocument.query.filter_by(startup_id=startup_id).delete()
        
        ChatConversation.delete_startup_chat(startup_id)
        
        # db.session.delete(startup)
        startup.status = 'deleted'
        db.session.commit()
        return success_response(message='Startup deleted successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to delete startup: {str(e)}', 500)

#! GET STARTUP LOGO (Public - no auth required)
@startups_bp.route('/<int:startup_id>/logo')
def get_startup_logo(startup_id):
    """Get startup logo from file system"""
    startup = Startup.query.get_or_404(startup_id)
    if not startup.logo_path or not os.path.exists(startup.logo_path):
        return error_response('Logo not found', 404)
    
    return send_file(
        startup.logo_path,
        mimetype=startup.logo_content_type,
        as_attachment=False,
        download_name=f'logo_{startup.name}{os.path.splitext(startup.logo_path)[1]}'
    )

#! GET STARTUP BANNER (Public - no auth required)
@startups_bp.route('/<int:startup_id>/banner')
def get_startup_banner(startup_id):
    """Get startup banner from file system"""
    startup = Startup.query.get_or_404(startup_id)
    if not startup.banner_path or not os.path.exists(startup.banner_path):
        return error_response('Banner not found', 404)
    
    return send_file(
        startup.banner_path,
        mimetype=startup.banner_content_type,
        as_attachment=False,
        download_name=f'banner_{startup.name}{os.path.splitext(startup.banner_path)[1]}'
    )

#! GET STARTUP DOCUMENTS
@startups_bp.route('/<int:startup_id>/documents', methods=['GET'])
@jwt_required()
def get_startup_documents(startup_id):
    """Get all startup documents"""
    current_user_id = get_jwt_identity()

    documents = StartupDocument.query.filter_by(startup_id=startup_id).all()

    filtered_documents = []
    for doc in documents:
        if has_startup_document_visibility_access(current_user_id, doc):
            filtered_documents.append(doc)
    return success_response({'documents': [doc.to_dict() for doc in filtered_documents]})

#! SERVE STARTUP FILE (Public - no auth required)
@startups_bp.route('/uploads/<int:startup_id>/<filename>', methods=['GET'])
def serve_startup_file(startup_id, filename):
    """Serve uploaded startup files directly"""
    try:
        startup = Startup.query.get(startup_id)
        if not startup:
            return error_response('Startup not found', 404)
        
        # Security check
        file_path = os.path.join(UPLOAD_FOLDER, str(startup_id), filename)
        
        if not os.path.exists(file_path):
            return error_response('File not found', 404)
        
        # Check if file is in the startup's upload directory
        expected_dir = os.path.join(UPLOAD_FOLDER, str(startup_id))
        if not os.path.commonpath([file_path, expected_dir]) == expected_dir:
            return error_response('Access denied', 403)
        
        return send_file(file_path)
        
    except Exception as e:
        return error_response(f'Failed to serve file: {str(e)}', 500)
        
#! DOWNLOAD DOCUMENT
@startups_bp.route('/<int:startup_id>/documents/<int:document_id>/download')
@jwt_required()
def download_document(startup_id, document_id):
    """Download a specific document from file system"""
    current_user_id = get_jwt_identity()
    
    document = StartupDocument.query.filter_by(id=document_id, startup_id=startup_id).first_or_404()
    
    # Check if user has access to this startup
    if not has_startup_access(current_user_id, startup_id):
        return error_response('Unauthorized to download this document', 403)
    
    if not os.path.exists(document.file_path):
        return error_response('File not found on server', 404)
    
    return send_file(
        document.file_path,
        as_attachment=True,
        download_name=document.filename
    )

#! UPLOAD DOCUMENT
@startups_bp.route('/<int:startup_id>/documents', methods=['POST'])
@jwt_required()
def upload_document(startup_id):
    """Upload additional documents to startup"""
    current_user_id = get_jwt_identity()
    


    if not can_manage_documents(startup_id, current_user_id):
        return error_response("Only owner or founder can upload documents", 403)
    # Check if user is authorized to upload documents
    if not has_startup_management_access(current_user_id, startup_id):
        return error_response('Unauthorized to upload documents to this startup', 403)
    
    if 'document' not in request.files:
        return error_response('No document provided')
    
    document_file = request.files['document']
    if document_file.filename == '':
        return error_response('No file selected')
    
    if not allowed_file(document_file.filename):
        return error_response('File type not allowed')
    
    if not validate_file_size(document_file):
        return error_response('File size too large')
    
    try:
        # Create startup upload directory if it doesn't exist
        startup_upload_dir = os.path.join(UPLOAD_FOLDER, str(startup_id))
        os.makedirs(startup_upload_dir, exist_ok=True)
        
        # Save file to file system first so we can measure its size
        unique_filename = generate_unique_filename(document_file.filename)
        doc_path = os.path.join(startup_upload_dir, unique_filename)
        document_file.save(doc_path)

        # Now check storage limit with the actual saved file size
        file_size_mb = (os.path.getsize(doc_path) / (1024 * 1024)) if os.path.exists(doc_path) else 0
        can_upload, error_message = can_upload_file(current_user_id, file_size_mb)
        if not can_upload:
            # Clean up the file we just saved since upload is not allowed
            if os.path.exists(doc_path):
                os.remove(doc_path)
            return error_response(error_message, 403)
        
        # Create document with file_url
        file_url = f"/api/startups/uploads/{startup_id}/{unique_filename}"
        print(f"Uploading document: {document_file.filename}, visible_by: {request.form.get('visible_by', 'public')}")
        document = StartupDocument(
            startup_id=startup_id,
            filename=document_file.filename,
            visible_by=request.form.get('visible_by', 'public'),
            file_path=doc_path,
            file_url=file_url,  # Set the file_url
            content_type=document_file.content_type,
            document_type=request.form.get('document_type', 'general'),
            file_size_mb=file_size_mb
        )

        user = User.query.get(current_user_id)
        if user:
            user.increase_storage_used(file_size_mb)
        
        db.session.add(document)
        db.session.commit()
        
        return success_response({'document': document.to_dict()}, 'Document uploaded successfully')
    except Exception as e:
        return error_response(f'Failed to upload document: {str(e)}', 500)
        
#! DELETE DOCUMENT
@startups_bp.route('/<int:startup_id>/documents/<int:document_id>', methods=['DELETE'])
@jwt_required()
def delete_document(startup_id, document_id):
    """Delete a document from startup"""
    current_user_id = get_jwt_identity()
    
    document = StartupDocument.query.filter_by(id=document_id, startup_id=startup_id).first_or_404()

    # Check if user is authorized to delete documents
    if not can_manage_documents(startup_id, current_user_id):
        return error_response("Only owner or founder can delete documents", 403)
    
    try:
        # Delete file from file system
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        # Delete from database, and decrease user's storage used
        user = User.query.get(current_user_id)
        if user:
            user.decrease_storage_used(document.file_size_mb or 0)
            
        db.session.delete(document)
        db.session.commit()
        return success_response(message='Document deleted successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to delete document: {str(e)}', 500)

#! GET USER'S STARTUPS
@startups_bp.route('/user/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_startups(user_id):
    """Get all startups created by a specific user"""
    current_user_id = get_jwt_identity()
    
    # Users can only see their own startups unless they're admin
    if user_id != current_user_id:
        current_user = User.query.get(current_user_id)
        if not current_user or current_user.role != 'admin':
            return error_response('Unauthorized to view other users startups', 403)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = Startup.query.filter_by(creator_id=user_id)
    result = paginate(query, page, per_page)
    
    return success_response({
        'startups': [startup.to_dict() for startup in result['items']],
        'pagination': {
            'page': result['page'],
            'per_page': result['per_page'],
            'total': result['total'],
            'pages': result['pages']
        }
    })
# GET startup names
@startups_bp.route('/names', methods=['GET'])
@jwt_required()
def get_startup_names():
    """Get names and IDs of all startups"""
    user_id = get_jwt_identity()
    startups = Startup.query.all()
    startup_list = [{'id': s.id, 'name': s.name} for s in startups]
    # Get startups where user is a member
    member_startups = StartupMember.query.filter_by(user_id=user_id, is_active=True).all()
    for member in member_startups:
        if not any(s['id'] == member.startup_id for s in startup_list):
            startup = Startup.query.get(member.startup_id)
            if startup:
                startup_list.append({'id': startup.id, 'name': startup.name})
    return success_response({'startups': startup_list})
#! GET STARTUP STATS
@startups_bp.route('/<int:startup_id>/stats', methods=['GET'])
@jwt_required()
def get_startup_stats(startup_id):
    """Get startup statistics"""
    current_user_id = get_jwt_identity()
    
    startup = Startup.query.get_or_404(startup_id)
    
    # Check if user has access to this startup
    if not has_startup_access(current_user_id, startup_id):
        return error_response('Unauthorized to access this startup stats', 403)
    
    stats = {
        'views': startup.views,
        'member_count': startup.member_count,
        'positions': startup.positions,
        'created_at': startup.created_at.isoformat() if startup.created_at else None,
        'stage': startup._enum_to_value(startup.stage)
    }
    
    return success_response({'stats': stats})

#! GET AVAILABLE INDUSTRIES AND STAGES (Public - no auth required)
@startups_bp.route('/industries', methods=['GET'])
def get_industries():
    """Get list of all available industries"""
    industries = db.session.query(Startup.industry).distinct().all()
    industry_list = [industry[0] for industry in industries if industry[0]]
    
    return success_response({'industries': industry_list})

@startups_bp.route('/stages', methods=['GET'])
def get_stages():
    """Get list of all available startup stages"""
    from app.models.startup import StartupStage
    stages = [stage.value for stage in StartupStage]
    
    return success_response({'stages': stages})


@startups_bp.route('/<int:startup_id>/join-requests', methods=['GET'])
@jwt_required()
def get_join_requests(startup_id):
    """
    Get all join requests for a startup (pending + processed)
    Only owner or founder members can see this
    """
    current_user_id = get_jwt_identity()
    if not can_manage_members(startup_id, current_user_id):
        return error_response(
            "Only the startup owner or founders can view join requests", 
            403
        )

    startup = Startup.query.get_or_404(startup_id)

    # Optional: filter by status
    status_filter = request.args.get('status', 'all')  # default: all
    valid_statuses = ['pending', 'approved', 'rejected', 'cancelled', 'all']
    if status_filter not in valid_statuses:
        status_filter = 'pending'

    query = startup.join_requests
    if status_filter != 'all':
        query = query.filter_by(status=JoinRequestStatus(status_filter))

    requests = query.order_by(JoinRequest.created_at.desc()).all()

    return success_response({
        'join_requests': [req.to_dict() for req in requests],
        'count': len(requests),
        'filter': status_filter,
        'current_user_role': get_current_user_startup_role(startup_id)
    })

@startups_bp.route('/user/<int:user_id>/startup/<int:startup_id>', methods=['GET'])
def get_join_request_by_user_and_startup(user_id, startup_id):
    """Get join request by user ID and startup ID"""
    join_request = JoinRequest.query.filter_by(
        user_id=user_id,
        startup_id=startup_id
    ).first()
    
    if not join_request:
        return error_response('Join request not found', 404)
    
    return success_response({'join_request': join_request.to_dict()})
@startups_bp.route('/<int:startup_id>/join-request', methods=['OPTIONS'])
def join_request_options(startup_id):
    """CORS preflight handler for join requests"""
    return success_response({'message': 'ok'}, status=200)


@startups_bp.route('/<int:startup_id>/join-request', methods=['POST'])
@jwt_required()
def send_join_request(startup_id):
    """Allow any authenticated user to submit a join request"""
    try:
        current_user_id = get_jwt_identity()
        startup = Startup.query.get_or_404(startup_id)

        current_user = User.query.get(current_user_id)
        if not current_user:
            print(f"User {current_user_id} not found")
            return error_response('User not found', 404)
        membership = StartupMember.query.filter_by(
            startup_id=startup_id,
            user_id=current_user_id
        ).first()
        if membership:
            print(f"User {current_user_id} is already a member of startup {startup_id}")
            return error_response('You are already a member of this startup', 400)

        data = request.get_json() or {}
        message = (data.get('message') or '').strip()
        role = data.get('role', 'member')
        linkedin_url = (data.get('linkedin_url') or '').strip()
        portfolio_url = (data.get('portfolio_url') or '').strip()
        github_url = (data.get('github_url') or '').strip()
        media_links = {
            'linkedin': linkedin_url,
            'portfolio': portfolio_url,
            'github': github_url
        }
        print(f"Join Request Data: {data}, Message: '{message}'")
        
        if not message:
            print("No message provided")
            return error_response('Please share why you want to join this team', 400)

        existing = JoinRequest.query.filter_by(
            startup_id=startup_id,
            user_id=current_user_id,
            status=JoinRequestStatus.pending
        ).first()
        if existing:
            print(f"User {current_user_id} already has pending request {existing.id} for startup {startup_id}")
            return error_response('You already have a pending request for this startup', 409)

        user = User.query.get(current_user_id)
        if not user:
            print(f"User {current_user_id} not found")
            return error_response('User not found', 404)

        print(f"Creating join request for user {user.first_name} {user.last_name} to startup {startup.name}")

        join_request = JoinRequest(
            startup_id=startup_id,
            startup_name=startup.name,
            user_id=current_user_id,
            first_name=user.first_name,
            last_name=user.last_name,
            media_links=media_links,
            message=message,
            role=role,
            status=JoinRequestStatus.pending
        )

        db.session.add(join_request)
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: New Join Request (4.4)
        # ════════════════════════════════════════════════════════════
        try:
            
            
            # Get owners and founders

            managers = StartupMember.query.filter(
                StartupMember.startup_id == startup_id,
                (StartupMember.role.in_(['owner', 'founder'])) | (StartupMember.admin == True),
                StartupMember.is_active == True
            ).all()
            print(f"Notifying {len(managers)} managers about new join request:", [f"{m.first_name} {m.last_name}" for m in managers])
            requester_name = f"{current_user.first_name} {current_user.last_name}"
            for manager in managers:
                notify_info(
                    user_id=manager.user_id,
                    message=f"{requester_name} has requested to join {startup.name} as a {role}.",
                    link_url=f"/startup-details/{startup.id}"
                )
        except Exception as e:
            print(f"⚠️ Join request notification failed: {e}")

        print(f"Join request created successfully with ID {join_request.id}")

        return success_response({
            'join_request': join_request.to_dict()
        }, 'Join request submitted successfully', 201)
    except Exception as e:
        print(f"Error in send_join_request: {str(e)}")
        db.session.rollback()
        return error_response(f'Failed to send join request: {str(e)}', 500)

@startups_bp.route('/<int:startup_id>/join-requests/<int:request_id>/accept', methods=['POST'])
@jwt_required()
def accept_join_request(startup_id, request_id):
    """
    Accept a pending join request and automatically add the user as a member
    """
    from app.models.joinRequest import JoinRequestStatus
    
    current_user_id = get_jwt_identity()
    if not can_manage_members(startup_id, current_user_id):
        return error_response(
            "Only the startup owner or founders can accept join requests", 
            403
        )

    join_request = JoinRequest.query.filter_by(
        id=request_id,
        startup_id=startup_id,
        status=JoinRequestStatus.pending
    ).first()

    if not join_request:
        return error_response("Join request not found or already processed", 404)

    # Get startup info for notification
    startup = Startup.query.get(startup_id)
    user_id_to_notify = join_request.user_id

    try:
        # The approve method already handles adding the member
        new_member = join_request.approve()
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Join Request Accepted / Added to Startup (4.4)
        # ════════════════════════════════════════════════════════════
        try:
            notify_added_to_startup(
                user_id=user_id_to_notify,
                startup_name=startup.name,
                startup_id=startup.id,
                role=new_member.role
            )
            
            # Also notify as access granted
            notify_access_granted(
                user_id=user_id_to_notify,
                resource=startup.name,
                resource_id=startup.id
            )
        except Exception as e:
            print(f"⚠️ Join request acceptance notification failed: {e}")
        
        return success_response({
            'message': "Join request accepted. User added as team member.",
            'new_member': {
                'userId': new_member.user_id,
                'role': new_member.role,
                'joinedAt': new_member.joined_at.isoformat() if hasattr(new_member, 'joined_at') else None
            }
        }, status=200)

    except Exception as e:
        db.session.rollback()
        return error_response(f"Failed to accept request: {str(e)}", 500)


@startups_bp.route('/<int:startup_id>/join-requests/<int:request_id>/reject', methods=['POST'])
@jwt_required()
def reject_join_request(startup_id, request_id):
    """
    Reject a pending join request
    """
    current_user_id = get_jwt_identity()
    if not can_manage_members(startup_id, current_user_id):
        return error_response(
            "Only the startup owner or founders can reject join requests", 
            403
        )

    join_request = JoinRequest.query.filter_by(
        id=request_id,
        startup_id=startup_id,
        status=JoinRequestStatus.pending
    ).first()

    if not join_request:
        return error_response("Join request not found or already processed", 404)

    # Get startup info for notification
    startup = Startup.query.get(startup_id)
    user_id_to_notify = join_request.user_id

    try:
        join_request.reject()
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Join Request Rejected (4.4)
        # ════════════════════════════════════════════════════════════
        try:
            notify_info(
                user_id=user_id_to_notify,
                message=f"Your request to join {startup.name} was not approved at this time."
            )
        except Exception as e:
            print(f"⚠️ Join request rejection notification failed: {e}")
        
        return success_response({
            "message": "Join request rejected successfully",
            "request_id": request_id
        })

    except Exception as e:
        db.session.rollback()
        return error_response(f"Failed to reject request: {str(e)}", 500)



# Optional: Allow user to cancel their own request
@startups_bp.route('/join-requests/<int:request_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_my_join_request(request_id):
    """
    Let the requesting user cancel their own pending join request
    """
    current_user_id = get_jwt_identity()
    
    join_request = JoinRequest.query.filter_by(
        id=request_id,
        user_id=current_user_id,
        status=JoinRequestStatus.pending
    ).first()

    if not join_request:
        return error_response("Request not found, not yours, or already processed", 404)

    try:
        join_request.cancel()
        return success_response({
            "message": "Your join request has been cancelled",
            "request_id": request_id
        })

    except Exception as e:
        db.session.rollback()
        return error_response(f"Failed to cancel request: {str(e)}", 500)

# Helper functions for authorization
def has_startup_access(user_id, startup_id):
    """Check if user has access to view startup data"""
    # Admin users can access all startups
    current_user = User.query.get(user_id)
    if current_user and current_user.role == 'admin':
        return True
    
    # Check if user is a member of the startup
    membership = StartupMember.query.filter_by(
        user_id=user_id, 
        startup_id=startup_id
    ).first()
    
    return membership is not None

def has_startup_management_access(user_id, startup_id):
    """Check if user has permission to manage startup data"""
    # Admin users can manage all startups
    current_user = User.query.get(user_id)
    if current_user and current_user.role == 'admin':
        return True
    # Check if user is the creator or has admin/manager role in the startup
    startup = Startup.query.get(startup_id)
    if startup and startup.creator_id == user_id:
        return True
    
    # Check if user is an admin or manager of the startup
    membership = StartupMember.query.filter_by(
        user_id=user_id, 
        startup_id=startup_id
    ).first()
    admin = membership.admin if membership else False
    if not membership or not membership.role or (membership.role.value if hasattr(membership.role, 'value') else membership.role) not in ['owner', 'founder', 'manager'] and not admin:
        return False
    membership_role_value = membership.role.value if hasattr(membership.role, 'value') else membership.role

    allowed_roles = {
        UserRoles.admin.value,
        'manager',
        UserRoles.founder.value,
        'owner'
    }

    return membership_role_value in allowed_roles



def get_startup_member_ids(startup_id, exclude_user_id=None):
    """Get list of user IDs who are members of a startup"""
    from app.models.startUpMember import StartupMember
    members = StartupMember.query.filter_by(startup_id=startup_id, is_active=True).all()
    user_ids = [m.user_id for m in members if m.user_id]
    if exclude_user_id:
        user_ids = [uid for uid in user_ids if uid != exclude_user_id]
    return user_ids

@startups_bp.route('/<int:startup_id>/members/<int:member_id>', methods=['DELETE'])
@jwt_required()
def remove_startup_member(startup_id, member_id):
    """Remove member from startup"""
    current_user = get_jwt_identity()
    startup = Startup.query.get_or_404(startup_id)

    if not can_manage_members(startup_id, current_user):
        return error_response('Unauthorized', 403)

    # Get member info before removal for notification
    member = StartupMember.query.get(member_id)
    if member.user_id == current_user:
        return error_response('You cannot remove yourself. Use the leave startup endpoint instead.', 400)
    member_user_id = member.user_id if member else None

    db.session.delete(member)
    # chat_conversation = ChatConversation.query.filter_by(startup_id=startup_id).first()
    # if chat_conversation and member_user_id:
    #     chat_conversation.remove_participant(member_user_id)

    db.session.commit()

    
    # ════════════════════════════════════════════════════════════
    # ✨ NOTIFICATION: Removed from Startup (4.4)
    # ════════════════════════════════════════════════════════════
    if member_user_id:
        try:
            notify_removed_from_startup(
                user_id=member_user_id,
                startup_name=startup.name,
                startup_id=startup.id
            )
        except Exception as e:
            print(f"⚠️ Removed from startup notification failed: {e}")
    return success_response(message='Member removed successfully')

@startups_bp.route('/<int:startup_id>/members/<int:member_id>/promote', methods=['POST'])
@jwt_required()
def promote_member_to_admin(startup_id, member_id):
    """Promote a member to admin role"""
    current_user_id = get_jwt_identity()
    
    if not has_startup_management_access(current_user_id, startup_id):
        return error_response('Unauthorized', 403)
    
    member = StartupMember.query.get(member_id)
    if not member:
        return error_response('Member not found', 404)
    
    if member.startup_id != startup_id:
        return error_response('Member does not belong to this startup', 400)
    
    try:
        member.admin = True
        db.session.commit()
        
        try:
            notify_info(
                user_id=member.user_id,
                message=f"You have been promoted to admin of the startup: {member.startup.name}"
            )
        except Exception as e:
            print(f"⚠️ Promoted to admin notification failed: {e}")
        
        return success_response(message='Member promoted to admin successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to promote member: {str(e)}', 500)

@startups_bp.route('/<int:startup_id>/members/<int:member_id>/demote', methods=['POST'])
@jwt_required()
def demote_member_from_admin(startup_id, member_id):
    """Demote an admin member back to regular member role"""
    current_user_id = get_jwt_identity()
    
    if not has_startup_management_access(current_user_id, startup_id):
        return error_response('Unauthorized', 403)
    
    member = StartupMember.query.get(member_id)
    if not member:
        return error_response('Member not found', 404)
    
    if member.startup_id != startup_id:
        return error_response('Member does not belong to this startup', 400)
    
    try:
        member.admin = False
        db.session.commit()
        
        try:
            notify_info(
                user_id=member.user_id,
                message=f"You have been demoted from admin of the startup: {member.startup.name}"
            )
        except Exception as e:
            print(f"⚠️ Demoted from admin notification failed: {e}")
        
        return success_response(message='Member demoted from admin successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to demote member: {str(e)}', 500)
@startups_bp.route('/<int:startup_id>/leave', methods=['DELETE'])
@jwt_required()
def leave_startup(startup_id):
    """Allow current user to leave a startup"""
    current_user_id = get_jwt_identity()
    
    membership = StartupMember.query.filter_by(
        startup_id=startup_id,
        user_id=current_user_id
    ).first()
    startup = Startup.query.get(startup_id)
    if startup and startup.creator_id == current_user_id:
        return error_response('Startup owner cannot leave their own startup', 403)
    if not membership:
        return error_response('You are not a member of this startup', 404)
    
    try:
        db.session.delete(membership)
        # chat_conversation = ChatConversation.query.filter_by(startup_id=startup_id).first()
        # if chat_conversation:
        #     chat_conversation.remove_participant(current_user_id)
        db.session.commit()
        
        try:
            startup = Startup.query.get(startup_id)
            notify_info(
                user_id=current_user_id,
                message=f"You have successfully left the startup: {startup.name}"
            )
            notify_info(
                user_id=startup.creator_id,
                message=f"{membership.first_name} {membership.last_name} has left your startup: {startup.name}"
            )
        except Exception as e:
            print(f"⚠️ Left startup notification failed: {e}")
        
        return success_response(message='You have left the startup successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to leave startup: {str(e)}', 500)

@startups_bp.route('/<int:startup_id>/members/<int:member_id>/change-role', methods=['POST'])
@jwt_required()
def change_member_role(startup_id, member_id):
    """Change a member's role (e.g. from member to founder)"""
    current_user_id = get_jwt_identity()
    
    if not has_startup_management_access(current_user_id, startup_id):
        return error_response('Unauthorized', 403)
    
    member = StartupMember.query.get(member_id)
    if not member:
        return error_response('Member not found', 404)
    
    if member.startup_id != startup_id:
        return error_response('Member does not belong to this startup', 400)
    startup = Startup.query.get(startup_id)
    data = request.get_json() or {}
    new_role = data.get('role')
    if new_role not in startup.roles.keys():
        return error_response('Invalid role specified', 400)
    
    try:
        member.role = new_role
        db.session.commit()
        
        try:
            notify_info(
                user_id=member.user_id,
                message=f"Your role in the startup {member.startup.name} has been changed to: {new_role}"
            )
        except Exception as e:
            print(f"⚠️ Role change notification failed: {e}")
        
        return success_response(message='Member role changed successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to change member role: {str(e)}', 500)

@startups_bp.route('/<int:startup_id>/invitations/mine', methods=['OPTIONS'])
def get_my_startup_invitation_options(startup_id):
    """CORS preflight handler for /invitations/mine"""
    return success_response({'message': 'ok'})

@startups_bp.route('/<int:startup_id>/invitations/mine', methods=['GET'])
@jwt_required()
def get_my_startup_invitation(startup_id):
    """
    Get the current user's pending invitation for a specific startup.
    No manager role required — users can only see their own invitation.
    """
    current_user_id = get_jwt_identity()

    invitation = StartupInvitation.query.filter_by(
        startup_id=startup_id,
        invited_user_id=current_user_id,
        status=InvitationStatus.pending
    ).first()

    return success_response({
        'invitation': invitation.to_dict() if invitation else None,
        'has_pending_invitation': invitation is not None
    })

# STARTUP INVITATIONS CRUD
@startups_bp.route('/<int:startup_id>/invitations', methods=['GET'])
@jwt_required()
def get_startup_invitations(startup_id):
    """Get all invitations for a startup (only for managers)"""
    current_user_id = get_jwt_identity()
    
    if not can_manage_members(startup_id, current_user_id):
        return error_response(
            "Only the startup owner or founders can view invitations",
            403
        )
    
    startup = Startup.query.get_or_404(startup_id)
    
    status_filter = request.args.get('status', 'all')
    valid_statuses = ['pending', 'accepted', 'rejected', 'expired', 'all']
    if status_filter not in valid_statuses:
        status_filter = 'pending'
    
    query = startup.invitations
    if status_filter != 'all':
        query = query.filter_by(status=InvitationStatus(status_filter))
    
    invitations = query.order_by(StartupInvitation.created_at.desc()).all()
    
    return success_response({
        'invitations': [inv.to_dict() for inv in invitations],
        'count': len(invitations),
        'filter': status_filter
    })
@startups_bp.route('/<int:startup_id>/invitations', methods=['POST'])
@jwt_required()
def create_startup_invitation(startup_id):
    """Send invitation to a non-member user to join startup"""
    
    current_user_id = get_jwt_identity()
    
    if not can_manage_members(startup_id, current_user_id):
        return error_response(
            "Only the startup owner or founders can send invitations",
            403
        )
    
    startup = Startup.query.get_or_404(startup_id)
    data = request.get_json() or {}
    
    required_fields = ['user_id', 'role']
    
    for field in required_fields:
        if field not in data:
            return error_response(f'{field} is required', 400)
    
    invited_user_id = data['user_id']
    role = data['role']
    expires_in_days = data.get('expires_in_days', 7)  # Default expiration
    
    invited_user = User.query.get(invited_user_id)
    if not invited_user:
        return error_response('User not found', 404)
    
    # Check if user is already a member
    existing_member = StartupMember.query.filter_by(
        startup_id=startup_id,
        user_id=invited_user_id
    ).first()
    if existing_member:
        return error_response('User is already a member of this startup', 400)
    
    # Check if invitation already exists and is pending
    existing_invitation = StartupInvitation.query.filter_by(
        startup_id=startup_id,
        invited_user_id=invited_user_id,
        status=InvitationStatus.pending
    ).first()
    if existing_invitation:
        return error_response('An active invitation already exists for this user', 409)
    
    try:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        invitation = StartupInvitation(
            startup_id=startup_id,
            invited_user_id=invited_user_id,
            invited_by_id=current_user_id,
            role=role,
            expires_at=expires_at,
            status=InvitationStatus.pending
        )
        
        db.session.add(invitation)
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Invited to Startup
        # ════════════════════════════════════════════════════════════
        try:
            notify_info(
                user_id=invited_user_id,
                message=f"You have been invited to join {startup.name} as a {role}.",
                link_url=f"/startup-details/{startup.id}"
            )
        except Exception as e:
            print(f"⚠️ Startup invitation notification failed: {e}")
        
        return success_response({
            'invitation': invitation.to_dict()
        }, 'Invitation sent successfully', 201)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to create invitation: {str(e)}', 500)
@startups_bp.route('/<int:startup_id>/invitations/<int:invitation_id>/accept', methods=['POST'])
@jwt_required()
def accept_startup_invitation(startup_id, invitation_id):
    """Accept a startup invitation and add user as member"""
    
    current_user_id = get_jwt_identity()
    
    invitation = StartupInvitation.query.filter_by(
        id=invitation_id,
        startup_id=startup_id,
        invited_user_id=current_user_id,
        status=InvitationStatus.pending
    ).first()
    if not invitation:
        return error_response("Invitation not found or already processed", 404)
    
    # Check if invitation has expired
    if invitation.expires_at and datetime.utcnow() > invitation.expires_at:
        invitation.status = InvitationStatus.expired
        db.session.commit()
        return error_response("This invitation has expired", 410)
    
    startup = Startup.query.get(startup_id)
    invited_user = User.query.get(current_user_id)
    
    try:
        # Add user as member with the role from invitation
        new_member = startup.add_member(
            current_user_id,
            invited_user.first_name,
            invited_user.last_name,
            invitation.role
        )
        
        # Update invitation status
        invitation.status = InvitationStatus.accepted
        invitation.responded_at = datetime.utcnow()
        
        # Add to startup chat
        ChatConversation.add_to_startup_chat(invited_user, startup)
        
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Invitation Accepted
        # ════════════════════════════════════════════════════════════
        try:
            notify_added_to_startup(
                user_id=current_user_id,
                startup_name=startup.name,
                startup_id=startup.id,
                role=invitation.role
            )
            
            # Notify the inviter
            notify_info(
                user_id=invitation.invited_by_id,
                message=f"{invited_user.first_name} {invited_user.last_name} accepted your invitation to join {startup.name}.",
                link_url=f"/startup-details/{startup.id}"
            )
        except Exception as e:
            print(f"⚠️ Invitation acceptance notification failed: {e}")
        
        return success_response({
            'message': "Invitation accepted. You are now a member of the startup.",
            'new_member': {
                'userId': new_member.user_id,
                'role': new_member.role,
                'joinedAt': new_member.joined_at.isoformat() if hasattr(new_member, 'joined_at') else None
            }
        }, status=200)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f"Failed to accept invitation: {str(e)}", 500)
@startups_bp.route('/<int:startup_id>/invitations/<int:invitation_id>/reject', methods=['POST'])
@jwt_required()
def reject_startup_invitation(startup_id, invitation_id):
    """Reject a startup invitation"""
    
    current_user_id = get_jwt_identity()
    
    invitation = StartupInvitation.query.filter_by(
        id=invitation_id,
        startup_id=startup_id,
        invited_user_id=current_user_id,
        status=InvitationStatus.pending
    ).first()
    
    if not invitation:
        return error_response("Invitation not found or already processed", 404)
    
    startup = Startup.query.get(startup_id)
    invited_user = User.query.get(current_user_id)
    
    try:
        invitation.status = InvitationStatus.rejected
        invitation.responded_at = datetime.utcnow()
        db.session.commit()
        
        # ════════════════════════════════════════════════════════════
        # ✨ NOTIFICATION: Invitation Rejected
        # ════════════════════════════════════════════════════════════
        try:
            notify_info(
                user_id=invitation.invited_by_id,
                message=f"{invited_user.first_name} {invited_user.last_name} declined your invitation to join {startup.name}."
            )
        except Exception as e:
            print(f"⚠️ Invitation rejection notification failed: {e}")
        
        return success_response({
            "message": "Invitation rejected successfully",
            "invitation_id": invitation_id
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f"Failed to reject invitation: {str(e)}", 500)
@startups_bp.route('/<int:startup_id>/invitations/<int:invitation_id>', methods=['DELETE'])
@jwt_required()
def cancel_startup_invitation(startup_id, invitation_id):
    """Cancel a pending invitation (only by the inviter or managers)"""
    
    current_user_id = get_jwt_identity()
    
    if not can_manage_members(startup_id, current_user_id):
        return error_response(
            "Only the startup owner or founders can cancel invitations",
            403
        )
    
    invitation = StartupInvitation.query.filter_by(
        id=invitation_id,
        startup_id=startup_id,
        status=InvitationStatus.pending
    ).first()
    
    if not invitation:
        return error_response("Invitation not found or already processed", 404)
    
    try:
        invited_user = User.query.get(invitation.invited_user_id)
        
        db.session.delete(invitation)
        db.session.commit()
        
        try:
            if invited_user:
                notify_info(
                    user_id=invitation.invited_user_id,
                    message=f"Your invitation to join a startup has been cancelled."
                )
        except Exception as e:
            print(f"⚠️ Invitation cancellation notification failed: {e}")
        
        return success_response(message='Invitation cancelled successfully')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f"Failed to cancel invitation: {str(e)}", 500)
@startups_bp.route('/invitations', methods=['GET'])
@jwt_required()
def get_my_invitations():
    """Get all invitations for the current user"""
    
    current_user_id = get_jwt_identity()
    
    status_filter = request.args.get('status', 'pending')
    
    valid_statuses = ['pending', 'accepted', 'rejected', 'expired', 'all']
    if status_filter not in valid_statuses:
        status_filter = 'pending'
    
    query = StartupInvitation.query.filter_by(invited_user_id=current_user_id)

    if status_filter != 'all':
        query = query.filter_by(status=InvitationStatus(status_filter))

    invitations = query.order_by(StartupInvitation.created_at.desc()).all()

    return success_response({
        'invitations': [inv.to_dict() for inv in invitations],
        'count': len(invitations),
        'filter': status_filter
    })

# ==================== RATING ENDPOINTS ====================

@startups_bp.route('/<int:startup_id>/rate', methods=['POST'])
@jwt_required()
def rate_startup(startup_id):
    """Submit or update a rating for a startup"""
    current_user_id = get_jwt_identity()
    
    startup = Startup.query.get(startup_id)
    if not startup:
        return error_response('Startup not found', 404)
    
    data = request.get_json()
    rating = data.get('rating')
    review_text = data.get('review_text', '')
    
    # Validate rating
    if rating is None or not isinstance(rating, (int, float)):
        return error_response('Rating is required and must be a number', 400)
    
    if rating < 1 or rating > 5:
        return error_response('Rating must be between 1 and 5', 400)
    
    try:
        from app.models.startup_rating import StartupRating
        
        # Check if user already rated this startup
        existing_rating = StartupRating.query.filter_by(
            user_id=current_user_id,
            startup_id=startup_id
        ).first()
        
        if existing_rating:
            # Update existing rating
            existing_rating.rating = float(rating)
            existing_rating.review_text = review_text
        else:
            # Create new rating
            new_rating = StartupRating(
                user_id=current_user_id,
                startup_id=startup_id,
                rating=float(rating),
                review_text=review_text
            )
            db.session.add(new_rating)
        
        db.session.commit()
        
        return success_response({
            'message': 'Rating submitted successfully',
            'rating': float(rating)
        })
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to submit rating: {str(e)}', 500)


@startups_bp.route('/<int:startup_id>/ratings', methods=['GET'])
def get_startup_ratings(startup_id):
    """Get all ratings for a startup and calculate average"""
    startup = Startup.query.get(startup_id)
    if not startup:
        return error_response('Startup not found', 404)
    
    try:
        from app.models.startup_rating import StartupRating

        
        ratings = StartupRating.query.filter_by(startup_id=startup_id).all()
        
        # Calculate average rating
        if ratings:
            avg_rating = sum(r.rating for r in ratings) / len(ratings)
        else:
            avg_rating = 0
        
        return success_response({
            'startup_id': startup_id,
            'ratings': [{
                'id': r.id,
                'user_id': r.user_id,
                'rating': r.rating,
                'review_text': r.review_text,
                'created_at': r.created_at.isoformat()
            } for r in ratings],
            'average_rating': round(avg_rating, 2),
            'total_ratings': len(ratings)
        })
    except Exception as e:
        return error_response(f'Failed to fetch ratings: {str(e)}', 500)
from app.utils.ai_helpers import get_response
import re
@startups_bp.route('/<int:startup_id>/launch-data', methods=['GET'])
@jwt_required()
def get_startup_launch_data(startup_id):
    """
    AI endpoint to generate startup registration suggestions based on an existing idea.
    Fetches idea data and returns pre-filled startup registration data.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return error_response('User not found', 404)
    
    # Fetch the idea by startup_id (assuming it's passed as idea_id)
    from app.models.idea import Idea
    idea = Idea.query.get(startup_id)
    
    if not idea:
        return error_response('Idea not found', 404)
    
    try:
        system_prompt = (
            "You are a startup registration assistant. "
            "Based on the provided idea data, generate startup registration suggestions. "
            "Return ONLY valid JSON with no markdown formatting.\n\n"
            "Schema:\n"
            "{\n"
            '  "name": "string (suggested startup name based on idea title)",\n'
            '  "industry": "string (industry category)",\n'
            '  "description": "string (2-3 sentence description based on idea)",\n'
            '  "stage": "string (idea|mvp|beta|launched|growth)",\n'
            '  "roles": {\n'
            '    "role_name": {"positionsNumber": number}\n'
            '  },\n'
            '  "tech_stack": ["string (technologies)"],\n'
            '  "location": "string (optional location)",\n'
            '  "funding_round": "string (pre-seed|seed|seriesA|seriesB|etc)"\n'
            "}"
        )
        
        user_prompt = (
            f"Based on this idea, suggest startup registration details:\n\n"
            f"Title: {idea.title}\n"
            f"Industry: {idea.industry}\n"
            f"Stage: {idea.stage}\n"
            f"Description: {idea.description}\n"
            f"Project Details: {idea.project_details}\n"
            f"Tags: {', '.join(idea.tags or [])}\n\n"
            f"Generate realistic suggestions for a startup registration form."
        )
        
        response_text, tokens_used = get_response(
            model="qwen/qwen3-32b",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=1024
        )
        
        # Parse JSON response
        try:
            suggestions = json.loads(response_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                suggestions = json.loads(json_match.group())
            else:
                return error_response('Failed to parse AI suggestions', 500)
        
        return success_response({
            'suggestions': suggestions,
            'tokens_used': tokens_used
        }, 'Suggestions generated successfully')
        
    except Exception as e:
        print(f"❌ [AI_LAUNCH_DATA] Error: {str(e)}")
        return error_response(f'Failed to generate suggestions: {str(e)}', 500)
@startups_bp.route('/<int:startup_id>/ai/refine-description', methods=['POST'])
@jwt_required()
def refine_startup_description(startup_id):
    """
    AI endpoint to refine and improve startup description.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return error_response('User not found', 404)
    
    data = request.get_json() or {}
    description = data.get('description', '').strip()
    
    if not description:
        return error_response('Please provide a description to refine', 400)
    
    try:
        system_prompt = (
            "You are a professional startup copywriter. "
            "Improve and refine the given startup description to be more compelling, "
            "professional, and investor-ready. Keep it concise (2-3 sentences). "
            "Return ONLY the refined description text, no JSON."
        )
        
        response_text, tokens_used = get_response(
            model="qwen/qwen3-32b",
            system_prompt=system_prompt,
            user_prompt=f"Refine this startup description:\n\n{description}",
            temperature=0.7,
            max_tokens=256
        )
        
        return success_response({
            'refined_description': response_text.strip(),
            'tokens_used': tokens_used
        })
        
    except Exception as e:
        print(f"❌ [AI_REFINE_DESCRIPTION] Error: {str(e)}")
        return error_response(f'Failed to refine description: {str(e)}', 500)
@startups_bp.route('/<int:startup_id>/ai/suggest-roles', methods=['POST'])
@jwt_required()
def suggest_startup_roles(startup_id):
    """
    AI endpoint to suggest team roles based on startup description.
    """
    current_user_id = get_jwt_identity()
    
    data = request.get_json() or {}
    startup_description = data.get('description', '').strip()
    industry = data.get('industry', '').strip()
    
    if not startup_description:
        return error_response('Please provide a startup description', 400)
    
    try:
        system_prompt = (
            "You are a startup HR consultant. "
            "Based on the startup description and industry, suggest key team roles needed. "
            "Return ONLY valid JSON with no markdown.\n\n"
            "Schema:\n"
            "{\n"
            '  "roles": {\n'
            '    "role_name": {"positionsNumber": number}\n'
            '  }\n'
            "}"
        )
        
        user_prompt = (
            f"Suggest team roles for this startup:\n"
            f"Industry: {industry}\n"
            f"Description: {startup_description}\n\n"
            f"Suggest 3-5 key roles with position counts."
        )
        
        response_text, tokens_used = get_response(
            model="qwen/qwen3-32b",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=512
        )
        
        try:
            roles_data = json.loads(response_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                roles_data = json.loads(json_match.group())
            else:
                return error_response('Failed to parse role suggestions', 500)
        
        return success_response({
            'roles': roles_data.get('roles', {}),
            'tokens_used': tokens_used
        })
        
    except Exception as e:
        print(f"❌ [AI_SUGGEST_ROLES] Error: {str(e)}")
        return error_response(f'Failed to suggest roles: {str(e)}', 500)