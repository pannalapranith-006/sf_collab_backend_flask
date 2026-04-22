# utils/auth.py
# SFCollab ERP — Auth helpers
# JWT claim extraction + route-level admin guard

from __future__ import annotations

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt


def get_jwt_claims() -> tuple[int, str, int]:
    """
    Extract (workspace_id, role, user_id) from the current JWT.
    Raises ValueError if any required claim is missing.
    """
    claims = get_jwt()
    workspace_id = claims.get("workspace_id")
    role         = claims.get("role")
    user_id      = claims.get("user_id") or claims.get("sub")

    if workspace_id is None:
        raise ValueError("JWT missing workspace_id claim")
    if role is None:
        raise ValueError("JWT missing role claim")
    if user_id is None:
        raise ValueError("JWT missing user_id/sub claim")

    return int(workspace_id), role, int(user_id)


def admin_required(fn):
    """Route decorator — rejects non-admin callers with 403."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            _, role, _ = get_jwt_claims()
        except ValueError as e:
            # Missing claim is a bad request, not an auth failure
            return jsonify({"error": str(e)}), 400
        except Exception:
            return jsonify({"error": "Authentication failed"}), 401
        if role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return fn(*args, **kwargs)
    return wrapper