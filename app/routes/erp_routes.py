"""
routes/erp_routes.py
────────────────────
ERP attendance, alerts, daily updates routes.

workspace_id is passed as a request param (?workspace_id=N or JSON body).
JWT identity is a string — always cast with int(get_jwt_identity()).
User name = first_name + last_name (no .name field).
is_active is a method — use user.status check instead of column filter.
"""

from datetime import datetime, date
from functools import wraps

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.extensions import db
from app.models.user import User
from app.models.attendance import Attendance
from app.models.alert import Alert, AlertType, AlertPriority
from app.models.erp_support import DailyUpdate, Holiday


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _uid():
    return int(get_jwt_identity())


def _parse_workspace_id(source='json'):
    raw = (request.get_json(silent=True) or {}).get('workspace_id') \
        if source == 'json' else request.args.get('workspace_id')
    if not raw:
        return None, (jsonify({'error': 'workspace_id is required'}), 400)
    try:
        return int(raw), None
    except (ValueError, TypeError):
        return None, (jsonify({'error': 'workspace_id must be an integer'}), 400)


def _get_holiday(workspace_id, target_date):
    return Holiday.query.filter(
        Holiday.workspace_id == workspace_id,
        Holiday.start_date  <= target_date,
        Holiday.end_date    >= target_date,
    ).first()


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = User.query.get(_uid())
        if not user:
            return jsonify({'error': 'User not found'}), 401
        from app.models.Enums import UserRoles
        if user.role not in (UserRoles.admin,):
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE  —  /api/attendance
# ══════════════════════════════════════════════════════════════════════════════

attendance_bp = Blueprint('attendance', __name__, url_prefix='/api/attendance')


