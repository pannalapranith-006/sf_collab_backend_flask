# models/analytics.py
# SFCollab ERP — Analytics Snapshot Model
# DB layer ONLY — no routes, no auth, no business logic, no Flask imports

from __future__ import annotations

from datetime import datetime

from app.extensions import db


class AnalyticsSnapshot(db.Model):
    """
    Append-only snapshot written by the nightly cron.
    One row per (workspace_id, date_range, period_start).
    Old rows are never overwritten — full trend history is preserved.
    """

    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id", "date_range", "period_start",
            name="uq_snapshot_period",
        ),
    )

    id                   = db.Column(db.Integer, primary_key=True)
    workspace_id         = db.Column(db.Integer, nullable=False, index=True)
    date_range           = db.Column(db.String(20))          # daily / weekly / monthly
    period_start         = db.Column(db.Date, nullable=False)
    period_end           = db.Column(db.Date, nullable=False)
    attendance_rate      = db.Column(db.Float, default=0.0)
    task_completion_rate = db.Column(db.Float, default=0.0)
    update_consistency   = db.Column(db.Float, default=0.0)
    active_users_daily   = db.Column(db.Integer, default=0)
    active_users_weekly  = db.Column(db.Integer, default=0)
    total_users          = db.Column(db.Integer, default=0)
    overdue_tasks        = db.Column(db.Integer, default=0)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        # Explicit field list — avoids leaking SQLAlchemy internal state
        return {
            "id":                   self.id,
            "workspace_id":         self.workspace_id,
            "date_range":           self.date_range,
            "period_start":         str(self.period_start),
            "period_end":           str(self.period_end),
            "attendance_rate":      self.attendance_rate,
            "task_completion_rate": self.task_completion_rate,
            "update_consistency":   self.update_consistency,
            "active_users_daily":   self.active_users_daily,
            "active_users_weekly":  self.active_users_weekly,
            "total_users":          self.total_users,
            "overdue_tasks":        self.overdue_tasks,
            "created_at":           self.created_at.isoformat() if self.created_at else None,
        }