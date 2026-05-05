import enum
from datetime import datetime
from app.extensions import db


class AlertType(enum.Enum):
    missing_attendance = "missing_attendance"
    late_attendance = "late_attendance"
    missing_update = "missing_update"
    task_overdue = "task_overdue"
    inactive_user = "inactive_user"


class AlertPriority(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Alert(db.Model):
    __tablename__ = "erp_alerts"

    id = db.Column(db.Integer, primary_key=True)

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id"),
        nullable=False,
        index=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    type = db.Column(
        db.Enum(AlertType),
        nullable=False
    )

    priority = db.Column(
        db.Enum(AlertPriority),
        nullable=False,
        default=AlertPriority.LOW
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    resolved = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    reference_id = db.Column(
        db.Integer,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    resolved_at = db.Column(
        db.DateTime,
        nullable=True
    )

    resolved_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    resolution_note = db.Column(
        db.Text,
        nullable=True
    )

    archived = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    archived_at = db.Column(
        db.DateTime,
        nullable=True
    )

    __table_args__ = (
        db.Index(
            "idx_erp_alert_lookup",
            "workspace_id",
            "user_id",
            "type",
            "resolved",
            "archived"
        ),
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("erp_alerts", lazy="dynamic")
    )

    resolver = db.relationship(
        "User",
        foreign_keys=[resolved_by]
    )

    workspace = db.relationship(
        "Workspace",
        backref=db.backref("erp_workspace_alerts", lazy="dynamic")
    )

    def to_dict(self):
        from app.models.user import User

        user = User.query.get(self.user_id) if self.user_id else None

        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "type": self.type.value if self.type else None,
            "priority": self.priority.value if self.priority else None,
            "message": self.message,
            "resolved": self.resolved,
            "reference_id": self.reference_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "archived": self.archived,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "user": {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
            } if user else None,
        }


class WorkspaceAlertConfig(db.Model):
    __tablename__ = "workspace_alert_configs"

    id = db.Column(db.Integer, primary_key=True)

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id"),
        nullable=False,
        unique=True
    )

    shift_start = db.Column(
        db.Time,
        default=datetime.strptime("09:00", "%H:%M").time
    )

    attendance_cutoff = db.Column(
        db.Time,
        default=datetime.strptime("10:00", "%H:%M").time
    )

    update_cutoff = db.Column(
        db.Time,
        default=datetime.strptime("18:00", "%H:%M").time
    )

    inactivity_days = db.Column(
        db.Integer,
        default=3
    )

    late_grace_minutes = db.Column(
        db.Integer,
        default=15
    )

    skip_weekends = db.Column(
        db.Boolean,
        default=True
    )

    workspace = db.relationship(
        "Workspace",
        backref=db.backref("alert_config", uselist=False)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "shift_start": self.shift_start.isoformat() if self.shift_start else None,
            "attendance_cutoff": self.attendance_cutoff.isoformat() if self.attendance_cutoff else None,
            "update_cutoff": self.update_cutoff.isoformat() if self.update_cutoff else None,
            "inactivity_days": self.inactivity_days,
            "late_grace_minutes": self.late_grace_minutes,
            "skip_weekends": self.skip_weekends,
        }