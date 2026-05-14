from enum import Enum
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON

db = SQLAlchemy()

# ========== Enums ==========
class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    APPROVED = "approved"
    REJECTED = "rejected"

class TaskComplexity(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    CRITICAL = "critical"

class TaskPriority(str, Enum):      # added for clarity
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class QualityRating(str, Enum):
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    GOOD = "good"
    EXCELLENT = "excellent"

COMPLEXITY_BASE_POINTS = {
    TaskComplexity.SMALL: 5,
    TaskComplexity.MEDIUM: 15,
    TaskComplexity.LARGE: 35,
    TaskComplexity.CRITICAL: 60,
}

QUALITY_MULTIPLIERS = {
    QualityRating.REJECTED: 0.0,
    QualityRating.ACCEPTED: 1.0,
    QualityRating.GOOD: 1.2,
    QualityRating.EXCELLENT: 1.5,
}

# ========== Task Model ==========
class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    startup_id = db.Column(db.Integer, db.ForeignKey('startups.id'), nullable=True)
    
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Use the proper enums
    priority = db.Column(db.Enum(TaskPriority), default=TaskPriority.MEDIUM)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.TODO)
    complexity = db.Column(db.Enum(TaskComplexity), nullable=True)   # new field
    
    visible_by = db.Column(db.String(50), default='all')  # 'public', 'team', 'private'
    tags = db.Column(JSON, default=list)
    labels = db.Column(JSON, default=list)
    
    due_date = db.Column(db.DateTime, nullable=True)
    completed_date = db.Column(db.DateTime, nullable=True)
    estimated_hours = db.Column(db.Float, nullable=True)
    actual_hours = db.Column(db.Float, nullable=True)
    
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    urgent = db.Column(db.Boolean, default=False)
    is_on_time = db.Column(db.Boolean, default=True)
    progress_percentage = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    task_owner = db.relationship(
        "User",
        back_populates="owned_tasks",
        foreign_keys=[user_id]
    )
    task_creator = db.relationship(
        "User",
        back_populates="created_tasks",
        foreign_keys=[created_by]
    )
    task_assignee = db.relationship(
        "User",
        back_populates="assigned_tasks",
        foreign_keys=[assigned_to]
    )
    parent_startup = db.relationship(
        "Startup",
        back_populates="startup_tasks",
        foreign_keys=[startup_id]
    )
    
    # ========== Helper Methods ==========
    def update_status(self, new_status: TaskStatus):
        """Update task status and handle completion date."""
        self.status = new_status
        if new_status == TaskStatus.DONE:
            self.completed_date = datetime.utcnow()
            self.progress_percentage = 100
            self.check_if_on_time()
        elif new_status == TaskStatus.IN_PROGRESS and self.progress_percentage == 0:
            self.progress_percentage = 50
        db.session.commit()
    
    def update_progress(self, percentage: int):
        """Update progress percentage (0-100)."""
        self.progress_percentage = max(0, min(100, percentage))
        if percentage >= 100:
            self.update_status(TaskStatus.DONE)
        elif percentage > 0 and self.status == TaskStatus.TODO:
            self.update_status(TaskStatus.IN_PROGRESS)
        db.session.commit()
    
    def check_if_on_time(self):
        """Set is_on_time based on due_date and completion."""
        if self.due_date and self.completed_date:
            self.is_on_time = self.completed_date <= self.due_date
        elif self.due_date and datetime.utcnow() > self.due_date:
            self.is_on_time = False
        else:
            self.is_on_time = True
        db.session.commit()
    
    def assign_to_user(self, user_id: int):
        self.assigned_to = user_id
        db.session.commit()
    
    def add_tag(self, tag: str):
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
        db.session.commit()
    
    def add_label(self, label: str, color: str = None):
        if self.labels is None:
            self.labels = []
        label_data = {'name': label}
        if color:
            label_data['color'] = color
        self.labels.append(label_data)
        db.session.commit()
    
    def log_time(self, hours: float):
        if self.actual_hours is None:
            self.actual_hours = 0.0
        self.actual_hours += hours
        db.session.commit()
    
    def is_overdue(self) -> bool:
        """Return True if task is not done and due date has passed."""
        if self.due_date and self.status != TaskStatus.DONE:
            return datetime.utcnow() > self.due_date
        return False
    
    def to_dict(self):
        """Convert task to dictionary, handling enums and relationships."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'startup_id': self.startup_id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority.value if self.priority else None,
            'status': self.status.value if self.status else None,
            'complexity': self.complexity.value if self.complexity else None,
            'tags': self.tags or [],
            'labels': self.labels or [],
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours,
            'assigned_to': self.assigned_to,
            'created_by': self.created_by,
            'is_on_time': self.is_on_time,
            'progress_percentage': self.progress_percentage,
            'is_overdue': self.is_overdue(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'visible_by': self.visible_by,
            'urgent': self.urgent,
            'assigned_user': {
                'id': self.task_assignee.id,
                'firstName': self.task_assignee.first_name,
                'lastName': self.task_assignee.last_name,
                'profilePicture': self.task_assignee.profile_picture
            } if self.task_assignee else None,
            'startup': {
                'id': self.parent_startup.id,
                'name': self.parent_startup.name,
                'logoUrl': self.parent_startup.logo_url
            } if self.parent_startup else None
        }