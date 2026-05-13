"""
routes/activity_monitor_routes.py
────────────────────────────────────────────────────────────────────────────
Activity monitoring for SFCollab ERP.

Key differences from original:
- Uses flask_jwt_extended (not flask_login)
- Uses app.extensions.limiter (already in your extensions.py)
- User has no workspace_id column — workspace comes from UserActivity records
- User name = first_name + last_name
- All imports use app. prefix
"""

import logging
import time as time_module
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import (get_jwt_identity, jwt_required,
                                 verify_jwt_in_request)
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

from app.extensions import db, limiter
from app.models.user import User
from app.models.erp_activity import UserActivity, ActivityMonitorJobHealth
from app.models.alert import Alert, AlertType, AlertPriority

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

ACTIVITY_CONFIG = {
    'active_threshold':       timedelta(minutes=5),
    'idle_threshold':         timedelta(minutes=30),
    'dead_threshold':         timedelta(hours=24),
    'heartbeat_min_interval': timedelta(seconds=30),
    'middleware_min_interval':timedelta(seconds=30),
    'alert_cooldown_hours':   24,
    'pagination_limit':       50,
    'cron_batch_size':        500,
    'cron_max_batches':       1000,
    'alert_lookup_chunk_size':100,
    'include_total_in_pagination': False,
}

ALERT_TYPE_MAP = {
    'idle':     'inactive_user_idle',
    'inactive': 'inactive_user_inactive',
    'dead':     'inactive_user_dead',
}

HEARTBEAT_RATE_LIMIT = '30 per minute'
MAX_PAGINATION_LIMIT = 100
CRON_JOB_NAME        = 'inactivity_monitor'
ACTIVITY_PATH_PREFIX = '/api/activity'

activity_monitor_bp = Blueprint('activity_monitor', __name__, url_prefix='/api/activity')


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    model_config = ConfigDict(extra='forbid')
    page:          int  = Field(default=0, ge=0)
    limit:         int  = Field(default=ACTIVITY_CONFIG['pagination_limit'],
                                ge=1, le=MAX_PAGINATION_LIMIT)
    include_total: bool = Field(default=ACTIVITY_CONFIG['include_total_in_pagination'])


class HeartbeatPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    client_timestamp: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _uid() -> int:
    return int(get_jwt_identity())


def _log(level, event, **ctx):
    logger.log(level, event, extra={'event': event, **ctx})


def _log_exc(event, **ctx):
    logger.exception(event, extra={'event': event, **ctx})


def _safe_commit(event, raise_on_error=False, **ctx):
    try:
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        _log_exc(f'{event}_failed', **ctx)
        if raise_on_error: raise
        return False


def _validate_payload(model_cls):
    payload = request.get_json(silent=True) or {}
    try:
        return model_cls.model_validate(payload), None
    except ValidationError as exc:
        return None, (jsonify({'error': 'Invalid payload', 'details': exc.errors()}), 400)


def _get_pagination_params():
    raw = {
        'page':          request.args.get('page',  0),
        'limit':         request.args.get('limit', ACTIVITY_CONFIG['pagination_limit']),
        'include_total': request.args.get('include_total',
                                          ACTIVITY_CONFIG['include_total_in_pagination']),
    }
    try:
        return PaginationParams.model_validate(raw), None
    except ValidationError as exc:
        return None, (jsonify({'error': 'Invalid pagination', 'details': exc.errors()}), 400)


def paginate(query, page, limit, include_total=False):
    total = query.count() if include_total else None
    return query.limit(limit).offset(page * limit).all(), total


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


def _get_user_workspace(user_id: int) -> int | None:
    """
    Workspace is not stored on User — look it up from their latest activity record.
    Falls back to user_id itself as the workspace scope if no record exists.
    """
    record = (UserActivity.query
              .filter_by(user_id=user_id)
              .order_by(UserActivity.last_activity.desc())
              .first())
    return record.workspace_id if record else user_id  # default to user_id


def _should_track():
    if request.method == 'OPTIONS':                          return False
    if request.path == '/health':                            return False
    if request.path.startswith(ACTIVITY_PATH_PREFIX):        return False
    try:
        verify_jwt_in_request(optional=True)
        return get_jwt_identity() is not None
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────

