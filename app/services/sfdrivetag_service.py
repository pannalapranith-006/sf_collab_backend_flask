from app.models.sfdrive_tag import Tag
from app.models.sfdrive_file import SFFile
from app import db


def add_tags(file_id, tags):

    file = SFFile.query.get(file_id)

    if not file:
        return {"error": "File not found"}, 404

    created_tags = []

    try:

        for tag_name in tags:

            tag_name = tag_name.strip().lower()

            if not tag_name:
                continue

            existing_tag = Tag.query.filter_by(
                file_id=file_id,
                tag_name=tag_name
            ).first()

            if existing_tag:
                continue

            tag = Tag(
                file_id=file_id,
                tag_name=tag_name,
                tag_type='manual'
            )

            db.session.add(tag)

            created_tags.append(tag_name)

        db.session.commit()

        return {
            "message": "Tags added successfully",
            "tags": created_tags
        }, 201

    except Exception as e:

        db.session.rollback()

        return {"error": str(e)}, 500


def get_file_tags(file_id):
    file = SFFile.query.get(file_id)

    if not file:
        return {"error": "File not found"}, 404

    tags = Tag.query.filter_by(file_id=file_id).all()

    return {
        "file_id": file_id,
        "tags": [
            {
                "id": tag.id,
                "tag_name": tag.tag_name,
                "tag_type": tag.tag_type
            }
            for tag in tags
        ]
    }, 200

def generate_system_tags(file):

    generated_tags = []

    filename = file.file_name.lower()

    if "roadmap" in filename:
        generated_tags.append("roadmap")

    if "spec" in filename:
        generated_tags.append("technical-spec")

    if filename.endswith(".pdf"):
        generated_tags.append("pdf")

    try:

        for tag_name in generated_tags:

            existing_tag = Tag.query.filter_by(
                file_id=file.id,
                tag_name=tag_name
            ).first()

            if existing_tag:
                continue

            tag = Tag(
                file_id=file.id,
                tag_name=tag_name,
                tag_type='system'
            )

            db.session.add(tag)

        db.session.commit()

        return generated_tags

    except Exception as e:

        db.session.rollback()

        return []