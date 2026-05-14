from datetime import datetime
import hashlib

#Upload a file
def generate_checksum(file):
    return hashlib.md5(file.read()).hexdigest()

@file_version_bp.route("/files/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")

    if not file:
        return {"error": "No file"}, 400

    checksum = generate_checksum(file)
    file.seek(0)

    new_file = DriveFile(
        filename=file.filename,
        version_number=1,
        checksum=checksum,
        uploaded_at=datetime.utcnow()
    )

    db.session.add(new_file)
    db.session.commit()

    return {
        "file_id": new_file.id,
        "version": new_file.version_number
    }

#Upload New version

@file_version_bp.route("/files/<int:file_id>/version", methods=["POST"])
def upload_new_version(file_id):
    file = request.files.get("file")

    file_obj = DriveFile.query.get(file_id)

    if not file_obj:
        return {"error": "File not found"}, 404

    checksum = generate_checksum(file)
    file.seek(0)

    # 🚀 VERSION INCREMENT

    file_obj.uploaded_at = datetime.utcnow()

    db.session.commit()

    return {
        "file_id": file_id,
        "new_version": file_obj.version_number
    }
#Get File (Latest State)

@file_version_bp.route("/files/<int:file_id>", methods=["GET"])
def get_file(file_id):
    file_obj = DriveFile.query.get(file_id)

    if not file_obj:
        return {"error": "Not found"}, 404

    return {
        "file_id": file_id,
        "filename": file_obj.filename,
        "version": file_obj.version_number,
        "checksum": file_obj.checksum,
        "uploaded_at": file_obj.uploaded_at,
        "indexed_at": file_obj.indexed_at
    }

#4. Mark File as Indexed

@file_version_bp.route("/files/<int:file_id>/index", methods=["POST"])
def mark_indexed(file_id):
    file_obj = DriveFile.query.get(file_id)

    if not file_obj:
        return {"error": "Not found"}, 404

    file_obj.indexed_at = datetime.utcnow()
    db.session.commit()

    return {"message": "File indexed successfully"}