def register_activity_middleware(app):
    @app.before_request
    def _track():
        if not _should_track():
            return
        if hasattr(g, 'activity_tracked'):
            return
        g.activity_tracked = True

        try:
            user_id      = int(get_jwt_identity())
            workspace_id = _get_user_workspace(user_id)
            if not workspace_id:
                return
            activity = UserActivity.get_or_create(user_id, workspace_id)
            now      = datetime.utcnow()
            if (activity.last_activity is None or
                    (now - activity.last_activity) > ACTIVITY_CONFIG['middleware_min_interval']):
                activity.update_activity(request_obj=request)
                _safe_commit('activity_middleware_update', user_id=user_id,
                             workspace_id=workspace_id)
        except Exception:
            pass  # never block a request due to activity tracking


@activity_monitor_bp.record_once
def _setup(state):
    register_activity_middleware(state.app)
    _log(logging.INFO, 'activity_blueprint_initialized')


# ─────────────────────────────────────────────────────────────────────────────
# Login / logout hooks — call from auth_routes.py
# ─────────────────────────────────────────────────────────────────────────────

def on_user_login(user, workspace_id: int, request_obj=None):
    """
    Call after successful login:
        from app.routes.activity_monitor_routes import on_user_login
        on_user_login(user, workspace_id=N, request_obj=request)

    workspace_id must be passed explicitly since it's not on the User model.
    """
    activity = UserActivity.get_or_create(user.id, workspace_id)
    activity.set_login(request_obj)
    _safe_commit('activity_login', user_id=user.id, workspace_id=workspace_id)
    return activity


def on_user_logout(user_id: int):
    """Call from logout route."""
    records = UserActivity.query.filter_by(user_id=user_id).all()
    for r in records:
        r.set_logout()
    _safe_commit('activity_logout', user_id=user_id)


# ─────────────────────────────────────────────────────────────────────────────
# Cron: inactivity checker
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_alerts_chunked(pairs, alert_types):
    if not pairs:
        return {}
    chunk_size   = ACTIVITY_CONFIG['alert_lookup_chunk_size']
    alert_lookup = {}
    for i in range(0, len(pairs), chunk_size):
        chunk  = pairs[i:i + chunk_size]
        alerts = Alert.query.filter(
            Alert.resolved == False,
            Alert.type.in_(alert_types),
        ).filter(db.tuple_(Alert.workspace_id, Alert.user_id).in_(chunk)).all()
        for a in alerts:
            alert_lookup[(a.workspace_id, a.user_id, a.type)] = a.created_at
    return alert_lookup


def check_inactive_users_and_alert():
    start_time = time_module.time()
    with current_app.app_context():
        now                    = datetime.utcnow()
        idle_t                 = now - ACTIVITY_CONFIG['idle_threshold']
        inactive_t             = now - ACTIVITY_CONFIG['idle_threshold']   # same as idle for "inactive" band
        dead_t                 = now - ACTIVITY_CONFIG['dead_threshold']
        cooldown               = timedelta(hours=ACTIVITY_CONFIG['alert_cooldown_hours'])
        batch_size             = ACTIVITY_CONFIG['cron_batch_size']
        last_id = alerts_created = batch_count = total_processed = 0

        try:
            while batch_count < ACTIVITY_CONFIG['cron_max_batches']:
                batch = (db.session.query(UserActivity)
                         .join(User, User.id == UserActivity.user_id)
                         .filter(UserActivity.last_activity < idle_t,
                                 UserActivity.id > last_id)
                         .options(joinedload(UserActivity.user))
                         .order_by(UserActivity.id)
                         .limit(batch_size).all())
                if not batch: break

                last_id          = batch[-1].id
                total_processed += len(batch)
                pairs            = [(a.workspace_id, a.user_id) for a in batch]
                alert_lookup     = _fetch_alerts_chunked(pairs, list(ALERT_TYPE_MAP.values()))

                for act in batch:
                    la = act.last_activity
                    if la < dead_t:     severity = 'dead'
                    elif la < inactive_t: severity = 'inactive'
                    elif la < idle_t:   severity = 'idle'
                    else:               continue

                    alert_type      = ALERT_TYPE_MAP[severity]
                    key             = (act.workspace_id, act.user_id, alert_type)
                    last_alert_time = alert_lookup.get(key)
                    if last_alert_time and (now - last_alert_time) < cooldown:
                        continue

                    db.session.add(Alert(
                        workspace_id=act.workspace_id, user_id=act.user_id,
                        type=AlertType.inactive_user, priority=AlertPriority.LOW,
                        message=f'User has been {severity} for an extended period.',
                        resolved=False, archived=False, created_at=now,
                    ))
                    alerts_created += 1

                _safe_commit('activity_cron_batch', raise_on_error=True,
                             batch_number=batch_count + 1)
                batch_count += 1
                if len(batch) < batch_size: break

            _log(logging.INFO, 'activity_cron_finished',
                 batch_count=batch_count, total_processed=total_processed,
                 alerts_created=alerts_created,
                 duration_ms=int((time_module.time() - start_time) * 1000))
        except Exception as exc:
            db.session.rollback()
            _log_exc('activity_cron_failed', error=str(exc))


