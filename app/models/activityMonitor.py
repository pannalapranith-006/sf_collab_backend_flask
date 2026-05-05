"""
Activity monitoring for SFCollab ERP.

Production hardening in this module:
- Rate-limited heartbeat writes.
- Structured logging helpers for searchable events.
- Pydantic validation for request payloads and pagination params.
- Cron health persistence with success/failure tracking.
- Runtime bootstrap for critical activity-monitoring indexes.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from flask_login import current_user, login_required
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import Index, UniqueConstraint, and_, func, inspect as sa_inspect
from sqlalchemy.orm import joinedload

from app.extensions import limiter
from models import Alert, User, db


logger = logging.getLogger(__name__)

ACTIVITY_CONFIG = {
    'active_threshold': timedelta(minutes=5),
    'idle_threshold': timedelta(minutes=30),
    'inactive_threshold': timedelta(minutes=30),
    'dead_threshold': timedelta(hours=24),
    'cron_interval_minutes': 5,
    'heartbeat_min_interval': timedelta(seconds=30),
    'middleware_min_interval': timedelta(seconds=30),
    'alert_cooldown_hours': 24,
    'pagination_limit': 50,
    'cron_batch_size': 500,
    'cron_max_batches': 1000,
    'alert_lookup_chunk_size': 100,
    'include_total_in_pagination': False,
}

ALERT_TYPE_MAP = {
    'idle': 'inactive_user_idle',
    'inactive': 'inactive_user_inactive',
    'dead': 'inactive_user_dead',
}

HEARTBEAT_RATE_LIMIT = "30 per minute"
MAX_PAGINATION_LIMIT = 100
CRON_JOB_NAME = 'inactivity_monitor'
SCHEDULER_ENABLE_ENV = 'ACTIVITY_MONITOR_RUN_SCHEDULER'
SCHEDULER_ENABLE_CONFIG_KEY = 'ACTIVITY_MONITOR_RUN_SCHEDULER'
ACTIVITY_PATH_PREFIX = '/api/activity'

REQUIRED_INDEXES = {
    'user_activity': {'idx_user_activity_workspace_last_activity'},
    'alerts': {'idx_alert_lookup'},
    'users': {'idx_users_id_is_active'},
}


class PaginationParams(BaseModel):
    model_config = ConfigDict(extra='forbid')

    page: int = Field(default=0, ge=0)
    limit: int = Field(default=ACTIVITY_CONFIG['pagination_limit'], ge=1, le=MAX_PAGINATION_LIMIT)
    include_total: bool = Field(default=ACTIVITY_CONFIG['include_total_in_pagination'])


class HeartbeatPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    client_timestamp: datetime | None = None


def _log(level, event, **context):
    logger.log(level, event, extra={'event': event, **context})


def _log_exception(event, **context):
    logger.exception(event, extra={'event': event, **context})


class UserActivity(db.Model):
    """Tracks user activity and presence per workspace."""

    __tablename__ = 'user_activity'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)
    last_login = db.Column(db.DateTime)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_logout = db.Column(db.DateTime)
    ip_address = db.Column(db.String(45))
    device_info = db.Column(db.Text)

    __table_args__ = (
        UniqueConstraint('user_id', 'workspace_id', name='unique_user_workspace'),
        Index('idx_user_activity_workspace_last_activity', 'workspace_id', 'last_activity'),
    )

    user = db.relationship('User', backref=db.backref('activity', uselist=False))

    @classmethod
    def get_or_create(cls, user_id, workspace_id):
        record = cls.query.filter_by(user_id=user_id, workspace_id=workspace_id).first()
        if record:
            return record

        try:
            record = cls(user_id=user_id, workspace_id=workspace_id)
            db.session.add(record)
            db.session.flush()
            return record
        except Exception:
            db.session.rollback()
            _log_exception(
                'user_activity_get_or_create_failed',
                user_id=user_id,
                workspace_id=workspace_id,
            )
            return cls.query.filter_by(user_id=user_id, workspace_id=workspace_id).first()

    def _clear_status_cache(self):
        if hasattr(self, '_cached_status'):
            del self._cached_status

    def update_activity(self, request_obj=None):
        self.last_activity = datetime.utcnow()
        self._clear_status_cache()
        if request_obj:
            new_ip = request_obj.remote_addr
            new_device = request_obj.headers.get('User-Agent', '')
            if self.ip_address != new_ip:
                self.ip_address = new_ip
            if self.device_info != new_device:
                self.device_info = new_device

    def set_login(self, request_obj=None):
        now = datetime.utcnow()
        self.last_login = now
        self.last_activity = now
        self._clear_status_cache()
        if request_obj:
            self.ip_address = request_obj.remote_addr
            self.device_info = request_obj.headers.get('User-Agent', '')

    def set_logout(self):
        self.last_logout = datetime.utcnow()
        self._clear_status_cache()

    def get_status(self):
        if not hasattr(self, '_cached_status'):
            now = datetime.utcnow()
            if not self.last_activity:
                self._cached_status = 'unknown'
            else:
                diff = now - self.last_activity
                if diff < ACTIVITY_CONFIG['active_threshold']:
                    self._cached_status = 'active'
                elif diff < ACTIVITY_CONFIG['idle_threshold']:
                    self._cached_status = 'idle'
                elif diff < ACTIVITY_CONFIG['dead_threshold']:
                    self._cached_status = 'inactive'
                else:
                    self._cached_status = 'dead'
        return self._cached_status

    def is_online(self):
        return self.get_status() in ('active', 'idle')


class ActivityMonitorJobHealth(db.Model):
    __tablename__ = 'activity_monitor_job_health'

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(100), nullable=False, unique=True)
    last_run_at = db.Column(db.DateTime)
    last_success_at = db.Column(db.DateTime)
    last_failure_at = db.Column(db.DateTime)
    last_duration_ms = db.Column(db.Integer)
    last_status = db.Column(db.String(20), nullable=False, default='never')
    last_error = db.Column(db.Text)
    consecutive_failures = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


activity_bp = Blueprint('activity', __name__, url_prefix='/api/activity')


@activity_bp.record_once
def _setup_activity_blueprint(state):
    app = state.app
    register_activity_middleware(app)
    validate_activity_monitoring_indexes()
    _log(logging.INFO, 'activity_blueprint_initialized')


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthenticated'}), 401
        if current_user.role not in ['admin', 'team_lead']:
            return jsonify({'error': 'Admin/Team lead access required'}), 403
        return func(*args, **kwargs)

    return wrapper


def _safe_commit(event, raise_on_error=False, **context):
    try:
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        _log_exception(f'{event}_failed', **context)
        if raise_on_error:
            raise
        return False


def _validate_payload(model_cls):
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}

    try:
        return model_cls.model_validate(payload), None
    except ValidationError as exc:
        _log(
            logging.WARNING,
            'activity_request_validation_failed',
            endpoint=request.path,
            user_id=getattr(current_user, 'id', None),
            errors=exc.errors(),
        )
        return None, (jsonify({'error': 'Invalid request payload', 'details': exc.errors()}), 400)


def _get_pagination_params():
    raw_params = {
        'page': request.args.get('page', 0),
        'limit': request.args.get('limit', ACTIVITY_CONFIG['pagination_limit']),
        'include_total': request.args.get('include_total', ACTIVITY_CONFIG['include_total_in_pagination']),
    }

    try:
        return PaginationParams.model_validate(raw_params), None
    except ValidationError as exc:
        _log(
            logging.WARNING,
            'activity_pagination_validation_failed',
            endpoint=request.path,
            user_id=getattr(current_user, 'id', None),
            errors=exc.errors(),
        )
        return None, (jsonify({'error': 'Invalid pagination parameters', 'details': exc.errors()}), 400)


def _get_cached_request_user():
    if hasattr(g, 'activity_request_user'):
        return g.activity_request_user

    user = current_user if getattr(current_user, 'is_authenticated', False) else None
    g.activity_request_user = user
    return user


def _should_track_request_activity():
    if request.method == 'OPTIONS':
        return False

    if request.path == '/health':
        return False

    # Avoid duplicate writes for endpoints that already update presence directly.
    if request.path.startswith(ACTIVITY_PATH_PREFIX):
        return False

    user = _get_cached_request_user()
    return user is not None


def _cron_health_table_available():
    try:
        inspector = sa_inspect(db.engine)
        return ActivityMonitorJobHealth.__tablename__ in inspector.get_table_names()
    except Exception:
        _log_exception('activity_cron_health_table_check_failed')
        return False


def validate_activity_monitoring_indexes():
    try:
        inspector = sa_inspect(db.engine)
        for table_name, required_indexes in REQUIRED_INDEXES.items():
            existing_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}
            missing_indexes = sorted(required_indexes - existing_indexes)
            if missing_indexes:
                _log(
                    logging.ERROR,
                    'activity_required_indexes_missing',
                    table_name=table_name,
                    missing_indexes=missing_indexes,
                )
            else:
                _log(
                    logging.INFO,
                    'activity_required_indexes_present',
                    table_name=table_name,
                    indexes=sorted(required_indexes),
                )
    except Exception:
        _log_exception('activity_index_validation_failed')


def _get_job_health(job_name):
    if not _cron_health_table_available():
        return None

    health = ActivityMonitorJobHealth.query.filter_by(job_name=job_name).first()
    if health:
        return health

    health = ActivityMonitorJobHealth(job_name=job_name)
    db.session.add(health)
    db.session.flush()
    return health


def _record_job_health_success(job_name, duration_ms, **context):
    finished_at = datetime.utcnow()
    health = _get_job_health(job_name)
    if health is None:
        _log(
            logging.WARNING,
            'activity_job_health_table_missing',
            job_name=job_name,
            duration_ms=duration_ms,
        )
        return
    health.last_run_at = finished_at
    health.last_success_at = finished_at
    health.last_duration_ms = duration_ms
    health.last_status = 'success'
    health.last_error = None
    health.consecutive_failures = 0
    _safe_commit(
        'activity_job_health_success',
        raise_on_error=False,
        job_name=job_name,
        duration_ms=duration_ms,
        **context,
    )


def _record_job_health_failure(job_name, duration_ms, error_message, **context):
    finished_at = datetime.utcnow()
    health = _get_job_health(job_name)
    if health is None:
        _log(
            logging.ERROR,
            'activity_job_health_table_missing_on_failure',
            job_name=job_name,
            duration_ms=duration_ms,
            error_message=error_message[:500],
        )
        return
    health.last_run_at = finished_at
    health.last_failure_at = finished_at
    health.last_duration_ms = duration_ms
    health.last_status = 'failed'
    health.last_error = error_message[:2000]
    health.consecutive_failures = (health.consecutive_failures or 0) + 1
    _safe_commit(
        'activity_job_health_failure',
        raise_on_error=False,
        job_name=job_name,
        duration_ms=duration_ms,
        **context,
    )
    _log(
        logging.ERROR,
        'activity_cron_failure_alert',
        job_name=job_name,
        duration_ms=duration_ms,
        consecutive_failures=health.consecutive_failures,
        error_message=error_message[:500],
        **context,
    )


def register_activity_middleware(app):
    @app.before_request
    def track_authenticated_activity():
        if not _should_track_request_activity():
            return

        user = _get_cached_request_user()
        if user is None:
            return

        workspace_id = getattr(user, 'workspace_id', None)
        if not workspace_id:
            return

        activity = UserActivity.get_or_create(user.id, workspace_id)
        now = datetime.utcnow()
        if activity.last_activity is None or (now - activity.last_activity) > ACTIVITY_CONFIG['middleware_min_interval']:
            activity.update_activity(request_obj=request)
            _safe_commit(
                'activity_middleware_update',
                raise_on_error=False,
                user_id=user.id,
                workspace_id=workspace_id,
                path=request.path,
            )


@activity_bp.route('/heartbeat', methods=['POST'])
@login_required
@limiter.limit(HEARTBEAT_RATE_LIMIT)
def heartbeat():
    _, validation_error = _validate_payload(HeartbeatPayload)
    if validation_error:
        return validation_error

    workspace_id = current_user.workspace_id
    if not workspace_id:
        return jsonify({'error': 'User has no workspace'}), 400

    activity = UserActivity.get_or_create(current_user.id, workspace_id)
    now = datetime.utcnow()
    if activity.last_activity is None or (now - activity.last_activity) > ACTIVITY_CONFIG['heartbeat_min_interval']:
        activity.update_activity(request_obj=request)
        if not _safe_commit(
            'activity_heartbeat_update',
            raise_on_error=False,
            user_id=current_user.id,
            workspace_id=workspace_id,
            remote_addr=request.remote_addr,
        ):
            return jsonify({'error': 'Failed to record heartbeat'}), 500

    return jsonify({'status': 'ok'})


def on_user_login(user, request_obj=None):
    workspace_id = user.workspace_id
    if not workspace_id:
        _log(logging.WARNING, 'activity_login_workspace_missing', user_id=getattr(user, 'id', None))
        return None

    activity = UserActivity.get_or_create(user.id, workspace_id)
    activity.set_login(request_obj)
    _safe_commit(
        'activity_login_update',
        raise_on_error=False,
        user_id=user.id,
        workspace_id=workspace_id,
    )
    return activity


def on_user_logout(user):
    workspace_id = user.workspace_id
    if not workspace_id:
        _log(logging.WARNING, 'activity_logout_workspace_missing', user_id=getattr(user, 'id', None))
        return

    activity = UserActivity.query.filter_by(user_id=user.id, workspace_id=workspace_id).first()
    if activity:
        activity.set_logout()
        _safe_commit(
            'activity_logout_update',
            raise_on_error=False,
            user_id=user.id,
            workspace_id=workspace_id,
        )


def _fetch_existing_alerts_chunked(pairs, alert_types):
    """
    Fetch unresolved alerts for given (workspace_id, user_id) pairs.
    Returns a dict keyed by (workspace_id, user_id, type).
    """
    if not pairs:
        return {}

    chunk_size = ACTIVITY_CONFIG['alert_lookup_chunk_size']
    alert_lookup = {}

    for i in range(0, len(pairs), chunk_size):
        chunk = pairs[i:i + chunk_size]
        alerts = Alert.query.filter(
            Alert.resolved == False,
            Alert.type.in_(alert_types),
        ).filter(
            db.tuple_(Alert.workspace_id, Alert.user_id).in_(chunk)
        ).all()
        for alert in alerts:
            key = (alert.workspace_id, alert.user_id, alert.type)
            alert_lookup[key] = alert.created_at

    return alert_lookup


def check_inactive_users_and_alert():
    """
    Scheduled job: scans only active users with stale last_activity.
    Uses cursor pagination and chunked alert lookup.
    """
    start_time = time.time()

    with current_app.app_context():
        now = datetime.utcnow()
        idle_threshold_time = now - ACTIVITY_CONFIG['idle_threshold']
        inactive_threshold_time = now - ACTIVITY_CONFIG['inactive_threshold']
        dead_threshold_time = now - ACTIVITY_CONFIG['dead_threshold']
        cooldown_delta = timedelta(hours=ACTIVITY_CONFIG['alert_cooldown_hours'])

        batch_size = ACTIVITY_CONFIG['cron_batch_size']
        max_batches = ACTIVITY_CONFIG['cron_max_batches']
        last_id = 0
        alerts_created = 0
        batch_count = 0
        total_processed = 0

        try:
            while batch_count < max_batches:
                batch_start = time.time()
                batch = db.session.query(UserActivity).join(
                    User, User.id == UserActivity.user_id
                ).filter(
                    User.is_active == True,
                    UserActivity.last_activity < idle_threshold_time,
                    UserActivity.id > last_id,
                ).options(
                    joinedload(UserActivity.user)
                ).order_by(UserActivity.id).limit(batch_size).all()

                if not batch:
                    break

                last_id = batch[-1].id
                total_processed += len(batch)
                pairs = [(act.workspace_id, act.user_id) for act in batch]
                alert_lookup = _fetch_existing_alerts_chunked(pairs, list(ALERT_TYPE_MAP.values()))

                for act in batch:
                    last_act = act.last_activity
                    if last_act < dead_threshold_time:
                        severity = 'dead'
                    elif last_act < inactive_threshold_time:
                        severity = 'inactive'
                    elif last_act < idle_threshold_time:
                        severity = 'idle'
                    else:
                        continue

                    alert_type = ALERT_TYPE_MAP[severity]
                    key = (act.workspace_id, act.user_id, alert_type)
                    last_alert_time = alert_lookup.get(key)

                    if last_alert_time and (now - last_alert_time) < cooldown_delta:
                        continue

                    db.session.add(
                        Alert(
                            workspace_id=act.workspace_id,
                            user_id=act.user_id,
                            type=alert_type,
                            message=f"User has been {severity} for a significant period.",
                            resolved=False,
                            created_at=now,
                        )
                    )
                    alerts_created += 1

                _safe_commit(
                    'activity_cron_batch_commit',
                    raise_on_error=True,
                    job_name=CRON_JOB_NAME,
                    batch_number=batch_count + 1,
                    batch_size=len(batch),
                )

                _log(
                    logging.DEBUG,
                    'activity_cron_batch_processed',
                    job_name=CRON_JOB_NAME,
                    batch_number=batch_count + 1,
                    batch_size=len(batch),
                    batch_duration_ms=int((time.time() - batch_start) * 1000),
                )

                batch_count += 1
                if len(batch) < batch_size:
                    break

            total_duration_ms = int((time.time() - start_time) * 1000)
            _record_job_health_success(
                CRON_JOB_NAME,
                total_duration_ms,
                batch_count=batch_count,
                total_processed=total_processed,
                alerts_created=alerts_created,
            )
            _log(
                logging.INFO,
                'activity_cron_finished',
                job_name=CRON_JOB_NAME,
                batch_count=batch_count,
                total_processed=total_processed,
                alerts_created=alerts_created,
                duration_ms=total_duration_ms,
            )
        except Exception as exc:
            total_duration_ms = int((time.time() - start_time) * 1000)
            _log_exception(
                'activity_cron_failed',
                job_name=CRON_JOB_NAME,
                batch_count=batch_count,
                total_processed=total_processed,
                alerts_created=alerts_created,
                duration_ms=total_duration_ms,
            )
            _record_job_health_failure(
                CRON_JOB_NAME,
                total_duration_ms,
                str(exc),
                batch_count=batch_count,
                total_processed=total_processed,
                alerts_created=alerts_created,
            )
            raise


def init_scheduler(app):
    if getattr(app, '_activity_monitor_scheduler_started', False):
        _log(logging.INFO, 'activity_scheduler_already_started', job_name=CRON_JOB_NAME)
        return

    scheduler_enabled = app.config.get(SCHEDULER_ENABLE_CONFIG_KEY)
    if scheduler_enabled is None:
        scheduler_enabled = os.getenv(SCHEDULER_ENABLE_ENV, '').lower() in {'1', 'true', 'yes'}

    if not scheduler_enabled:
        _log(
            logging.INFO,
            'activity_scheduler_disabled',
            job_name=CRON_JOB_NAME,
            config_key=SCHEDULER_ENABLE_CONFIG_KEY,
            env_var=SCHEDULER_ENABLE_ENV,
        )
        return

    try:
        from flask_apscheduler import APScheduler

        scheduler = APScheduler()
        scheduler.init_app(app)
        scheduler.start()
        app._activity_monitor_scheduler_started = True

        scheduler.add_job(
            id=CRON_JOB_NAME,
            func=check_inactive_users_and_alert,
            trigger='interval',
            minutes=ACTIVITY_CONFIG['cron_interval_minutes'],
            replace_existing=True,
        )
        _log(logging.INFO, 'activity_scheduler_started', job_name=CRON_JOB_NAME)
    except ImportError:
        _log(logging.WARNING, 'activity_scheduler_not_started', reason='Flask-APScheduler not installed')
    except Exception:
        _log_exception('activity_scheduler_start_failed', job_name=CRON_JOB_NAME)


def paginate(query, page, limit, include_total=False):
    total = None
    if include_total:
        total = query.count()
    items = query.limit(limit).offset(page * limit).all()
    return items, total


@activity_bp.route('/me', methods=['GET'])
@login_required
def get_my_activity():
    workspace_id = current_user.workspace_id
    if not workspace_id:
        return jsonify({'error': 'User has no workspace'}), 400

    activity = UserActivity.query.filter_by(user_id=current_user.id, workspace_id=workspace_id).first()
    if not activity:
        return jsonify({'status': 'no_data'})

    return jsonify({
        'user_id': activity.user_id,
        'last_login': activity.last_login.isoformat() if activity.last_login else None,
        'last_activity': activity.last_activity.isoformat() if activity.last_activity else None,
        'last_logout': activity.last_logout.isoformat() if activity.last_logout else None,
        'status': activity.get_status(),
        'is_online': activity.is_online(),
        'ip_address': activity.ip_address,
        'device_info': activity.device_info,
    })


@activity_bp.route('/user/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user_activity(user_id):
    workspace_id = current_user.workspace_id
    if not workspace_id:
        return jsonify({'error': 'Workspace context missing'}), 400

    activity = UserActivity.query.filter_by(user_id=user_id, workspace_id=workspace_id).first()
    if not activity:
        return jsonify({'error': 'No activity data for this user'}), 404

    return jsonify({
        'user_id': activity.user_id,
        'last_login': activity.last_login.isoformat() if activity.last_login else None,
        'last_activity': activity.last_activity.isoformat() if activity.last_activity else None,
        'last_logout': activity.last_logout.isoformat() if activity.last_logout else None,
        'status': activity.get_status(),
        'is_online': activity.is_online(),
        'ip_address': activity.ip_address,
        'device_info': activity.device_info,
    })


@activity_bp.route('/workspace', methods=['GET'])
@login_required
@admin_required
def get_workspace_activity():
    workspace_id = current_user.workspace_id
    if not workspace_id:
        return jsonify({'error': 'Workspace context missing'}), 400

    pagination, validation_error = _get_pagination_params()
    if validation_error:
        return validation_error

    query = UserActivity.query.filter_by(workspace_id=workspace_id).options(joinedload(UserActivity.user))
    activities, total = paginate(query, pagination.page, pagination.limit, pagination.include_total)

    result = [{
        'user_id': activity.user_id,
        'name': activity.user.name if activity.user else 'Unknown',
        'last_activity': activity.last_activity.isoformat() if activity.last_activity else None,
        'status': activity.get_status(),
        'is_online': activity.is_online(),
    } for activity in activities]

    response = {'data': result, 'page': pagination.page, 'limit': pagination.limit}
    if total is not None:
        response['total'] = total
        response['pages'] = (total + pagination.limit - 1) // pagination.limit
    return jsonify(response)


@activity_bp.route('/active-users', methods=['GET'])
@login_required
@admin_required
def get_active_users():
    workspace_id = current_user.workspace_id
    if not workspace_id:
        return jsonify({'error': 'Workspace context missing'}), 400

    pagination, validation_error = _get_pagination_params()
    if validation_error:
        return validation_error

    threshold = datetime.utcnow() - ACTIVITY_CONFIG['active_threshold']
    query = UserActivity.query.filter(
        UserActivity.workspace_id == workspace_id,
        UserActivity.last_activity >= threshold,
    ).options(joinedload(UserActivity.user))

    activities, total = paginate(query, pagination.page, pagination.limit, pagination.include_total)

    result = [{
        'user_id': activity.user_id,
        'name': activity.user.name if activity.user else 'Unknown',
        'last_activity': activity.last_activity.isoformat(),
        'status': 'active',
    } for activity in activities]

    response = {'data': result, 'page': pagination.page, 'limit': pagination.limit}
    if total is not None:
        response['total'] = total
        response['pages'] = (total + pagination.limit - 1) // pagination.limit
    return jsonify(response)


@activity_bp.route('/inactive-users', methods=['GET'])
@login_required
@admin_required
def get_inactive_users():
    workspace_id = current_user.workspace_id
    if not workspace_id:
        return jsonify({'error': 'Workspace context missing'}), 400

    pagination, validation_error = _get_pagination_params()
    if validation_error:
        return validation_error

    threshold = datetime.utcnow() - ACTIVITY_CONFIG['idle_threshold']
    query = UserActivity.query.filter(
        UserActivity.workspace_id == workspace_id,
        UserActivity.last_activity < threshold,
    ).options(joinedload(UserActivity.user))

    activities, total = paginate(query, pagination.page, pagination.limit, pagination.include_total)

    result = [{
        'user_id': activity.user_id,
        'name': activity.user.name if activity.user else 'Unknown',
        'last_activity': activity.last_activity.isoformat() if activity.last_activity else None,
        'status': activity.get_status(),
    } for activity in activities]

    response = {'data': result, 'page': pagination.page, 'limit': pagination.limit}
    if total is not None:
        response['total'] = total
        response['pages'] = (total + pagination.limit - 1) // pagination.limit
    return jsonify(response)


@activity_bp.route('/status-summary', methods=['GET'])
@login_required
@admin_required
def get_status_summary():
    workspace_id = current_user.workspace_id
    if not workspace_id:
        return jsonify({'error': 'Workspace context missing'}), 400

    now = datetime.utcnow()
    active_threshold = now - ACTIVITY_CONFIG['active_threshold']
    idle_threshold = now - ACTIVITY_CONFIG['idle_threshold']
    dead_threshold = now - ACTIVITY_CONFIG['dead_threshold']

    summary = db.session.query(
        func.count().label('total'),
        func.sum(
            db.case(
                (UserActivity.last_activity >= active_threshold, 1),
                else_=0,
            )
        ).label('active'),
        func.sum(
            db.case(
                (
                    and_(
                        UserActivity.last_activity < active_threshold,
                        UserActivity.last_activity >= idle_threshold,
                    ),
                    1,
                ),
                else_=0,
            )
        ).label('idle'),
        func.sum(
            db.case(
                (
                    and_(
                        UserActivity.last_activity < idle_threshold,
                        UserActivity.last_activity >= dead_threshold,
                    ),
                    1,
                ),
                else_=0,
            )
        ).label('inactive'),
        func.sum(
            db.case(
                (UserActivity.last_activity < dead_threshold, 1),
                else_=0,
            )
        ).label('dead'),
    ).filter(UserActivity.workspace_id == workspace_id).first()

    return jsonify({
        'total': summary.total or 0,
        'active': summary.active or 0,
        'idle': summary.idle or 0,
        'inactive': summary.inactive or 0,
        'dead': summary.dead or 0,
    })
