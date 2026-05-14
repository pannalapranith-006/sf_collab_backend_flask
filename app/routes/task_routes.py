"""
Task Routes
-----------
POST /api/workspaces/<workspace_id>/tasks/<task_id>/approve
POST /api/workspaces/<workspace_id>/tasks/<task_id>/reject
"""
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from app.models.task import Task
from app.models.erp_task import ErpTask
from app.models.user import User
from app.models.startUpMember import StartupMember
from app.services.achievement_service import AchievementService
from app.extensions import db
from app.utils.helper import error_response, success_response, paginate
from app.utils.plans_utils import can_create_task_or_milestone
from app.utils.workspace_permissions import get_workspace_membership, is_global_admin
# ===== NOTIFICATION IMPORTS =====
from app.notifications.helpers import (
    notify_task_assigned,
    notify_task_updated,
    notify_task_completed,
    notify_task_overdue,
    notify_task_reassigned,
    notify_task_deadline_approaching
)

logger = logging.getLogger(__name__)

task_bp = Blueprint("tasks", __name__, url_prefix="/api/workspaces")


# ---------------------------------------------------------------------------
# Stubs — replace with your real ORM / auth middleware
# ---------------------------------------------------------------------------

def _get_membership(workspace_id):
    """
    SECURITY NOTE: When replacing this stub, ensure workspace_id is taken
    from the authenticated session token (e.g. g.current_user.workspace_id),
    NOT from the URL parameter. Trusting the URL allows any authenticated
    user to forge membership in a different workspace.
    """
    return {
        # FIX: was getattr(g, "user_role", "admin") — defaulting to admin
        # meant any unauthenticated request had full approval power.
        "role": getattr(g, "user_role", None),
        "user_id": getattr(g, "user_id", None),
        "workspace_id": workspace_id,
    }


def _get_task(workspace_id, task_id):
    """
    Replace with:
        Task.query
            .filter_by(id=task_id, workspace_id=workspace_id)
            .first_or_404()
    Workspace isolation is enforced by the workspace_id filter.
    """
    raise NotImplementedError(
        "Replace _get_task() with your ORM call, e.g.:\n"
        "  Task.query.filter_by(id=task_id, workspace_id=workspace_id).first_or_404()"
    )


def _save(task_id, updates, audit_entry, db_session=None):
    """
    Replace with:
        task = Task.query.get(task_id)
        for k, v in updates.items():
            setattr(task, k, v)
        db.session.add(AuditLog(**audit_entry))
        db.session.commit()
    """
    raise NotImplementedError("Replace with real DB update + commit.")


# ---------------------------------------------------------------------------
# POST /api/workspaces/<workspace_id>/tasks/<task_id>/approve
# ---------------------------------------------------------------------------

