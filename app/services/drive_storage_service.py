import hashlib
import mimetypes
import os
import uuid as _uuid
from pathlib import Path
from typing import IO
from flask import current_app

ALLOWED_MIME_PREFIXES = {
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml": "xlsx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml": "pptx",
    "application/zip": "zip",
    "application/json": "json",
    "application/xml": "xml",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "text/html": "html",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/gif": "gif",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/ogg": "ogg",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/ogg": "ogv",
}

DEFAULT_MAX_BYTES = 200 * 1024 * 1024  # 200 MB

class StorageError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _storage_root() -> Path:
    root = Path(current_app.config.get("DRIVE_STORAGE_ROOT", "drive_storage"))
    root.mkdir(parents=True, exist_ok=True)
    return root

def _resolve_mime(filename: str, declared: str | None) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    if declared and declared != "application/octet-stream":
        return declared.split(";")[0].strip()
    if guessed:
        return guessed
    return "application/octet-stream"

def _assert_mime_allowed(mime: str) -> None:
    for prefix in ALLOWED_MIME_PREFIXES:
        if mime.startswith(prefix):
            return
    raise StorageError(f"File type '{mime}' is not permitted.", 415)

def _extension_for(filename: str, mime: str) -> str:
    _, dot_ext = os.path.splitext(filename)
    if dot_ext:
        return dot_ext.lstrip(".").lower()
    for prefix, label in ALLOWED_MIME_PREFIXES.items():
        if mime.startswith(prefix):
            return label
    return "bin"


def save_upload(file_stream: IO[bytes], original_filename: str,
                declared_mime: str | None, owner_scope_type: str,
                owner_scope_id: str) -> dict:
    root = _storage_root()
    max_bytes = current_app.config.get("DRIVE_MAX_UPLOAD_BYTES", DEFAULT_MAX_BYTES)

    mime = _resolve_mime(original_filename, declared_mime)
    _assert_mime_allowed(mime)

    ext = _extension_for(original_filename, mime)
    file_id = str(_uuid.uuid4())
    rel_dir = os.path.join(owner_scope_type, str(owner_scope_id))
    rel_path = os.path.join(rel_dir, f"{file_id}.{ext}")
    abs_dir = root / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    abs_path = root / rel_path

    sha256 = hashlib.sha256()
    size = 0
    chunk_size = 64 * 1024

    try:
        with open(abs_path, "wb") as dest:
            while True:
                chunk = file_stream.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    dest.close()
                    abs_path.unlink(missing_ok=True)
                    raise StorageError(f"File exceeds maximum allowed size of {max_bytes // (1024*1024)} MB.", 413)
                sha256.update(chunk)
                dest.write(chunk)
    except StorageError:
        raise
    except OSError as exc:
        raise StorageError(f"Storage write failed: {exc}", 500)

    if size == 0:
        abs_path.unlink(missing_ok=True)
        raise StorageError("Uploaded file is empty.", 400)

    return {
        "storage_key": rel_path,
        "size_bytes": size,
        "checksum": sha256.hexdigest(),
        "mime_type": mime,
        "extension": ext,
    }


def open_for_download(storage_key: str):
    abs_path = _storage_root() / storage_key
    if not abs_path.exists():
        raise StorageError("File not found in storage.", 404)
    try:
        return open(abs_path, "rb")
    except OSError as exc:
        raise StorageError(f"Cannot open file: {exc}", 500)


def delete_from_storage(storage_key: str) -> bool:
    abs_path = _storage_root() / storage_key
    try:
        abs_path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        current_app.logger.warning("Could not delete storage file %s: %s", storage_key, exc)
        return False


def get_absolute_path(storage_key: str) -> Path:
    return _storage_root() / storage_key
