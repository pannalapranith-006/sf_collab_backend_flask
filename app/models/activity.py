from datetime import datetime
from app.extensions import db
from app.models.user import User  

class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    action = db.Column(db.String(255), nullable=False, index=True)  
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        lazy="joined"
    )

    def __repr__(self):
        return f"<Activity id={self.id} user_id={self.user_id} action={self.action}>"

    def to_dict(self, include_user_info=False):
        """Convert activity to dictionary"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Include user info if requested and available
        if include_user_info and self.user:
            data['user'] = {
                'id': self.user.id,
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
                'email': self.user.email
            }
        
        return data

    @classmethod
    def log(cls, action, user_id=None, details=None, request=None):
        """Log an activity with optional request context"""
        activity_data = {
            'user_id': user_id,
            'action': action,
            'details': details
        }
        
        # Add request info if available
        if request:
            activity_data['ip_address'] = request.remote_addr
            activity_data['user_agent'] = request.headers.get('User-Agent')
        
        activity = cls(**activity_data)
        db.session.add(activity)
        db.session.commit()
        return activity

    @classmethod
    def get_recent_activities(cls, limit=50, user_id=None, action=None):
        """Get recent activities with optional filters"""
        query = cls.query
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        if action:
            query = query.filter_by(action=action)
        
        return query.order_by(cls.created_at.desc()).limit(limit).all()

    def get_formatted_date(self, timezone='UTC'):
        """Get formatted date string"""
        # You can implement timezone conversion here if needed
        return self.created_at.strftime('%Y-%m-%d %H:%M:%S')