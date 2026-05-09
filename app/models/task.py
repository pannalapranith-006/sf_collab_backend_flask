from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import Enum, JSON
from app.extensions import db

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    startup_id = db.Column(db.Integer, db.ForeignKey('startups.id'), nullable=True)
    
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(Enum('low', 'medium', 'high'), default='medium')
    status = db.Column(Enum('to_do', 'in_progress', 'completed', 'overdue'), default='today')
    visible_by = db.Column(db.String(50), default='all')  # 'public', 'team', 'private'
    tags = db.Column(JSON, default=[])
    labels = db.Column(JSON, default=[])
    
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
    
    # HELPER FUNCTIONS
    def update_status(self, new_status):
        """Update task status and handle completion"""
        self.status = new_status
        if new_status == 'completed':
            self.completed_date = datetime.utcnow()
            self.progress_percentage = 100
            self.check_if_on_time()
        elif new_status == 'in_progress':
            self.progress_percentage = 50
        db.session.commit()
    
    def update_progress(self, percentage):
        """Update progress percentage"""
        self.progress_percentage = max(0, min(100, percentage))
        if percentage >= 100:
            self.update_status('completed')
        elif percentage > 0:
            self.update_status('in_progress')
        db.session.commit()
    
    def check_if_on_time(self):
        """Check if task was completed on time"""
        if self.due_date and self.completed_date:
            self.is_on_time = self.completed_date <= self.due_date
        elif self.due_date and datetime.utcnow() > self.due_date:
            self.is_on_time = False
            self.status = 'overdue'
        db.session.commit()
    
    def assign_to_user(self, user_id):
        """Assign task to user"""
        self.assigned_to = user_id
        db.session.commit()
    
    def add_tag(self, tag):
        """Add tag to task"""
        if not self.tags:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
        db.session.commit()
    
    def add_label(self, label, color=None):
        """Add label to task"""
        if not self.labels:
            self.labels = []
        label_data = {'name': label}
        if color:
            label_data['color'] = color
        self.labels.append(label_data)
        db.session.commit()
    
    def log_time(self, hours):
        """Log actual hours worked"""
        if not self.actual_hours:
            self.actual_hours = 0
        self.actual_hours += hours
        db.session.commit()
    
    def is_overdue(self):
        """Check if task is overdue"""
        if self.due_date and self.status != 'completed':
            return datetime.utcnow() > self.due_date
        return False
    
    def _enum_to_value(self,value):
        return value.value if hasattr(value, "value") else value
        
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'startup_id': self.startup_id,
            'title': self.title,
            'description': self.description,
            'priority': self._enum_to_value(self.priority),
            'status':self._enum_to_value(self.status),
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