def start_activity_scheduler(app):
    if not app.config.get('ACTIVITY_MONITOR_RUN_SCHEDULER', False):
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        if getattr(app, '_activity_scheduler_started', False):
            return
        scheduler = BackgroundScheduler()
        scheduler.start()
        app._activity_scheduler_started = True
        scheduler.add_job(id=CRON_JOB_NAME, func=check_inactive_users_and_alert,
                          trigger='interval', minutes=5, replace_existing=True)
        _log(logging.INFO, 'activity_scheduler_started')
    except ImportError:
        _log(logging.WARNING, 'activity_scheduler_skipped',
             reason='APScheduler not installed')
    except Exception:
        _log_exc('activity_scheduler_start_failed')


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@activity_monitor_bp.route('/heartbeat', methods=['POST'])
@jwt_required()
@limiter.limit(HEARTBEAT_RATE_LIMIT)
def heartbeat():
    _, err = _validate_payload(HeartbeatPayload)
    if err: return err

    user_id      = _uid()
    workspace_id = _get_user_workspace(user_id)
    # workspace_id now always resolves (defaults to user_id)

    activity = UserActivity.get_or_create(user_id, workspace_id)
    now      = datetime.utcnow()
    if (activity.last_activity is None or
            (now - activity.last_activity) > ACTIVITY_CONFIG['heartbeat_min_interval']):
        activity.update_activity(request_obj=request)
        if not _safe_commit('heartbeat', user_id=user_id, workspace_id=workspace_id):
            return jsonify({'error': 'Failed to record heartbeat'}), 500

    return jsonify({'status': 'ok'}), 200


@activity_monitor_bp.route('/me', methods=['GET'])
@jwt_required()
def get_my_activity():
    user_id  = _uid()
    records  = UserActivity.query.filter_by(user_id=user_id).all()
    if not records:
        return jsonify({'status': 'no_data'}), 200

    # Return the most recently active workspace record
    record = max(records, key=lambda r: r.last_activity or datetime.min)
    return jsonify({
        'user_id':       record.user_id,
        'workspace_id':  record.workspace_id,
        'last_login':    record.last_login.isoformat()    if record.last_login    else None,
        'last_activity': record.last_activity.isoformat() if record.last_activity else None,
        'last_logout':   record.last_logout.isoformat()   if record.last_logout   else None,
        'status':        record.get_status(),
        'is_online':     record.is_online(),
        'ip_address':    record.ip_address,
        'device_info':   record.device_info,
    }), 200


