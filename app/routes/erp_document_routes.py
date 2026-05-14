import os
from datetime import datetime
from uuid import uuid4

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.erp_document import ErpDocument
from app.models.workspace import Workspace
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user,
    get_current_user_id,
    get_workspace_membership,
    is_global_admin,
)


erp_documents_bp = Blueprint('erp_documents', __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
ERP_UPLOAD_ROOT = os.path.join(BASE_DIR, 'uploads', 'erp_documents')
os.makedirs(ERP_UPLOAD_ROOT, exist_ok=True)


def _sanitize_folder(raw):
    folder = (raw or '').strip()
    if not folder:
        return 'general'

    parts = [secure_filename(part) for part in folder.replace('\\', '/').split('/') if part and part not in ('.', '..')]
    clean = '/'.join(part for part in parts if part)
    return clean or 'general'


def _parse_workspace_id(source='form'):
    if source == 'form':
        raw = request.form.get('workspace_id')
    else:
        raw = request.args.get('workspace_id')

    if raw is None:
        return None, error_response('workspace_id is required', 400)

    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, error_response('workspace_id must be an integer', 400)


def _assert_workspace_exists(workspace_id):
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        return None, error_response('Workspace not found', 404)
    return workspace, None


def _assert_member_access(workspace_id, user_id, user):
    membership = get_workspace_membership(workspace_id, user_id)
    if membership or is_global_admin(user):
        return membership, None
    return None, error_response('Unauthorized to access this workspace', 403)


def _assert_admin_access(workspace_id, user_id, user):
    membership = get_workspace_membership(workspace_id, user_id)
    role = membership.role.value if (membership and hasattr(membership.role, 'value')) else (membership.role if membership else None)
    if role == 'admin' or is_global_admin(user):
        return membership, None
    return None, error_response('Admin access required', 403)


@erp_documents_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_document():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    workspace_id, err = _parse_workspace_id('form')
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    _, err = _assert_member_access(workspace_id, user_id, user)
    if err:
        return err

    upload = request.files.get('file')
    if not upload or not upload.filename:
        return error_response('file is required', 400)

    folder = _sanitize_folder(request.form.get('folder'))
    original_filename = upload.filename
    safe_original = secure_filename(original_filename)
    if not safe_original:
        return error_response('Invalid file name', 400)

    suffix = os.path.splitext(safe_original)[1]
    stored_filename = f'{uuid4().hex}{suffix}'

    target_dir = os.path.join(ERP_UPLOAD_ROOT, str(workspace_id), folder)
    os.makedirs(target_dir, exist_ok=True)

    abs_path = os.path.join(target_dir, stored_filename)
    upload.save(abs_path)

    rel_path = os.path.relpath(abs_path, BASE_DIR).replace('\\', '/')

    file_size = None
    try:
        file_size = os.path.getsize(abs_path)
    except OSError:
        file_size = None

    document = ErpDocument(
        workspace_id=workspace_id,
        uploaded_by=user_id,
        file_path=rel_path,
        folder=folder,
        original_filename=original_filename,
        stored_filename=stored_filename,
        content_type=upload.content_type,
        file_size=file_size,
    )

    try:
        db.session.add(document)
        db.session.commit()
        return success_response({'document': document.to_dict()}, 'Document uploaded', 201)
    except Exception as exc:
        db.session.rollback()
        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
        except OSError:
            pass
        return error_response(f'Failed to upload document: {exc}', 500)


@erp_documents_bp.route('/list', methods=['GET'])
@jwt_required()
def list_documents():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    workspace_id, err = _parse_workspace_id('args')
    if err:
        return err

    _, err = _assert_workspace_exists(workspace_id)
    if err:
        return err

    _, err = _assert_member_access(workspace_id, user_id, user)
    if err:
        return err

    folder_filter = request.args.get('folder')

    query = ErpDocument.query.filter_by(workspace_id=workspace_id)
    if folder_filter:
        query = query.filter_by(folder=_sanitize_folder(folder_filter))

    records = query.order_by(ErpDocument.created_at.desc()).all()

    return success_response({
        'workspace_id': workspace_id,
        'count': len(records),
        'documents': [r.to_dict() for r in records],
    })


@erp_documents_bp.route('/<int:document_id>', methods=['DELETE'])
@jwt_required()
def delete_document(document_id):
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    user = get_current_user()
    if not user:
        return error_response('User not found', 404)

    document = ErpDocument.query.get(document_id)
    if not document:
        return error_response('Document not found', 404)

    membership, err = _assert_member_access(document.workspace_id, user_id, user)
    if err:
        return err

    role = membership.role.value if (membership and hasattr(membership.role, 'value')) else (membership.role if membership else None)
    can_delete = document.uploaded_by == user_id or role == 'admin' or is_global_admin(user)
    if not can_delete:
        return error_response('Unauthorized to delete this document', 403)

    abs_path = os.path.join(BASE_DIR, document.file_path)

    try:
        deleted = document.to_dict()
        db.session.delete(document)
        db.session.commit()

        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
        except OSError:
            pass

        return success_response({'document': deleted}, 'Document deleted')
    except Exception as exc:
        db.session.rollback()
        return error_response(f'Failed to delete document: {exc}', 500)
