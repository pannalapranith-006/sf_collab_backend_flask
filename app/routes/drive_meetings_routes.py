from flask import Blueprint, request, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.drive_file import DriveFile
from app.models.drive_file_relation import DriveFileRelation
from app.routes.drive_file_relation_routes import _sync_denorm
from app.services.drive_event_service import emit_event
from app.utils.response_helpers import success_response, error_response

drive_meetings_bp = Blueprint(
    "drive_meetings",
    __name__,
    url_prefix="/api/drive/meetings"
)

RELATION_TYPE = "meeting"
ENTITY_TYPE = "meeting"


def _safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@drive_meetings_bp.post("/<int:meeting_id>/files")
@jwt_required()
def link_files_to_meeting(meeting_id):
    current_user_id = int(get_jwt_identity())
    body = request.get_json() or {}
    file_ids = body.get("file_ids", [])

    if not file_ids or not isinstance(file_ids, list):
        return error_response("'file_ids' must be a list", 400)

    created = []

    for fid in file_ids:
        file_id_int = _safe_int(fid)
        if not file_id_int:
            continue

        file = DriveFile.query.get(file_id_int)
        if not file or file.state == "deleted":
            continue

        # prevent duplicate
        existing = DriveFileRelation.query.filter_by(
            file_id=file_id_int,
            relation_type=RELATION_TYPE,
            related_entity_type=ENTITY_TYPE,
            related_entity_id=meeting_id
        ).first()

        if existing:
            continue

        rel = DriveFileRelation(
            file_id=file_id_int,
            relation_type=RELATION_TYPE,
            related_entity_type=ENTITY_TYPE,
            related_entity_id=meeting_id
        )

        db.session.add(rel)
        _sync_denorm(file, RELATION_TYPE, meeting_id, add=True)
        created.append(file_id_int)

    db.session.commit()
    emit_event("file_linked_to_meeting", file_id_int, current_user_id, event_metadata={"meeting_id": meeting_id})

    return success_response({
        "message": "Files linked to meeting",
        "linked_file_ids": created
    }, 201)


@drive_meetings_bp.get("/<int:meeting_id>/files")
@jwt_required()
def get_meeting_files(meeting_id):
    current_user_id = int(get_jwt_identity())

    relations = DriveFileRelation.query.filter_by(
        relation_type=RELATION_TYPE,
        related_entity_type=ENTITY_TYPE,
        related_entity_id=meeting_id
    ).all()

    file_ids = [r.file_id for r in relations]

    if not file_ids:
        return success_response([])

    files = DriveFile.query.filter(
        DriveFile.id.in_(file_ids),
        DriveFile.state != "deleted"
    ).all()

    return success_response([f.to_dict() for f in files])


@drive_meetings_bp.delete("/<int:meeting_id>/files/<int:file_id>")
@jwt_required()
def unlink_file_from_meeting(meeting_id, file_id):
    current_user_id = int(get_jwt_identity())

    rel = DriveFileRelation.query.filter_by(
        file_id=file_id,
        relation_type=RELATION_TYPE,
        related_entity_type=ENTITY_TYPE,
        related_entity_id=meeting_id
    ).first()

    if not rel:
        return error_response("Relation not found", 404)

    

    db.session.delete(rel)
    db.session.commit()

    emit_event("file_unlinked_from_meeting", file_id, current_user_id, event_metadata={"meeting_id": meeting_id})
    
    return success_response({"message": "File unlinked from meeting"})