@activity_monitor_bp.route('/user/<int:user_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_user_activity(user_id):
    workspace_id = request.args.get('workspace_id', type=int)
    if not workspace_id:
        return jsonify({'error': 'workspace_id required'}), 400

    activity = UserActivity.query.filter_by(
        user_id=user_id, workspace_id=workspace_id).first()
    if not activity:
        return jsonify({'error': 'No activity data for this user'}), 404

    return jsonify({
        'user_id':       activity.user_id,
        'workspace_id':  activity.workspace_id,
        'last_login':    activity.last_login.isoformat()    if activity.last_login    else None,
        'last_activity': activity.last_activity.isoformat() if activity.last_activity else None,
        'last_logout':   activity.last_logout.isoformat()   if activity.last_logout   else None,
        'status':        activity.get_status(),
        'is_online':     activity.is_online(),
        'ip_address':    activity.ip_address,
        'device_info':   activity.device_info,
    }), 200


@activity_monitor_bp.route('/workspace', methods=['GET'])
@jwt_required()
@admin_required
def get_workspace_activity():
    workspace_id = request.args.get('workspace_id', type=int)
    if not workspace_id:
        return jsonify({'error': 'workspace_id required'}), 400

    pagination, err = _get_pagination_params()
    if err: return err

    query = (UserActivity.query
             .filter_by(workspace_id=workspace_id)
             .options(joinedload(UserActivity.user)))
    activities, total = paginate(query, pagination.page,
                                 pagination.limit, pagination.include_total)

    result = [{
        'user_id':       a.user_id,
        'name':          f"{a.user.first_name} {a.user.last_name}" if a.user else 'Unknown',
        'last_activity': a.last_activity.isoformat() if a.last_activity else None,
        'status':        a.get_status(),
        'is_online':     a.is_online(),
    } for a in activities]

    response = {'data': result, 'page': pagination.page, 'limit': pagination.limit}
    if total is not None:
        response['total'] = total
        response['pages'] = (total + pagination.limit - 1) // pagination.limit
    return jsonify(response), 200


@activity_monitor_bp.route('/active-users', methods=['GET'])
@jwt_required()
@admin_required
def get_active_users():
    workspace_id = request.args.get('workspace_id', type=int)
    if not workspace_id:
        return jsonify({'error': 'workspace_id required'}), 400

    pagination, err = _get_pagination_params()
    if err: return err

    threshold = datetime.utcnow() - ACTIVITY_CONFIG['active_threshold']
    query = (UserActivity.query
             .filter(UserActivity.workspace_id == workspace_id,
                     UserActivity.last_activity >= threshold)
             .options(joinedload(UserActivity.user)))
    activities, total = paginate(query, pagination.page,
                                 pagination.limit, pagination.include_total)

    result = [{
        'user_id':       a.user_id,
        'name':          f"{a.user.first_name} {a.user.last_name}" if a.user else 'Unknown',
        'last_activity': a.last_activity.isoformat(),
        'status':        'active',
        'is_online':     True,
    } for a in activities]

    response = {'data': result, 'page': pagination.page, 'limit': pagination.limit}
    if total is not None:
        response['total'] = total
        response['pages'] = (total + pagination.limit - 1) // pagination.limit
    return jsonify(response), 200


@activity_monitor_bp.route('/inactive-users', methods=['GET'])
@jwt_required()
@admin_required
def get_inactive_users():
    workspace_id = request.args.get('workspace_id', type=int)
    if not workspace_id:
        return jsonify({'error': 'workspace_id required'}), 400

    pagination, err = _get_pagination_params()
    if err: return err

    threshold = datetime.utcnow() - ACTIVITY_CONFIG['idle_threshold']
    query = (UserActivity.query
             .filter(UserActivity.workspace_id == workspace_id,
                     UserActivity.last_activity < threshold)
             .options(joinedload(UserActivity.user)))
    activities, total = paginate(query, pagination.page,
                                 pagination.limit, pagination.include_total)

    result = [{
        'user_id':       a.user_id,
        'name':          f"{a.user.first_name} {a.user.last_name}" if a.user else 'Unknown',
        'last_activity': a.last_activity.isoformat() if a.last_activity else None,
        'status':        a.get_status(),
        'is_online':     False,
    } for a in activities]

    response = {'data': result, 'page': pagination.page, 'limit': pagination.limit}
    if total is not None:
        response['total'] = total
        response['pages'] = (total + pagination.limit - 1) // pagination.limit
    return jsonify(response), 200


@activity_monitor_bp.route('/status-summary', methods=['GET'])
@jwt_required()
@admin_required
def get_status_summary():
    workspace_id = request.args.get('workspace_id', type=int)
    if not workspace_id:
        return jsonify({'error': 'workspace_id required'}), 400

    now               = datetime.utcnow()
    active_threshold  = now - ACTIVITY_CONFIG['active_threshold']
    idle_threshold    = now - ACTIVITY_CONFIG['idle_threshold']
    dead_threshold    = now - ACTIVITY_CONFIG['dead_threshold']

    summary = db.session.query(
        func.count().label('total'),
        func.sum(db.case(
            (UserActivity.last_activity >= active_threshold, 1), else_=0
        )).label('active'),
        func.sum(db.case(
            (and_(UserActivity.last_activity < active_threshold,
                  UserActivity.last_activity >= idle_threshold), 1), else_=0
        )).label('idle'),
        func.sum(db.case(
            (and_(UserActivity.last_activity < idle_threshold,
                  UserActivity.last_activity >= dead_threshold), 1), else_=0
        )).label('inactive'),
        func.sum(db.case(
            (UserActivity.last_activity < dead_threshold, 1), else_=0
        )).label('dead'),
    ).filter(UserActivity.workspace_id == workspace_id).first()

    return jsonify({
        'total':    summary.total    or 0,
        'active':   summary.active   or 0,
        'idle':     summary.idle     or 0,
        'inactive': summary.inactive or 0,
        'dead':     summary.dead     or 0,
    }), 200