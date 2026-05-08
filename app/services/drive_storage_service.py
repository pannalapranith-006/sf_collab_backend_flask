"""
app/services/drive_storage_service.py

Handles the physical file I/O for SF Drive.

Currently stores files on the local filesystem under DRIVE_STORAGE_ROOT
(configured in app config, defaults to ./drive_storage/).

Swap this module's internals for an S3/GCS client when ready — the routes
and model never need to change.
"""

import hashlib
import mimetypes
import os
import shutil
from pathlib import Path
from typing import IO

from flask import current_app


# ── MIME type allowlist ───────────────────────────────────────────────────────
# Maps mime prefix → human label.  Anything not in this map is rejected.
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
    "application/yaml": "yaml",
    "application/x-yaml": "yaml",
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

# Maximum upload size in bytes (default 200 MB).
# Override with DRIVE_MAX_UPLOAD_BYTES in app config.
DEFAULT_MAX_BYTES = 200 * 1024 * 1024  # 200 MB


class StorageError(Exception):
    """Raised for any storage-layer failure (validation, IO, etc.)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ── Public API ────────────────────────────────────────────────────────────────

def save_upload(
    file_stream: IO[bytes],
    original_filename: str,
    declared_mime: str | None,
    owner_scope_type: str,
    owner_scope_id: str,
) -> dict:
    """
    Validate and persist an uploaded file stream.

    Parameters
    ----------
    file_stream        : Werkzeug FileStorage or any readable binary stream
    original_filename  : filename as reported by the client
    declared_mime      : Content-Type reported by the client (may be None)
    owner_scope_type   : "user" | "startup" | "organization" | "system"
    owner_scope_id     : UUID string of the owning entity

    Returns
    -------
    dict with keys:
        storage_key  – relative path used as the stable DB key
        size_bytes   – actual byte count written
        checksum     – sha256 hex digest
        mime_type    – resolved MIME type
        extension    – file extension (without leading dot)
    """
    root = _storage_root()
    max_bytes = current_app.config.get("DRIVE_MAX_UPLOAD_BYTES", DEFAULT_MAX_BYTES)

    # ── 1. Resolve and validate MIME ─────────────────────────────────────────
    mime = _resolve_mime(original_filename, declared_mime)
    _assert_mime_allowed(mime)

    # ── 2. Build destination path ────────────────────────────────────────────
    #   Layout: <root>/<scope_type>/<scope_id>/<uuid4>.<ext>
    import uuid as _uuid
    ext = _extension_for(original_filename, mime)
    file_id = str(_uuid.uuid4())
    rel_dir = os.path.join(owner_scope_type, str(owner_scope_id))
    rel_path = os.path.join(rel_dir, f"{file_id}.{ext}")
    abs_dir = root / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    abs_path = root / rel_path

    # ── 3. Stream to disk, enforce size limit, compute checksum ─────────────
    sha256 = hashlib.sha256()
    size = 0
    chunk_size = 64 * 1024  # 64 KB

    try:
        with open(abs_path, "wb") as dest:
            while True:
                chunk = file_stream.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    # Clean up partial file before raising
                    dest.close()
                    abs_path.unlink(missing_ok=True)
                    raise StorageError(
                        f"File exceeds maximum allowed size of "
                        f"{max_bytes // (1024 * 1024)} MB.",
                        status_code=413,
                    )
                sha256.update(chunk)
                dest.write(chunk)
    except StorageError:
        raise
    except OSError as exc:
        raise StorageError(f"Storage write failed: {exc}", status_code=500)

    if size == 0:
        abs_path.unlink(missing_ok=True)
        raise StorageError("Uploaded file is empty.", status_code=400)

    return {
        "storage_key": rel_path,          # stored in DB
        "size_bytes": size,
        "checksum": sha256.hexdigest(),
        "mime_type": mime,
        "extension": ext,
    }


def open_for_download(storage_key: str):
    """
    Return an open binary file handle for the given storage_key.

    The caller is responsible for closing it (Flask's send_file does this).

    Raises StorageError(404) if the file is missing from disk.
    """
    abs_path = _storage_root() / storage_key
    if not abs_path.exists():
        raise StorageError("File not found in storage.", status_code=404)
    try:
        return open(abs_path, "rb")  # noqa: SIM115 — caller owns lifecycle
    except OSError as exc:
        raise StorageError(f"Cannot open file: {exc}", status_code=500)


def delete_from_storage(storage_key: str) -> bool:
    """
    Remove the file from disk.  Returns True if deleted, False if already gone.
    Does not raise — missing files are treated as already deleted.
    """
    abs_path = _storage_root() / storage_key
    try:
        abs_path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        # Log but don't crash the soft-delete DB transaction
        current_app.logger.warning("Could not delete storage file %s: %s", storage_key, exc)
        return False


def get_absolute_path(storage_key: str) -> Path:
    """Return the absolute filesystem path for a storage key."""
    return _storage_root() / storage_key


# ── Private helpers ───────────────────────────────────────────────────────────

def _storage_root() -> Path:
    root = Path(current_app.config.get("DRIVE_STORAGE_ROOT", "drive_storage"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_mime(filename: str, declared: str | None) -> str:
    """Pick the best MIME type from filename + declared value."""
    guessed, _ = mimetypes.guess_type(filename)
    # Prefer the client-declared type when it is more specific than the guess,
    # but fall back to the guess if the client sent nothing or sent octet-stream.
    if declared and declared != "application/octet-stream":
        return declared.split(";")[0].strip()   # strip charset etc.
    if guessed:
        return guessed
    return "application/octet-stream"


def _assert_mime_allowed(mime: str) -> None:
    for prefix in ALLOWED_MIME_PREFIXES:
        if mime.startswith(prefix):
            return
    raise StorageError(
        f"File type '{mime}' is not permitted. "
        f"Allowed types include PDF, Word, Excel, images, audio, video, and text files.",
        status_code=415,
    )


def _extension_for(filename: str, mime: str) -> str:
    """Derive a clean extension: prefer the original filename, fall back to mime."""
    _, dot_ext = os.path.splitext(filename)
    if dot_ext:
        return dot_ext.lstrip(".").lower()
    # Try to get from mime map
    for prefix, label in ALLOWED_MIME_PREFIXES.items():
        if mime.startswith(prefix):
            return label
    return "bin"
