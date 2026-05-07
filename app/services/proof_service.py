import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from app import db
from app.models.proof import Proof
from app.models.erp_task import ErpTask
from app.services.membership_audit_service import log_membership_action

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {
        'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'
    }

def upload_proof(task_id, user_id, file):
    if not file or file.filename == '':
        raise ValueError('No file provided.')
    if not allowed_file(file.filename):
        raise ValueError('File type not allowed.')

    task = ErpTask.query.get(task_id)
    if not task:
        raise ValueError('Task not found.')

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    relative_path = os.path.join(current_app.config['PROOF_UPLOAD_FOLDER'], unique_name)
    absolute_path = os.path.join(current_app.root_path, relative_path)

    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

    file.save(absolute_path)
    file_size = os.path.getsize(absolute_path)

    proof = Proof(
        task_id=task_id,
        user_id=user_id,
        filename=unique_name,
        original_filename=secure_filename(file.filename),
        file_path=relative_path,
        file_size=file_size,
        mime_type=file.mimetype
    )
    db.session.add(proof)
    db.session.commit()

    log_membership_action(
        'proof_uploaded',
        workspace_id=task.workspace_id,
        details={
            'proof_id': proof.id,
            'task_id': task_id,
            'user_id': user_id,
            'file': unique_name
        }
    )
    return proof

def get_proofs_for_task(task_id):
    return Proof.query.filter_by(task_id=task_id).order_by(Proof.created_at.desc()).all()

def review_proof(proof_id, reviewer_id, status, comment=None):
    if status not in ['approved', 'rejected']:
        raise ValueError("Status must be 'approved' or 'rejected'.")

    proof = Proof.query.get(proof_id)
    if not proof:
        raise ValueError('Proof not found.')

    proof.status = status
    proof.reviewed_by = reviewer_id
    proof.reviewed_at = datetime.utcnow()
    proof.review_comment = comment
    db.session.commit()

    log_membership_action(
        f'proof_{status}',
        workspace_id=proof.task.workspace_id,
        details={
            'proof_id': proof.id,
            'task_id': proof.task_id,
            'reviewer_id': reviewer_id,
            'comment': comment
        }
    )
    return proof