@task_bp.route("/<workspace_id>/tasks/<task_id>/approve", methods=["POST"])
def approve(workspace_id, task_id):
    """
    Approve a task and generate execution points.

    Request body (JSON):
    {
        "quality_rating": "accepted" | "good" | "excellent"
    }

    Response 200:
    {
        "message": "Task approved",
        "task_id": "...",
        "status": "approved",
        "approved_points": 18.75,
        "point_breakdown": {
            "base_points": 15,
            "quality_multiplier": 1.0,
            "proof_multiplier": 1.25,
            "deadline_multiplier": 1.0,
            "final_points": 18.75
        }
    }

    Errors:
      400  missing or blank quality_rating
      403  caller is not an admin
      422  task not in DONE status / proof missing / invalid rating
      500  unexpected server error
    """
    body = request.get_json(silent=True) or {}

    # FIX: strip whitespace before validation so " accepted" doesn't pass
    # the presence check and then fail cryptically inside the enum constructor.
    quality_rating = (body.get("quality_rating") or "").strip()

    if not quality_rating:
        return jsonify({"error": "quality_rating is required"}), 400

        # Notify the task creator that someone claimed it (only if different person)
        try:
            if task.user_id and task.user_id != current_user_id:
                claimer_name = get_user_full_name(current_user_id)
                notify_task_assigned(
                    user_id=task.user_id,
                    assigner_id=current_user_id,
                    assigner_name=claimer_name,
                    task_title=task.title,
                    task_id=task.id
                )
        except Exception as e:
            print(f"Claim task notification failed: {e}")

        try:
            task_dict = task.to_dict()
        except Exception as e:
            print(f"task.to_dict() failed: {e}")
            task_dict = {
                'id': task.id,
                'title': task.title,
                'assigned_to': task.assigned_to,
                'status': task.status,
            }

        return success_response({'task': task_dict}, 'Task claimed successfully')
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to claim task: {str(e)}', 500)

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """Delete task"""
    current_user_id = int(get_jwt_identity())

    workspace_id_raw = request.args.get('workspace_id')
    if workspace_id_raw is not None:
        try:
            workspace_id = int(workspace_id_raw)
        except (TypeError, ValueError):
            return error_response('workspace_id must be an integer', 400)

        erp_task = ErpTask.query.filter_by(id=task_id, workspace_id=workspace_id).first()
        if not erp_task:
            return error_response('ERP task not found', 404)

        current_user = User.query.get(current_user_id)
        if not current_user:
            return error_response('User not found', 404)

        membership = get_workspace_membership(workspace_id, current_user_id)
        member_role = membership.role.value if (membership and hasattr(membership.role, 'value')) else (membership.role if membership else None)

        can_delete_erp = (
            erp_task.created_by == current_user_id
            or member_role == 'admin'
            or is_global_admin(current_user)
        )
        if not can_delete_erp:
            return error_response('Unauthorized to delete this ERP task', 403)

        try:
            db.session.delete(erp_task)
            db.session.commit()
            return success_response(message='ERP task deleted successfully')
        except Exception as e:
            db.session.rollback()
            return error_response(f'Failed to delete ERP task: {str(e)}', 500)
    
    task = Task.query.get(task_id)
    if not task:
        return error_response('Task not found', 404)
    
    if task.user_id != current_user_id:
        current_user = User.query.get(current_user_id)
        if not current_user.is_admin():
            return error_response('Unauthorized to delete this task', 403)
    
    try:
        task = _get_task(workspace_id, task_id)
        membership = _get_membership(workspace_id)

        result = approve_task(
            task=task,
            admin_membership=membership,
            quality_rating=quality_rating,
        )

        _save(task_id, result["task_updates"], result["audit_entry"])

        return jsonify({
            "message": "Task approved",
            "task_id": task_id,
            "status": "approved",
            "approved_points": result["task_updates"]["approved_points"],
            "point_breakdown": result["point_breakdown"],
        }), 200

    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception:
        # FIX: log the full exception server-side but do NOT return str(e)
        # to the caller — it can leak DB connection strings, stack traces,
        # or other internal details.
        logger.exception("Unexpected error in approve route task_id=%s", task_id)
        return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# POST /api/workspaces/<workspace_id>/tasks/<task_id>/reject
# ---------------------------------------------------------------------------

@task_bp.route("/<workspace_id>/tasks/<task_id>/reject", methods=["POST"])
def reject(workspace_id, task_id):
    """
    Reject a task. Points are zeroed out.

    Request body (JSON):
    {
        "rejection_reason": "Proof screenshots are broken links."
    }

    Response 200:
    {
        "message": "Task rejected",
        "task_id": "...",
        "status": "rejected",
        "approved_points": 0,
        "rejection_reason": "..."
    }

    Errors:
      400  missing or blank rejection_reason / reason exceeds max length
      403  caller is not an admin
      422  task not in DONE status
      500  unexpected server error
    """
    body = request.get_json(silent=True) or {}

    # FIX: validation is now only in one place (the route) at the boundary.
    # The service still has its own guard as a defence-in-depth safety net,
    # but the route owns the HTTP-layer 400 response.
    rejection_reason = (body.get("rejection_reason") or "").strip()

    if not rejection_reason:
        return jsonify({"error": "rejection_reason is required"}), 400

    # Check length on the stripped value (consistent with service layer)
    if len(rejection_reason) > MAX_REJECTION_REASON_LENGTH:
        return jsonify({
            "error": f"rejection_reason must be {MAX_REJECTION_REASON_LENGTH} "
                     f"characters or fewer (got {len(rejection_reason)})"
        }), 400

    try:
        task = _get_task(workspace_id, task_id)
        membership = _get_membership(workspace_id)

        result = reject_task(
            task=task,
            admin_membership=membership,
            rejection_reason=rejection_reason,
        )

        _save(task_id, result["task_updates"], result["audit_entry"])

        return jsonify({
            "message": "Task rejected",
            "task_id": task_id,
            "status": "rejected",
            "approved_points": 0,
            "rejection_reason": result["task_updates"]["rejection_reason"],
        }), 200

    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception:
        # FIX: same as approve — log internally, never leak str(e) to caller.
        logger.exception("Unexpected error in reject route task_id=%s", task_id)
        return jsonify({"error": "Internal server error"}), 500
