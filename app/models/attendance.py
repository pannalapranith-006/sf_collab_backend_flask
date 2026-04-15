# ============================================================
# models/attendance.py
# ============================================================
from datetime import datetime, date, time
from extensions import db


class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    clock_in_time = db.Column(db.DateTime)
    clock_out_time = db.Column(db.DateTime)
    # POINT 3: No default='absent'. Status is always set explicitly by
    # calculate_status() or admin logic — never silently defaulted by the DB.
    status = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', back_populates='attendance_records')
    workspace = db.relationship('Workspace', back_populates='attendance_records')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', 'workspace_id', name='unique_user_attendance_per_day'),
    )

    def calculate_status(self, late_threshold_hour=9, late_threshold_minute=0):
        """
        Set status from clock-in time. Doc logic:
          - No clock-in  -> absent
          - clock-in after threshold -> late
          - clock-in at/before threshold -> present
        Must be called before every insert so status is never unset.
        """
        if not self.clock_in_time:
            self.status = 'absent'
            return
        cutoff = time(late_threshold_hour, late_threshold_minute)
        self.status = 'late' if self.clock_in_time.time() > cutoff else 'present'

    def get_duration_hours(self):
        if self.clock_in_time and self.clock_out_time:
            delta = self.clock_out_time - self.clock_in_time
            return round(delta.total_seconds() / 3600, 2)
        return 0

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'workspace_id': self.workspace_id,
            'date': self.date.isoformat() if self.date else None,
            'clock_in_time': self.clock_in_time.isoformat() if self.clock_in_time else None,
            'clock_out_time': self.clock_out_time.isoformat() if self.clock_out_time else None,
            'status': self.status,
            'notes': self.notes,
            'duration_hours': self.get_duration_hours(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user': {
                'id': self.user.id,
                'name': self.user.name,
                'email': self.user.email
            } if self.user else None
        }


# ============================================================
# routes/attendance.py
# ============================================================
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date
from sqlalchemy import and_, func
from models import db, Attendance, User, Workspace, Alert, Holiday
from app import role_required

attendance_bp = Blueprint('attendance', __name__, url_prefix='/api/attendance')


# ----------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------

def _parse_workspace_id(source='json'):
    """
    Extract and coerce workspace_id from request body or query args.
    Returns (int, None) on success or (None, error_tuple) on failure.
    """
    raw = (request.get_json() or {}).get('workspace_id') \
        if source == 'json' else request.args.get('workspace_id')
    if not raw:
        return None, (jsonify({'error': 'Workspace ID is required'}), 400)
    try:
        return int(raw), None
    except (ValueError, TypeError):
        return None, (jsonify({'error': 'Workspace ID must be an integer'}), 400)


def _require_workspace(workspace_id):
    """
    POINT 4: Confirm the workspace exists before any business logic runs.
    Returns (Workspace, None) on success or (None, error_tuple) if not found.
    Called at the top of every endpoint.
    """
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        return None, (jsonify({'error': 'Workspace not found'}), 404)
    return workspace, None


def _get_holiday(workspace_id, target_date):
    """Return the Holiday record for a given workspace + date, or None."""
    return Holiday.query.filter_by(workspace_id=workspace_id, date=target_date).first()


