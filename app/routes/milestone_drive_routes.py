"""
Routes for attaching proof files to milestones.
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.drive_file import DriveFile
from app.models.drive_file_relation import DriveFileRelation
from app.utils.response_helpers import success_response, error_response

milestone_drive_bp = Blueprint('milestone_drive', __name__, url_prefix='/api/milestones')

@milestone_drive_bp.route('/<int:milestone_id>/files', methods=['POST'])
@jwt_required()
def attach_file_to_milestone(milestone_id):
    """
    Attach one or more files to a milestone as proof.
    Body: { "file_ids": [1,2,3], "mark_canonical": true }
    """
    current_user_id = int(get_jwt_identity())
    body = request.get_json(silent=True) or {}
    file_ids = body.get('file_ids', [])
    mark_canonical = body.get('mark_canonical', False)

    if not file_ids or not isinstance(file_ids, list):
        return error_response("'file_ids' (list) is required", 400)

    linked = []
    for fid in file_ids:
        file = DriveFile.query.get(fid)
        if not file or file.state == 'deleted':
            continue

        # Avoid duplicate
        existing = DriveFileRelation.query.filter_by(
            file_id=fid, relation_type='milestone', related_entity_id=milestone_id
        ).first()
        if existing:
            linked.append(existing.file_id)
            continue

        rel = DriveFileRelation(
            file_id=fid,
            relation_type='milestone',
            related_entity_id=milestone_id,
            related_entity_type='milestone',
            created_by_user_id=current_user_id
        )
        db.session.add(rel)

        # Denormalised linkage
        if not file.linked_milestone_ids:
            file.linked_milestone_ids = []
        if milestone_id not in file.linked_milestone_ids:
            file.linked_milestone_ids.append(milestone_id)

        if mark_canonical:
            # Mark this file as canonical proof for the milestone
            # (you might have a separate canonicality flag; here we use a tag)
            if not file.tags_json:
                file.tags_json = []
            if 'canonical-proof' not in file.tags_json:
                file.tags_json.append('canonical-proof')

        linked.append(fid)

    db.session.commit()
    return success_response({
        'message': f'Attached {len(linked)} file(s) to milestone {milestone_id}',
        'linked_file_ids': linked
    }, 201)


@milestone_drive_bp.route('/<int:milestone_id>/files', methods=['GET'])
@jwt_required()
def list_milestone_files(milestone_id):
    """Return all files linked to this milestone."""
    relations = DriveFileRelation.query.filter_by(
        relation_type='milestone',
        related_entity_id=milestone_id
    ).all()
    file_ids = [r.file_id for r in relations]

    if not file_ids:
        return success_response([])

    files = DriveFile.query.filter(
        DriveFile.file_id.in_(file_ids),
        DriveFile.state != 'deleted'
    ).all()

    return success_response([f.to_dict() for f in files])


@milestone_drive_bp.route('/<int:milestone_id>/files/<int:file_id>', methods=['DELETE'])
@jwt_required()
def detach_file_from_milestone(milestone_id, file_id):
    """Remove a file from a milestone."""
    current_user_id = int(get_jwt_identity())
    rel = DriveFileRelation.query.filter_by(
        file_id=file_id, relation_type='milestone', related_entity_id=milestone_id
    ).first()
    if not rel:
        return error_response("Link not found", 404)

    file = DriveFile.query.get(file_id)
    if file and file.linked_milestone_ids:
        file.linked_milestone_ids = [m for m in file.linked_milestone_ids if m != milestone_id]
        # Remove canonical tag if present
        if 'canonical-proof' in (file.tags_json or []):
            file.tags_json.remove('canonical-proof')

    db.session.delete(rel)
    db.session.commit()
    return success_response({'message': 'File detached from milestone'})