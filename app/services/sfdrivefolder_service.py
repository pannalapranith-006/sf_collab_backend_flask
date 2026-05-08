from app.models.sfdrivefolder import Folder
from app.models.sfdrive_file import SFFile
from app import db


def create_folder(name, workspace_id, parent_id, user_id):
    if not name or not workspace_id:
        return {"error": "name and workspace_id required"}, 400

    folder = Folder(
        name=name,
        workspace_id=workspace_id,
        parent_id=parent_id,
        created_by=user_id
    )

    db.session.add(folder)
    db.session.commit()

    return {"message": "Folder created successfully", "folder_id": folder.id}, 201


def get_folder_contents(folder_id, workspace_id):
    folders = Folder.query.filter_by(
        parent_id=folder_id,
        workspace_id=workspace_id
    ).all()

    files = SFFile.query.filter_by(
        folder_id=folder_id,
        workspace_id=workspace_id
    ).all()

    return {
        "folders": [
            {"id": f.id, "name": f.name}
            for f in folders
        ],
        "files": [
            {"id": d.id, "file_name": d.file_name}
            for d in files
        ]
    }, 200


def move_file(doc_id, new_folder_id, user_id):
    doc = SFFile.query.get(doc_id)

    if not doc:
        return {"error": "File not found"}, 404

    if doc.uploaded_by != user_id:
        return {"error": "Unauthorized"}, 403

    folder = Folder.query.get(new_folder_id)
    if not folder:
        return {"error": "Folder not found"}, 404

    if doc.workspace_id != folder.workspace_id:
        return {"error": "Workspace mismatch"}, 400

    doc.folder_id = new_folder_id
    db.session.commit()

    return {"message": "File moved successfully"}, 200