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

# CORRECTED IMPORTS
from app.extensions import db, limiter
from app.models.alert import Alert
from app.models.user import User


logger = logging.getLogger(__name__)


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
            name="unique_user_workspace"
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
            "activity",
            uselist=False,
            lazy="joined"
        )
    )

    workspace = db.relationship(
        "Workspace",
        backref=db.backref(
            "user_activities",
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
            logger.exception(
                "user_activity_get_or_create_failed",
                extra={
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                }
            )

            return cls.query.filter_by(
                user_id=user_id,
                workspace_id=workspace_id
            ).first()

    def update_activity(self, request_obj=None):
        self.last_activity = datetime.utcnow()

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

        if request_obj:
            self.ip_address = request_obj.remote_addr
            self.device_info = request_obj.headers.get(
                "User-Agent",
                ""
            )

    def set_logout(self):
        self.last_logout = datetime.utcnow()

    def get_status(self):
        if not self.last_activity:
            return "unknown"

        now = datetime.utcnow()
        diff = now - self.last_activity

        if diff < timedelta(minutes=5):
            return "active"
        elif diff < timedelta(minutes=30):
            return "idle"
        elif diff < timedelta(hours=24):
            return "inactive"

        return "dead"

    def is_online(self):
        return self.get_status() in ("active", "idle")