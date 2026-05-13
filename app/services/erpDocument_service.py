import os
from werkzeug.utils import secure_filename
from flask import send_file
from app.models.erpDocumentStorage import Document
from app import db

UPLOAD_FOLDER = "uploads"


def handle_upload(file, workspace_id, folder, user_id):
    if not workspace_id:
        return {"error": "workspace_id is required"}, 400

    filename = secure_filename(file.filename)

    try:
        path = os.path.join(UPLOAD_FOLDER, str(workspace_id), folder)
        os.makedirs(path, exist_ok=True)

        file_path = os.path.join(path, filename)
        file.save(file_path)

        doc = Document(
            workspace_id=workspace_id,
            uploaded_by=user_id,
            file_name=filename,
            file_path=file_path,
            folder=folder
        )

        db.session.add(doc)
        db.session.commit()

        return {"message": "File uploaded successfully"}, 201

    except Exception as e:
        return {"error": str(e)}, 500


def get_documents(workspace_id):
    if not workspace_id:
        return {"error": "workspace_id is required"}, 400

    docs = Document.query.filter_by(workspace_id=workspace_id).all()

    return [
        {
            "id": d.id,
            "file_name": d.file_name,
            "file_path": d.file_path,
            "folder": d.folder,
            "uploaded_by": d.uploaded_by,
            "created_at": d.created_at
        }
        for d in docs
    ], 200

def download_document(doc_id, user_id):
    doc = Document.query.get(doc_id)

    if not doc:
        return {"error": "Document not found"}, 404

    # Optional security check
    if doc.uploaded_by != user_id:
        return {"error": "Unauthorized"}, 403

    if not os.path.exists(doc.file_path):
        return {"error": "File not found on server"}, 404

    try:
        return send_file(
            doc.file_path,
            as_attachment=True,
            download_name=doc.file_name
        )
    except Exception as e:
        return {"error": str(e)}, 500

def remove_document(doc_id, user_id):
    doc = Document.query.get(doc_id)

    if not doc:
        return {"error": "Document not found"}, 404

    if doc.uploaded_by != user_id:
        return {"error": "Unauthorized"}, 403

    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        db.session.delete(doc)
        db.session.commit()

        return {"message": "Deleted successfully"}, 200

    except Exception as e:
        return {"error": str(e)}, 500