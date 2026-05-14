from datetime import date, datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.attendance import Attendance
from app.models.holiday import Holiday
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.utils.helper import error_response, success_response
from app.utils.workspace_permissions import (
    get_current_user_id,
    get_workspace_membership,
    workspace_admin_required,
)


attendance_bp = Blueprint('attendance', __name__)


def _parse_workspace_id(source='json'):
    if source == 'json':
        raw = (request.get_json(silent=True) or {}).get('workspace_id')
    else:
        raw = request.args.get('workspace_id')

    if raw is None:
        return None, error_response('workspace_id is required', 400)

    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, error_response('workspace_id must be an integer', 400)


def _late_cutoff():
    # Default 09:00; can be overridden later by config/env.
    return 9, 0


@attendance_bp.route('/clock-in', methods=['POST'])
@jwt_required()
def clock_in():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    workspace_id, err = _parse_workspace_id('json')
    if err:
        return err

    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        return error_response('Workspace not found', 404)

    membership = get_workspace_membership(workspace_id, user_id)
    if not membership:
        return error_response('Unauthorized to access this workspace', 403)

    today = date.today()
    holiday = Holiday.query.filter_by(workspace_id=workspace_id, date=today).first()
    if holiday:
        return error_response(
            f'Cannot clock in on holiday: {holiday.name}',
            400,
            {'holiday': holiday.to_dict()},
        )

    existing = Attendance.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        date=today,
    ).first()

    if existing:
        return error_response('Already clocked in today', 400, {'attendance': existing.to_dict()})

    late_hour, late_minute = _late_cutoff()
    attendance = Attendance(
        user_id=user_id,
        workspace_id=workspace_id,
        date=today,
        clock_in_time=datetime.utcnow(),
    )
    attendance.calculate_status(late_hour, late_minute)

    db.session.add(attendance)
    db.session.commit()

    return success_response({'attendance': attendance.to_dict()}, 'Clocked in successfully', 201)


@attendance_bp.route('/clock-out', methods=['POST'])
@jwt_required()
def clock_out():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    workspace_id, err = _parse_workspace_id('json')
    if err:
        return err

    membership = get_workspace_membership(workspace_id, user_id)
    if not membership:
        return error_response('Unauthorized to access this workspace', 403)

    today = date.today()
    attendance = Attendance.query.filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
        date=today,
    ).first()

    if not attendance or not attendance.clock_in_time:
        return error_response('No active clock-in found for today', 400)

    if attendance.clock_out_time:
        return error_response('Already clocked out today', 400, {'attendance': attendance.to_dict()})

    data = request.get_json(silent=True) or {}
    attendance.clock_out_time = datetime.utcnow()
    attendance.updated_at = datetime.utcnow()
    if data.get('notes'):
        attendance.notes = data.get('notes')

    db.session.commit()

    return success_response(
        {'attendance': attendance.to_dict(), 'duration_hours': attendance.get_duration_hours()},
        'Clocked out successfully',
    )


@attendance_bp.route('/my-history', methods=['GET'])
@jwt_required()
def my_history():
    user_id = get_current_user_id()
    if not user_id:
        return error_response('Invalid auth identity', 401)

    workspace_id, err = _parse_workspace_id('args')
    if err:
        return err

    membership = get_workspace_membership(workspace_id, user_id)
    if not membership:
        return error_response('Unauthorized to access this workspace', 403)

    limit_raw = request.args.get('limit', 30)
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError):
        return error_response('limit must be an integer', 400)

    if limit < 1:
        return error_response('limit must be >= 1', 400)

    limit = min(limit, 180)
    records = (Attendance.query
               .filter_by(user_id=user_id, workspace_id=workspace_id)
               .order_by(Attendance.date.desc())
               .limit(limit)
               .all())

    return success_response({'records': [r.to_dict() for r in records]})


@attendance_bp.route('/workspace-overview/<int:workspace_id>', methods=['GET'])
@workspace_admin_required('workspace_id')
def workspace_overview(workspace_id):
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        return error_response('Workspace not found', 404)

    target_raw = request.args.get('date')
    if target_raw:
        try:
            target_date = datetime.strptime(target_raw, '%Y-%m-%d').date()
        except ValueError:
            return error_response('date must be YYYY-MM-DD', 400)
    else:
        target_date = date.today()

    holiday = Holiday.query.filter_by(workspace_id=workspace_id, date=target_date).first()

    members = WorkspaceMember.query.filter_by(workspace_id=workspace_id, status='active').all()
    records = Attendance.query.filter_by(workspace_id=workspace_id, date=target_date).all()

    by_user = {r.user_id: r for r in records}
    absent_created = 0
    if not holiday:
        for m in members:
            if m.user_id in by_user:
                continue
            r = Attendance(
                user_id=m.user_id,
                workspace_id=workspace_id,
                date=target_date,
                status='absent',
            )
            db.session.add(r)
            by_user[m.user_id] = r
            absent_created += 1

    if absent_created:
        db.session.commit()
        records = Attendance.query.filter_by(workspace_id=workspace_id, date=target_date).all()

    summary = {'present': 0, 'late': 0, 'absent': 0, 'total': len(records)}
    for r in records:
        if r.status in summary:
            summary[r.status] += 1

    return success_response({
        'workspace': workspace.to_dict(),
        'date': target_date.isoformat(),
        'holiday': holiday.to_dict() if holiday else None,
        'summary': summary,
        'absent_marked': absent_created,
        'records': [r.to_dict() for r in records],
    })
