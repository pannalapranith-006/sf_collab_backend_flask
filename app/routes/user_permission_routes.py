from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.userPermission import UserPermission
from app.models.permission import Permission
# app.models.activity (old audit log) removed — no workspace_id context here
from app.extensions import db
from datetime import datetime
from app.utils.helper import error_response, success_response, paginate

user_permissions_bp = Blueprint('user_permissions', __name__)


@user_permissions_bp.route('', methods=['GET'])
@jwt_required()
def get_user_permissions():
    """Get all user permissions with filtering"""
    current_user_id = get_jwt_identity()
    
    page          = request.args.get('page', 1, type=int)
    per_page      = request.args.get('per_page', 20, type=int)
    user_id       = request.args.get('user_id', type=int)
    permission_id = request.args.get('permission_id', type=int)
    only_active   = request.args.get('only_active', 'false').lower() == 'true'
    
    query = UserPermission.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if permission_id:
        query = query.filter_by(permission_id=permission_id)
    
    if only_active:
        now = datetime.utcnow()
        query = query.filter(
            (UserPermission.starts_at == None) | (UserPermission.starts_at <= now),
            (UserPermission.expires_at == None) | (UserPermission.expires_at > now)
        )
    
    result = paginate(query, page, per_page)
    
    return success_response({
        'user_permissions': [up.to_dict(include_user_info=True) for up in result['items']],
        'pagination': {
            'page':     result['page'],
            'per_page': result['per_page'],
            'total':    result['total'],
            'pages':    result['pages'],
        }
    })


@user_permissions_bp.route('/<int:user_permission_id>', methods=['GET'])
@jwt_required()
def get_user_permission(user_permission_id):
    """Get single user permission by ID"""
    user_permission = UserPermission.query.get(user_permission_id)
    if not user_permission:
        return error_response('User permission not found', 404)
    
    return success_response({
        'user_permission': user_permission.to_dict(include_user_info=True)
    })


@user_permissions_bp.route('', methods=['POST'])
@jwt_required()
def create_user_permission():
    """Grant one or multiple permissions to a user"""
    current_user_id = get_jwt_identity()
    
    data = request.get_json()
    
    if 'user_id' not in data:
        return error_response('Missing required field: user_id')
    
    permission_ids = data.get('permission_id') or data.get('permission_ids')
    if not permission_ids:
        return error_response('Missing required field: permission_id or permission_ids')
    
    if isinstance(permission_ids, int):
        permission_ids = [permission_ids]
    elif not isinstance(permission_ids, list):
        return error_response('permission_ids must be a list of integers')
    
    granted_permissions = []
    errors              = []

    for pid in permission_ids:
        permission = Permission.query.get(pid)
        if not permission:
            errors.append(f'Permission {pid} not found')
            continue
        
        existing = UserPermission.query.filter_by(
            user_id=data['user_id'],
            permission_id=pid
        ).first()
        
        if existing:
            errors.append(f'User already has permission {permission.key}')
            continue
        
        try:
            user_permission = UserPermission(
                user_id=data['user_id'],
                permission_id=pid,
                granted_by=current_user_id,
                starts_at=datetime.fromisoformat(data['starts_at']) if 'starts_at' in data and data['starts_at'] else None,
                expires_at=datetime.fromisoformat(data['expires_at']) if 'expires_at' in data and data['expires_at'] else None,
            )
            db.session.add(user_permission)
            granted_permissions.append(user_permission)

            # FIX: Activity.log removed — no workspace_id context in auth routes
            print(f"[user_permissions] permission_granted: user_id={data['user_id']} permission={permission.key} by={current_user_id}")

        except Exception as e:
            errors.append(f"Failed to grant permission {pid}: {str(e)}")
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to grant permissions: {str(e)}', 500)
    
    return success_response({
        'granted_permissions': [up.to_dict(include_user_info=True) for up in granted_permissions],
        'errors': errors,
    }, 'Permissions processed successfully', 201)


@user_permissions_bp.route('/<int:user_permission_id>', methods=['PUT'])
@jwt_required()
def update_user_permission(user_permission_id):
    """Update user permission"""
    current_user_id = get_jwt_identity()
    
    user_permission = UserPermission.query.get(user_permission_id)
    if not user_permission:
        return error_response('User permission not found', 404)
    
    data = request.get_json()
    
    try:
        if 'starts_at' in data:
            user_permission.starts_at = datetime.fromisoformat(data['starts_at']) if data['starts_at'] else None
        
        if 'expires_at' in data:
            user_permission.expires_at = datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None
        
        db.session.commit()

        # FIX: Activity.log removed — no workspace_id context in auth routes
        print(f"[user_permissions] permission_updated: permission={user_permission.permission.key} user_id={user_permission.user_id} by={current_user_id}")

        return success_response({
            'user_permission': user_permission.to_dict(include_user_info=True)
        }, 'User permission updated successfully')

    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to update user permission: {str(e)}', 500)


@user_permissions_bp.route('/<int:user_permission_id>', methods=['DELETE'])
@jwt_required()
def delete_user_permission(user_permission_id):
    """Revoke user permission"""
    current_user_id = get_jwt_identity()
    
    user_permission = UserPermission.query.get(user_permission_id)
    if not user_permission:
        return error_response('User permission not found', 404)
    
    try:
        permission_key = user_permission.permission.key if user_permission.permission else 'unknown'
        target_user_id = user_permission.user_id
        
        db.session.delete(user_permission)
        db.session.commit()

        # FIX: Activity.log removed — no workspace_id context in auth routes
        print(f"[user_permissions] permission_revoked: permission={permission_key} user_id={target_user_id} by={current_user_id}")

        return success_response(message='User permission revoked successfully')

    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to revoke user permission: {str(e)}', 500)


@user_permissions_bp.route('/check', methods=['GET'])
@jwt_required()
def check_user_permission():
    """Check if user has specific permission"""
    current_user_id = get_jwt_identity()
    
    user_id        = request.args.get('user_id', current_user_id, type=int)
    permission_key = request.args.get('permission_key', type=str)
    
    if not permission_key:
        return error_response('Missing permission_key parameter', 400)
    
    permission = Permission.query.filter_by(key=permission_key).first()
    if not permission:
        return error_response('Permission not found', 404)
    
    user_permission = UserPermission.query.filter_by(
        user_id=user_id,
        permission_id=permission.id
    ).first()
    
    has_permission = False
    is_active      = False
    
    if user_permission:
        has_permission = True
        is_active      = user_permission.is_active()
    
    return success_response({
        'has_permission': has_permission,
        'is_active':      is_active,
        'permission':     permission.to_dict(),
        'user_permission': user_permission.to_dict() if user_permission else None,
    })