@attendance_bp.route('/clock-in', methods=['POST'])
@jwt_required()
def clock_in():
    try:
        user_id = _uid()
        workspace_id, err = _parse_workspace_id('json')
        if err: return err

        today   = date.today()
        holiday = _get_holiday(workspace_id, today)
        if holiday:
            return jsonify({'error': f'Clock-in not allowed on holiday: {holiday.name}',
                            'is_holiday': True, 'holiday': holiday.to_dict()}), 403

        existing = Attendance.query.filter_by(
            user_id=user_id, workspace_id=workspace_id, date=today).first()
        if existing:
            msg = 'Already clocked in today' if not existing.clock_out_time \
                  else 'Already completed attendance for today'
            return jsonify({'error': msg, 'attendance': existing.to_dict()}), 400

        attendance = Attendance(user_id=user_id, workspace_id=workspace_id,
                                date=today, clock_in_time=datetime.utcnow())
        attendance.calculate_status()
        db.session.add(attendance)

        if attendance.status == 'late':
            db.session.add(Alert(
                workspace_id=workspace_id, user_id=user_id,
                type=AlertType.late_attendance, priority=AlertPriority.MEDIUM,
                message=f'User clocked in late at {attendance.clock_in_time.strftime("%H:%M")}',
                resolved=False, archived=False,
            ))
        db.session.commit()
        return jsonify({'message': 'Clocked in successfully',
                        'attendance': attendance.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/clock-out', methods=['POST'])
@jwt_required()
def clock_out():
    try:
        user_id = _uid()
        workspace_id, err = _parse_workspace_id('json')
        if err: return err

        today      = date.today()
        attendance = Attendance.query.filter_by(
            user_id=user_id, workspace_id=workspace_id, date=today).first()

        if not attendance or not attendance.clock_in_time:
            return jsonify({'error': 'No active clock-in found for today'}), 400
        if attendance.clock_out_time:
            return jsonify({'error': 'Already clocked out today',
                            'attendance': attendance.to_dict()}), 400

        attendance.clock_out_time = datetime.utcnow()
        attendance.updated_at     = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': 'Clocked out successfully',
                        'attendance': attendance.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/today-status', methods=['GET'])
@jwt_required()
def today_status():
    try:
        user_id = _uid()
        workspace_id, err = _parse_workspace_id('args')
        if err: return err

        today      = date.today()
        attendance = Attendance.query.filter_by(
            user_id=user_id, workspace_id=workspace_id, date=today).first()
        holiday    = _get_holiday(workspace_id, today)

        can_clock_in  = (not holiday) and (attendance is None)
        can_clock_out = (not holiday and attendance is not None
                         and attendance.clock_in_time is not None
                         and attendance.clock_out_time is None)

        return jsonify({
            'date':          today.isoformat(),
            'is_holiday':    bool(holiday),
            'holiday':       holiday.to_dict() if holiday else None,
            'attendance':    attendance.to_dict() if attendance else {
                'status': 'not_clocked_in', 'clock_in_time': None,
                'clock_out_time': None, 'duration_hours': 0},
            'can_clock_in':  can_clock_in,
            'can_clock_out': can_clock_out,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/history', methods=['GET'])
@jwt_required()
def attendance_history():
    try:
        user_id = _uid()
        workspace_id, err = _parse_workspace_id('args')
        if err: return err

        limit   = min(int(request.args.get('limit', 30)), 100)
        records = (Attendance.query
                   .filter_by(user_id=user_id, workspace_id=workspace_id)
                   .order_by(Attendance.date.desc())
                   .limit(limit).all())
        return jsonify({'records': [r.to_dict() for r in records]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/workspace', methods=['GET'])
@jwt_required()
@admin_required
def workspace_attendance():
    try:
        workspace_id, err = _parse_workspace_id('args')
        if err: return err

        target_date_str = request.args.get('date', date.today().isoformat())
        target_date     = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        limit           = min(int(request.args.get('limit', 50)), 200)

        records = (Attendance.query
                   .filter_by(workspace_id=workspace_id, date=target_date)
                   .limit(limit).all())
        return jsonify({'records': [r.to_dict() for r in records]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/workspace-summary', methods=['GET'])
@jwt_required()
@admin_required
def workspace_summary():
    try:
        workspace_id, err = _parse_workspace_id('args')
        if err: return err

        target_date_str = request.args.get('date', date.today().isoformat())
        target_date     = datetime.strptime(target_date_str, '%Y-%m-%d').date()

        rows    = Attendance.query.filter_by(workspace_id=workspace_id, date=target_date).all()
        summary = {'present': 0, 'late': 0, 'absent': 0, 'total': len(rows)}
        for r in rows:
            if r.status in summary:
                summary[r.status] += 1
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/admin/mark-attendance', methods=['POST'])
@jwt_required()
@admin_required
def admin_mark_attendance():
    try:
        data     = request.get_json(silent=True) or {}
        required = ['workspace_id', 'user_id', 'date', 'status']
        missing  = [f for f in required if f not in data]
        if missing:
            return jsonify({'error': f'Missing: {", ".join(missing)}'}), 400
        if data['status'] not in ('present', 'late', 'absent'):
            return jsonify({'error': 'status must be present / late / absent'}), 400

        target_date  = datetime.strptime(data['date'], '%Y-%m-%d').date()
        workspace_id = int(data['workspace_id'])

        attendance = Attendance.query.filter_by(
            user_id=data['user_id'], workspace_id=workspace_id, date=target_date).first()

        if not attendance:
            attendance = Attendance(user_id=data['user_id'], workspace_id=workspace_id,
                                    date=target_date, status=data['status'])
            db.session.add(attendance)
        else:
            attendance.status     = data['status']
            attendance.updated_at = datetime.utcnow()

        if data.get('clock_in_time'):
            attendance.clock_in_time  = datetime.fromisoformat(data['clock_in_time'])
        if data.get('clock_out_time'):
            attendance.clock_out_time = datetime.fromisoformat(data['clock_out_time'])
        if data.get('notes'):
            attendance.notes = data['notes']

        db.session.commit()
        return jsonify({'message': 'Attendance marked',
                        'attendance': attendance.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/admin/bulk-mark-absent', methods=['POST'])
@jwt_required()
@admin_required
def bulk_mark_absent():
    try:
        data = request.get_json(silent=True) or {}
        workspace_id, err = _parse_workspace_id('json')
        if err: return err

        target_date_str = data.get('date', date.today().isoformat())
        target_date     = datetime.strptime(target_date_str, '%Y-%m-%d').date()

        holiday = _get_holiday(workspace_id, target_date)
        if holiday:
            return jsonify({'message': f'Skipped — holiday: {holiday.name}',
                            'is_holiday': True, 'marked_absent': 0}), 200

        # Use users who belong to this workspace_id via their activity records
        from app.models.erp_activity import UserActivity
        user_ids = [r.user_id for r in
                    UserActivity.query.filter_by(workspace_id=workspace_id)
                    .with_entities(UserActivity.user_id).distinct().all()]

        already_marked = {r.user_id for r in Attendance.query.filter(
            Attendance.workspace_id == workspace_id,
            Attendance.date         == target_date,
            Attendance.user_id.in_(user_ids),
        ).all()}

        marked = 0
        for uid in user_ids:
            if uid in already_marked:
                continue
            db.session.add(Attendance(user_id=uid, workspace_id=workspace_id,
                                      date=target_date, status='absent'))
            db.session.add(Alert(
                workspace_id=workspace_id, user_id=uid,
                type=AlertType.missing_attendance, priority=AlertPriority.MEDIUM,
                message=f'No clock-in recorded for {target_date_str}',
                resolved=False, archived=False,
            ))
            marked += 1

        db.session.commit()
        return jsonify({'message': f'Marked {marked} member(s) absent',
                        'marked_absent': marked}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# ALERTS  —  /api/alerts
# ══════════════════════════════════════════════════════════════════════════════

alerts_bp = Blueprint('erp_alerts', __name__, url_prefix='/api/erp-alerts')


@alerts_bp.route('', methods=['GET'])
@jwt_required()
def list_alerts():
    try:
        workspace_id, err = _parse_workspace_id('args')
        if err: return err

        query = Alert.query.filter_by(workspace_id=workspace_id, archived=False)

        alert_type = request.args.get('type')
        if alert_type:
            try:
                query = query.filter_by(type=AlertType[alert_type])
            except KeyError:
                return jsonify({'error': f'Invalid alert type: {alert_type}'}), 400

        resolved = request.args.get('resolved')
        if resolved is not None:
            query = query.filter_by(resolved=(resolved.lower() == 'true'))
        else:
            query = query.filter_by(resolved=False)

        limit   = min(int(request.args.get('limit', 50)), 200)
        records = query.order_by(Alert.created_at.desc()).limit(limit).all()
        return jsonify({'alerts': [r.to_dict() for r in records]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@alerts_bp.route('/digest', methods=['GET'])
@jwt_required()
@admin_required
def alert_digest():
    try:
        workspace_id, err = _parse_workspace_id('args')
        if err: return err

        from sqlalchemy import func
        today = date.today()
        rows  = (db.session.query(Alert.type, Alert.priority,
                                  func.count(Alert.id).label('count'))
                 .filter(Alert.workspace_id == workspace_id,
                         Alert.resolved     == False,
                         Alert.archived     == False,
                         Alert.created_at   >= datetime.combine(today, datetime.min.time()))
                 .group_by(Alert.type, Alert.priority).all())

        groups = [{'type':    r.type.value,
                   'priority': r.priority.value,
                   'count':    r.count} for r in rows]
        return jsonify({
            'workspace_id': workspace_id,
            'date':         str(today),
            'groups':       groups,
            'total_open':   sum(g['count'] for g in groups),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@alerts_bp.route('/<int:alert_id>/resolve', methods=['POST'])
@jwt_required()
@admin_required
def resolve_alert(alert_id):
    try:
        resolver_id = _uid()
        data        = request.get_json(silent=True) or {}
        alert       = Alert.query.get_or_404(alert_id)

        alert.resolved        = True
        alert.resolved_at     = datetime.utcnow()
        alert.resolved_by     = resolver_id
        alert.resolution_note = data.get('resolution_note', '')
        db.session.commit()
        return jsonify({'message': 'Alert resolved', 'alert': alert.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# DAILY UPDATES  —  /api/daily-updates
# ══════════════════════════════════════════════════════════════════════════════

daily_updates_bp = Blueprint('daily_updates', __name__, url_prefix='/api/daily-updates')


@daily_updates_bp.route('', methods=['POST'])
@jwt_required()
def submit_update():
    try:
        user_id = _uid()
        data    = request.get_json(silent=True) or {}
        workspace_id, err = _parse_workspace_id('json')
        if err: return err

        update = DailyUpdate(
            user_id         = user_id,
            workspace_id    = workspace_id,
            did_today       = data.get('did_today', ''),
            will_do_next    = data.get('will_do_next', ''),
            blockers        = data.get('blockers', ''),
            progress_rating = data.get('progress_rating'),
        )
        db.session.add(update)

        # Auto-resolve any open missing_update alert for today
        today = date.today()
        open_alert = Alert.query.filter(
            Alert.workspace_id == workspace_id,
            Alert.user_id      == user_id,
            Alert.type         == AlertType.missing_update,
            Alert.resolved     == False,
            Alert.archived     == False,
            Alert.created_at   >= datetime.combine(today, datetime.min.time()),
        ).first()
        if open_alert:
            open_alert.resolved        = True
            open_alert.resolved_at     = datetime.utcnow()
            open_alert.resolved_by     = user_id
            open_alert.resolution_note = 'Auto-resolved: user submitted daily update'

        db.session.commit()
        return jsonify({'message': 'Update submitted',
                        'update': update.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@daily_updates_bp.route('', methods=['GET'])
@jwt_required()
@admin_required
def list_updates():
    try:
        workspace_id, err = _parse_workspace_id('args')
        if err: return err

        limit   = min(int(request.args.get('limit', 50)), 200)
        records = (DailyUpdate.query
                   .filter_by(workspace_id=workspace_id)
                   .order_by(DailyUpdate.created_at.desc())
                   .limit(limit).all())
        return jsonify({'updates': [r.to_dict() for r in records]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500