# ----------------------------------------------------------------
# POST /api/attendance/clock-in
# ----------------------------------------------------------------
@attendance_bp.route('/clock-in', methods=['POST'])
@jwt_required()
def clock_in():
    """Clock in for the day."""
    try:
        user_id = get_jwt_identity()

        workspace_id, err = _parse_workspace_id('json')
        if err:
            return err

        # POINT 4
        _, err = _require_workspace(workspace_id)
        if err:
            return err

        today = date.today()

        # POINT 1 + POINT 5: Block clock-in entirely on holidays.
        # Doc: "Disable attendance alerts on holidays" — the system must
        # not process any attendance action on a holiday at all.
        holiday = _get_holiday(workspace_id, today)
        if holiday:
            return jsonify({
                'error': f'Clock-in is not allowed on a holiday: {holiday.name}',
                'is_holiday': True,
                'holiday': holiday.to_dict()
            }), 403

        existing = Attendance.query.filter_by(
            user_id=user_id, workspace_id=workspace_id, date=today
        ).first()

        if existing:
            if existing.clock_out_time:
                return jsonify({
                    'error': 'Already completed attendance for today',
                    'attendance': existing.to_dict()
                }), 400
            return jsonify({
                'error': 'Already clocked in today',
                'attendance': existing.to_dict()
            }), 400

        # POINT 3: status is always set explicitly by calculate_status()
        attendance = Attendance(
            user_id=user_id,
            workspace_id=workspace_id,
            date=today,
            clock_in_time=datetime.utcnow()
        )
        attendance.calculate_status()  # sets 'present' or 'late' — never relies on column default
        db.session.add(attendance)

        # Doc alerts spec: fire late_attendance alert when user is late
        if attendance.status == 'late':
            db.session.add(Alert(
                workspace_id=workspace_id,
                user_id=user_id,
                type='late_attendance',
                message=f'User clocked in late at {attendance.clock_in_time.strftime("%H:%M")}',
                resolved=False
            ))

        db.session.commit()

        return jsonify({
            'message': 'Clocked in successfully',
            'attendance': attendance.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------
# POST /api/attendance/clock-out
# ----------------------------------------------------------------
@attendance_bp.route('/clock-out', methods=['POST'])
@jwt_required()
def clock_out():
    """Clock out for the day."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}

        workspace_id, err = _parse_workspace_id('json')
        if err:
            return err

        # POINT 4
        _, err = _require_workspace(workspace_id)
        if err:
            return err

        today = date.today()
        attendance = Attendance.query.filter_by(
            user_id=user_id, workspace_id=workspace_id, date=today
        ).first()

        if not attendance or not attendance.clock_in_time:
            return jsonify({'error': 'Not clocked in today'}), 400

        if attendance.clock_out_time:
            return jsonify({
                'error': 'Already clocked out today',
                'attendance': attendance.to_dict()
            }), 400

        attendance.clock_out_time = datetime.utcnow()
        attendance.updated_at = datetime.utcnow()

        notes = data.get('notes', '')
        if notes:
            attendance.notes = notes

        db.session.commit()

        return jsonify({
            'message': 'Clocked out successfully',
            'attendance': attendance.to_dict(),
            'duration_hours': attendance.get_duration_hours()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------
# GET /api/attendance/my-history
# ----------------------------------------------------------------
@attendance_bp.route('/my-history', methods=['GET'])
@jwt_required()
def my_history():
    """Get current user's attendance history."""
    try:
        user_id = get_jwt_identity()

        workspace_id, err = _parse_workspace_id('args')
        if err:
            return err

        # POINT 4
        _, err = _require_workspace(workspace_id)
        if err:
            return err

        base_filter = dict(user_id=user_id, workspace_id=workspace_id)
        query = Attendance.query.filter_by(**base_filter)

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        month = request.args.get('month')   # YYYY-MM

        year = month_num = None
        if month:
            try:
                year, month_num = map(int, month.split('-'))
            except ValueError:
                return jsonify({'error': 'month must be in YYYY-MM format'}), 400
            query = query.filter(
                and_(
                    func.extract('year', Attendance.date) == year,
                    func.extract('month', Attendance.date) == month_num
                )
            )
        else:
            if start_date:
                try:
                    query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
                except ValueError:
                    return jsonify({'error': 'start_date must be YYYY-MM-DD'}), 400
            if end_date:
                try:
                    query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
                except ValueError:
                    return jsonify({'error': 'end_date must be YYYY-MM-DD'}), 400

        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 31))
        except ValueError:
            return jsonify({'error': 'page and per_page must be integers'}), 400

        paginated = query.order_by(Attendance.date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Stats run on the full filtered set, not just the current page
        stats_q = Attendance.query.filter_by(**base_filter)
        if month:
            stats_q = stats_q.filter(
                and_(
                    func.extract('year', Attendance.date) == year,
                    func.extract('month', Attendance.date) == month_num
                )
            )
        else:
            if start_date:
                stats_q = stats_q.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
            if end_date:
                stats_q = stats_q.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

        total_days = stats_q.count()
        present_days = stats_q.filter(Attendance.status == 'present').count()
        late_days = stats_q.filter(Attendance.status == 'late').count()
        absent_days = stats_q.filter(Attendance.status == 'absent').count()
        total_hours = sum(
            r.get_duration_hours()
            for r in stats_q.filter(Attendance.clock_out_time.isnot(None)).all()
        )

        return jsonify({
            'attendance': [r.to_dict() for r in paginated.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated.total,
                'pages': paginated.pages
            },
            'statistics': {
                'total_days': total_days,
                'present_days': present_days,
                'late_days': late_days,
                'absent_days': absent_days,
                'total_hours': round(total_hours, 2),
                'attendance_rate': f"{(present_days + late_days) / total_days * 100:.1f}%" if total_days > 0 else "0%"
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------
# GET /api/attendance/workspace-overview
# ----------------------------------------------------------------
@attendance_bp.route('/workspace-overview', methods=['GET'])
@jwt_required()
@role_required(['admin', 'member'])
def workspace_overview():
    """Get attendance overview for entire workspace (daily snapshot)."""
    try:
        workspace_id, err = _parse_workspace_id('args')
        if err:
            return err

        # POINT 4
        _, err = _require_workspace(workspace_id)
        if err:
            return err

        target_date_str = request.args.get('date', date.today().isoformat())
        try:
            target_date_obj = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'date must be YYYY-MM-DD'}), 400

        # POINT 5: surface holiday in overview so the frontend reflects that
        # attendance is not expected on this day
        holiday = _get_holiday(workspace_id, target_date_obj)

        from models.workspace import WorkspaceUser
        workspace_users = db.session.query(User, WorkspaceUser).join(
            WorkspaceUser, User.id == WorkspaceUser.user_id
        ).filter(WorkspaceUser.workspace_id == workspace_id).all()

        attendance_records = Attendance.query.filter_by(
            workspace_id=workspace_id, date=target_date_obj
        ).all()
        attendance_dict = {r.user_id: r for r in attendance_records}

        members_status = []
        for user, workspace_user in workspace_users:
            record = attendance_dict.get(user.id)
            members_status.append({
                'user': user.to_dict(),
                'role': workspace_user.role,
                'attendance': record.to_dict() if record else {
                    'status': 'absent',
                    'clock_in_time': None,
                    'clock_out_time': None,
                    'duration_hours': 0
                }
            })

        total_members = len(members_status)
        present = sum(1 for m in members_status if m['attendance']['status'] == 'present')
        late = sum(1 for m in members_status if m['attendance']['status'] == 'late')
        absent = sum(1 for m in members_status if m['attendance']['status'] == 'absent')
        not_clocked_out = sum(
            1 for m in members_status
            if m['attendance']['clock_in_time'] and not m['attendance']['clock_out_time']
        )

        return jsonify({
            'date': target_date_str,
            'is_holiday': bool(holiday),
            'holiday': holiday.to_dict() if holiday else None,
            'members': members_status,
            'statistics': {
                'total_members': total_members,
                'present': present,
                'late': late,
                'absent': absent,
                'not_clocked_out': not_clocked_out,
                'attendance_rate': f"{(present + late) / total_members * 100:.1f}%" if total_members > 0 else "0%"
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------
# GET /api/attendance/workspace-report  (admin only)
# ----------------------------------------------------------------
@attendance_bp.route('/workspace-report', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def workspace_report():
    """Generate detailed attendance report for a date range."""
    try:
        workspace_id, err = _parse_workspace_id('args')
        if err:
            return err

        # POINT 4
        _, err = _require_workspace(workspace_id)
        if err:
            return err

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date', date.today().isoformat())

        if not start_date:
            return jsonify({'error': 'start_date is required'}), 400

        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Dates must be YYYY-MM-DD'}), 400

        if start > end:
            return jsonify({'error': 'start_date must be before end_date'}), 400

        from models.workspace import WorkspaceUser
        workspace_users = WorkspaceUser.query.filter_by(workspace_id=workspace_id).all()
        user_ids = [wu.user_id for wu in workspace_users]

        if not user_ids:
            return jsonify({'period': {'start': start_date, 'end': end_date}, 'reports': []}), 200

        records = Attendance.query.filter(
            Attendance.workspace_id == workspace_id,
            Attendance.date.between(start, end),
            Attendance.user_id.in_(user_ids)
        ).all()

        total_days = (end - start).days + 1

        user_reports = {}
        for wu in workspace_users:
            uid = wu.user_id
            user_records = [r for r in records if r.user_id == uid]
            user = User.query.get(uid)

            present = sum(1 for r in user_records if r.status == 'present')
            late = sum(1 for r in user_records if r.status == 'late')
            clocked_in_days = sum(1 for r in user_records if r.clock_in_time)
            absent = total_days - clocked_in_days
            total_hours = sum(r.get_duration_hours() for r in user_records)

            user_reports[uid] = {
                'user': user.to_dict() if user else {'id': uid},
                'role': wu.role,
                'total_days': total_days,
                'present': present,
                'late': late,
                'absent': absent,
                'total_hours': round(total_hours, 2),
                'attendance_rate': f"{(present + late) / total_days * 100:.1f}%" if total_days > 0 else "0%",
                'daily_records': [r.to_dict() for r in sorted(user_records, key=lambda r: r.date)]
            }

        return jsonify({
            'period': {'start': start.isoformat(), 'end': end.isoformat(), 'total_days': total_days},
            'reports': list(user_reports.values())
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------
# GET /api/attendance/today-status
# ----------------------------------------------------------------
@attendance_bp.route('/today-status', methods=['GET'])
@jwt_required()
def today_status():
    """Get current user's attendance status for today."""
    try:
        user_id = get_jwt_identity()

        workspace_id, err = _parse_workspace_id('args')
        if err:
            return err

        # POINT 4
        _, err = _require_workspace(workspace_id)
        if err:
            return err

        today = date.today()
        attendance = Attendance.query.filter_by(
            user_id=user_id, workspace_id=workspace_id, date=today
        ).first()

        # POINT 5: holiday drives can_clock_in — consistent with the block in clock_in.
        # Frontend reads this flag to disable the button before the user even tries.
        holiday = _get_holiday(workspace_id, today)

        can_clock_in = (not holiday) and (attendance is None)
        can_clock_out = (
            not holiday and
            attendance is not None and
            attendance.clock_in_time is not None and
            attendance.clock_out_time is None
        )

        return jsonify({
            'date': today.isoformat(),
            'is_holiday': bool(holiday),
            'holiday': holiday.to_dict() if holiday else None,
            'attendance': attendance.to_dict() if attendance else {
                'status': 'not_clocked_in',
                'clock_in_time': None,
                'clock_out_time': None,
                'duration_hours': 0
            },
            'can_clock_in': can_clock_in,
            'can_clock_out': can_clock_out
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------
# POST /api/attendance/admin/mark-attendance  (admin only)
# ----------------------------------------------------------------
@attendance_bp.route('/admin/mark-attendance', methods=['POST'])
@jwt_required()
@role_required(['admin'])
def admin_mark_attendance():
    """Admin endpoint to manually mark or correct attendance."""
    try:
        data = request.get_json() or {}

        required_fields = ['workspace_id', 'user_id', 'date', 'status']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

        valid_statuses = {'present', 'late', 'absent'}
        if data['status'] not in valid_statuses:
            return jsonify({'error': f'status must be one of: {", ".join(valid_statuses)}'}), 400

        try:
            target_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'date must be YYYY-MM-DD'}), 400

        workspace_id = data['workspace_id']

        # POINT 4
        _, err = _require_workspace(workspace_id)
        if err:
            return err

        from models.workspace import WorkspaceUser
        if not WorkspaceUser.query.filter_by(user_id=data['user_id'], workspace_id=workspace_id).first():
            return jsonify({'error': 'User is not a member of this workspace'}), 403

        attendance = Attendance.query.filter_by(
            user_id=data['user_id'], workspace_id=workspace_id, date=target_date
        ).first()

        if not attendance:
            # POINT 3: status passed explicitly — no column default involved
            attendance = Attendance(
                user_id=data['user_id'],
                workspace_id=workspace_id,
                date=target_date,
                status=data['status']
            )
            db.session.add(attendance)
        else:
            attendance.status = data['status']
            attendance.updated_at = datetime.utcnow()

        if data.get('clock_in_time'):
            try:
                attendance.clock_in_time = datetime.fromisoformat(data['clock_in_time'])
            except ValueError:
                return jsonify({'error': 'clock_in_time must be ISO 8601'}), 400

        if data.get('clock_out_time'):
            try:
                attendance.clock_out_time = datetime.fromisoformat(data['clock_out_time'])
            except ValueError:
                return jsonify({'error': 'clock_out_time must be ISO 8601'}), 400

        if attendance.clock_in_time and attendance.clock_out_time:
            if attendance.clock_out_time <= attendance.clock_in_time:
                return jsonify({'error': 'clock_out_time must be after clock_in_time'}), 400

        if data.get('notes'):
            attendance.notes = data['notes']

        db.session.commit()

        return jsonify({
            'message': 'Attendance marked successfully',
            'attendance': attendance.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------
# POST /api/attendance/admin/bulk-mark-absent  (admin only)
# End-of-day cron trigger: marks absent + fires alerts for missing clock-ins.
# ----------------------------------------------------------------
@attendance_bp.route('/admin/bulk-mark-absent', methods=['POST'])
@jwt_required()
@role_required(['admin'])
def bulk_mark_absent():
    """
    Mark all workspace members who did not clock in as absent for a given date
    and raise missing_attendance alerts.
    POINT 1 + POINT 5: Entirely skipped on holidays — no records created and
    no alerts fired, consistent with the clock-in block.
    """
    try:
        workspace_id, err = _parse_workspace_id('json')
        if err:
            return err

        # POINT 4
        _, err = _require_workspace(workspace_id)
        if err:
            return err

        data = request.get_json() or {}
        target_date_str = data.get('date', date.today().isoformat())
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'date must be YYYY-MM-DD'}), 400

        # POINT 1 + POINT 5: Doc says "Disable attendance alerts on holidays".
        # No absent records and no alerts on a holiday — same rule as clock_in block.
        holiday = _get_holiday(workspace_id, target_date)
        if holiday:
            return jsonify({
                'message': f'Skipped — {target_date_str} is a holiday ({holiday.name})',
                'is_holiday': True,
                'marked_absent': 0
            }), 200

        from models.workspace import WorkspaceUser
        workspace_users = WorkspaceUser.query.filter_by(workspace_id=workspace_id).all()
        user_ids = [wu.user_id for wu in workspace_users]

        already_recorded = {
            r.user_id for r in Attendance.query.filter(
                Attendance.workspace_id == workspace_id,
                Attendance.date == target_date,
                Attendance.user_id.in_(user_ids)
            ).all()
        }

        marked = 0
        for uid in user_ids:
            if uid in already_recorded:
                continue

            # POINT 3: status set explicitly — no column default
            db.session.add(Attendance(
                user_id=uid,
                workspace_id=workspace_id,
                date=target_date,
                status='absent'
            ))

            # POINT 2: missing_attendance — not missing_update.
            # missing_update belongs to the Daily Updates module (doc section 5).
            # The cron "Missing clock-in" check maps to this attendance-specific type.
            db.session.add(Alert(
                workspace_id=workspace_id,
                user_id=uid,
                type='missing_attendance',
                message=f'No clock-in recorded for {target_date_str}',
                resolved=False
            ))
            marked += 1

        db.session.commit()

        return jsonify({
            'message': f'Marked {marked} member(s) as absent for {target_date_str}',
            'marked_absent': marked
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
