from datetime import datetime, timedelta

from sqlalchemy import Index, UniqueConstraint

from app.extensions import db
from app.models.alert import Alert
from app.models.user import User


ACTIVITY_CONFIG = {
    "active_threshold": timedelta(minutes=5),
    "idle_threshold": timedelta(minutes=30),
    "dead_threshold": timedelta(hours=24),
}


class UserActivity(db.Model):
    __tablename__ = "user_activity"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id"),
        nullable=False,
        index=True
    )

    last_login = db.Column(db.DateTime)

    last_activity = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        index=True
    )

    last_logout = db.Column(db.DateTime)

    ip_address = db.Column(db.String(45))
    device_info = db.Column(db.Text)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "workspace_id",
            name="unique_user_workspace_activity"
        ),
        Index(
            "idx_user_activity_workspace_last_activity",
            "workspace_id",
            "last_activity"
        ),
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "activity_record",
            uselist=False
        )
    )

    workspace = db.relationship(
        "Workspace",
        backref=db.backref(
            "activity_records",
            lazy="dynamic"
        )
    )

    @classmethod
    def get_or_create(cls, user_id, workspace_id):
        record = cls.query.filter_by(
            user_id=user_id,
            workspace_id=workspace_id
        ).first()

        if record:
            return record

        try:
            record = cls(
                user_id=user_id,
                workspace_id=workspace_id
            )
            db.session.add(record)
            db.session.flush()
            return record

        except Exception:
            db.session.rollback()
            return cls.query.filter_by(
                user_id=user_id,
                workspace_id=workspace_id
            ).first()

    def _clear_status_cache(self):
        if hasattr(self, "_cached_status"):
            del self._cached_status

    def update_activity(self, request_obj=None):
        self.last_activity = datetime.utcnow()
        self._clear_status_cache()

        if request_obj:
            self.ip_address = request_obj.remote_addr
            self.device_info = request_obj.headers.get(
                "User-Agent",
                ""
            )

    def set_login(self, request_obj=None):
        now = datetime.utcnow()

        self.last_login = now
        self.last_activity = now
        self._clear_status_cache()

        if request_obj:
            self.ip_address = request_obj.remote_addr
            self.device_info = request_obj.headers.get(
                "User-Agent",
                ""
            )

    def set_logout(self):
        self.last_logout = datetime.utcnow()
        self._clear_status_cache()

    def get_status(self):
        if not hasattr(self, "_cached_status"):
            if not self.last_activity:
                self._cached_status = "unknown"
            else:
                diff = datetime.utcnow() - self.last_activity

                if diff < ACTIVITY_CONFIG["active_threshold"]:
                    self._cached_status = "active"
                elif diff < ACTIVITY_CONFIG["idle_threshold"]:
                    self._cached_status = "idle"
                elif diff < ACTIVITY_CONFIG["dead_threshold"]:
                    self._cached_status = "inactive"
                else:
                    self._cached_status = "dead"

        return self._cached_status

    def is_online(self):
        return self.get_status() in ("active", "idle")

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "last_logout": self.last_logout.isoformat() if self.last_logout else None,
            "status": self.get_status(),
            "is_online": self.is_online(),
            "ip_address": self.ip_address,
            "device_info": self.device_info,
        }


class ActivityMonitorJobHealth(db.Model):
    __tablename__ = "activity_monitor_job_health"

    id = db.Column(db.Integer, primary_key=True)

    job_name = db.Column(
        db.String(100),
        nullable=False,
        unique=True
    )

    last_run_at = db.Column(db.DateTime)
    last_success_at = db.Column(db.DateTime)
    last_failure_at = db.Column(db.DateTime)

    last_duration_ms = db.Column(db.Integer)

    last_status = db.Column(
        db.String(20),
        nullable=False,
        default="never"
    )

    last_error = db.Column(db.Text)

    consecutive_failures = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class AnalyticsSnapshot(db.Model):
    __tablename__ = "analytics_snapshots"

    id = db.Column(db.Integer, primary_key=True)

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id"),
        nullable=False,
        index=True
    )

    date_range = db.Column(db.String(20))

    period_start = db.Column(
        db.Date,
        nullable=False
    )

    period_end = db.Column(
        db.Date,
        nullable=False
    )

    attendance_rate = db.Column(
        db.Float,
        default=0.0
    )

    task_completion_rate = db.Column(
        db.Float,
        default=0.0
    )

    update_consistency = db.Column(
        db.Float,
        default=0.0
    )

    active_users_daily = db.Column(
        db.Integer,
        default=0
    )

    active_users_weekly = db.Column(
        db.Integer,
        default=0
    )

    total_users = db.Column(
        db.Integer,
        default=0
    )

    overdue_tasks = db.Column(
        db.Integer,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id",
            "date_range",
            "period_start",
            name="uq_snapshot_period"
        ),
    )

    workspace = db.relationship(
        "Workspace",
        backref=db.backref(
            "analytics_snapshots",
            lazy="dynamic"
        )
    )

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "date_range": self.date_range,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "attendance_rate": self.attendance_rate,
            "task_completion_rate": self.task_completion_rate,
            "update_consistency": self.update_consistency,
            "active_users_daily": self.active_users_daily,
            "active_users_weekly": self.active_users_weekly,
            "total_users": self.total_users,
            "overdue_tasks": self.overdue_tasks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }