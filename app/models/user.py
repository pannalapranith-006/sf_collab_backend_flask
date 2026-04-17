from datetime import datetime, timedelta
from sqlalchemy import Enum, JSON
from app.extensions import db
from app.models.Enums import UserStatus, Privacy, Theme, EmailDigest, UserRoles
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=True)
    password = db.Column(db.String(255), nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)  # Updated on socket disconnect
    status = db.Column(Enum(UserStatus), default=UserStatus.active)
    role = db.Column(Enum(UserRoles), default=UserRoles.member)
    xp_points = db.Column(db.Integer, default=0)
    streak_days = db.Column(db.Integer, default=0)
    last_activity_date = db.Column(db.Date)
    builder_plan_id = db.Column(db.String(255), nullable=True) # Subscription plan
    founder_plan_id = db.Column(db.String(255), nullable=True) # Subscription plan
    credits = db.Column(db.Integer, default=0)  # For tracking user credits
    last_login_ip = db.Column(db.String(45), nullable=True)  # IPv4/IPv6

    # Computed/cached stats
    total_revenue = db.Column(db.Float, default=0.0)
    satisfaction_percentage = db.Column(db.Float, default=100.0)
    active_startups_count = db.Column(db.Integer, default=0)

    # -------------------------------------------------------------------------
    # Stripe Connect — needed for contributor/mentor withdrawal payouts
    # -------------------------------------------------------------------------
    stripe_connect_account_id = db.Column(db.String(255), nullable=True)

    # -------------------------------------------------------------------------
    # Reputation System — execution-based only (per SF Economy docs)
    # Rule: money/crystals/ratings must NEVER directly affect these scores.
    # -------------------------------------------------------------------------
    reputation_score      = db.Column(db.Float, default=0.0)
    milestones_completed  = db.Column(db.Integer, default=0)
    milestones_on_time    = db.Column(db.Integer, default=0)
    tasks_completed       = db.Column(db.Integer, default=0)
    tasks_on_time         = db.Column(db.Integer, default=0)
    collaborations_count  = db.Column(db.Integer, default=0)
    
    # Profile
    profile_picture = db.Column(db.String(500), nullable=True)
    profile_bio = db.Column(db.Text, nullable=True)
    profile_company = db.Column(db.String(255), nullable=True)
    profile_social_links = db.Column(JSON, default={})
    profile_country = db.Column(db.String(100), nullable=True)
    profile_city = db.Column(db.String(100), nullable=True)
    profile_timezone = db.Column(db.String(50), nullable=True)
    
    # Multi-Role Profile Fields (from ProfileSetup & MultiRoleProfileForm)
    # roles = db.Column(JSON, default=[])  # Array: ["founder", "builder", "investor", "influencer"]
    
    # Role-specific profile data stored as JSON
    # founder_profile = db.Column(JSON, default={})  # Founder-specific data
    # builder_profile = db.Column(JSON, default={})  # Builder-specific data
    # influencer_profile = db.Column(JSON, default={})  # Influencer-specific data
    # investor_profile = db.Column(JSON, default={})  # Investor-specific data
    
    # # Profile completion tracking
    # profile_setup_completed = db.Column(db.Boolean, default=False)  # Basic profile setup (ProfileSetup)
    # role_profile_completed = db.Column(db.Boolean, default=False)  # Multi-role profile (MultiRoleProfileForm)
    
    # Preferences
    pref_email_notifications = db.Column(db.Boolean, default=True)
    pref_push_notifications = db.Column(db.Boolean, default=True)
    pref_privacy = db.Column(Enum(Privacy), default=Privacy.public)
    pref_language = db.Column(db.String(10), default='en')
    pref_timezone = db.Column(db.String(50), default='UTC')
    pref_theme = db.Column(Enum(Theme), default=Theme.light)
    pref_builder_preferences = db.Column(db.String(50), default='')  # Builder-specific preferences
    # Notification Settings
    notif_new_comments = db.Column(db.Boolean, default=True)
    notif_new_likes = db.Column(db.Boolean, default=True)
    notif_new_suggestions = db.Column(db.Boolean, default=True)
    notif_join_requests = db.Column(db.Boolean, default=True)
    notif_approvals = db.Column(db.Boolean, default=True)
    notif_story_views = db.Column(db.Boolean, default=True)
    notif_post_engagement = db.Column(db.Boolean, default=True)
    notif_email_digest = db.Column(Enum(EmailDigest), default=EmailDigest.weekly)
    notif_quiet_hours_enabled = db.Column(db.Boolean, default=False)
    notif_quiet_hours_start = db.Column(db.String(5), default='22:00')
    notif_quiet_hours_end = db.Column(db.String(5), default='08:00')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Storage
    storage_used_mb = db.Column(db.Float, default=0.0, nullable=False)
    
    # ========== RELATIONSHIPS ==========
    
     # Marketplace seller profile (one-to-one)
    seller_profile = db.relationship(
        'Seller',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan'
    )
    
    
    mentor_profile = db.relationship(
        'MentorProfile',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan'
    )
    
    builder_profile = db.relationship(
        'BuilderProfile',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan'
    )
    
    # =========================================================================
    # WALLET & STORE RELATIONSHIPS - ADD THESE TO YOUR USER MODEL
    # =========================================================================

    # Wallet (one-to-one relationship)
    wallet = db.relationship("UserWallet", 
        back_populates="user", 
        uselist=False, 
        cascade="all, delete-orphan")

    # Wallet transactions
    wallet_transactions = db.relationship("WalletTransaction", 
        back_populates="user", 
        lazy='dynamic',
        cascade="all, delete-orphan")

    # Store purchases
    purchases = db.relationship('ProductPurchase', 
        back_populates='user', 
        lazy='dynamic',
        cascade="all, delete-orphan")

    # User inventory (owned items)
    inventory = db.relationship('UserInventory', 
        back_populates='user', 
        lazy='dynamic',
        cascade="all, delete-orphan")

    # Event token balances
    event_token_balances = db.relationship("EventTokenBalance", 
        back_populates="user",
        lazy='dynamic')

    # =========================================================================
    # ECONOMY LAYER 2 — Real-money Balance + Escrow
    # =========================================================================

    # Real-money balance (one-to-one)
    balance = db.relationship(
        'Balance',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan'
    )

    # Immutable audit log of every real-money movement
    balance_transactions = db.relationship(
        'BalanceTransaction',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # Escrow agreements where this user is the Payer (Founder)
    escrows_as_payer = db.relationship(
        'EscrowTransaction',
        foreign_keys='EscrowTransaction.payer_id',
        back_populates='payer',
        lazy='dynamic'
    )

    # Escrow agreements where this user is the Payee (Contributor)
    escrows_as_payee = db.relationship(
        'EscrowTransaction',
        foreign_keys='EscrowTransaction.payee_id',
        back_populates='payee',
        lazy='dynamic'
    )

    # =========================================================================
    # ECONOMY LAYER 3 — Crystals (visibility acceleration only — NOT money)
    # =========================================================================

    # Crystal wallet (one-to-one)
    crystal_wallet = db.relationship(
        'CrystalWallet',
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan'
    )

    # Crystal transaction log
    crystal_transactions = db.relationship(
        'CrystalTransaction',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # Visibility boosts purchased with crystals
    visibility_boosts = db.relationship(
        'VisibilityBoost',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    # Core Authentication & Profile
    refresh_tokens = db.relationship('RefreshToken', 
        back_populates='token_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='RefreshToken.user_id')
    
    notifications = db.relationship('Notification', 
        back_populates='notification_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='Notification.user_id')
    
    # Content Creation
    knowledge_posts = db.relationship('Knowledge', 
        back_populates='knowledge_author', 
        lazy='dynamic', 
        foreign_keys='Knowledge.author_id',
        cascade='all, delete-orphan')
    
    ideas = db.relationship('Idea', 
        back_populates='idea_creator', 
        lazy='dynamic', 
        foreign_keys='Idea.creator_id',
        cascade='all, delete-orphan')
    
    startups = db.relationship('Startup', 
        back_populates='startup_creator', 
        lazy='dynamic', 
        foreign_keys='Startup.creator_id',
        cascade='all, delete-orphan')
    
    stories = db.relationship('Story', 
        back_populates='story_author', 
        lazy='dynamic', 
        foreign_keys='Story.author_id',
        cascade='all, delete-orphan')
    
    authored_posts = db.relationship('Post', 
        back_populates='post_author', 
        lazy='dynamic', 
        foreign_keys='Post.author_id')
    
    # Comments & Engagement
    idea_comments = db.relationship('IdeaComment', 
        back_populates='comment_author', 
        lazy='dynamic', 
        foreign_keys='IdeaComment.author_id',
        cascade='all, delete-orphan')
    
    knowledge_comments = db.relationship('KnowledgeComment', 
        back_populates='comment_author', 
        lazy='dynamic', 
        foreign_keys='KnowledgeComment.author_id',
        cascade='all, delete-orphan')
    
    post_comments_list = db.relationship('PostComment', 
        back_populates='comment_author', 
        lazy='dynamic', 
        foreign_keys='PostComment.author_id',
        cascade='all, delete-orphan')
    
    # Likes & Bookmarks
    post_likes = db.relationship('PostLike', 
        back_populates='like_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='PostLike.user_id')
    
    resource_likes = db.relationship('ResourceLike', 
        back_populates='like_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='ResourceLike.user_id')
    
    startup_bookmarks = db.relationship('StartupBookmark', 
        back_populates='user', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='StartupBookmark.user_id')
    
    knowledge_bookmarks = db.relationship('KnowledgeBookmark', 
        back_populates='bookmark_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='KnowledgeBookmark.user_id')
    
    idea_bookmarks = db.relationship('IdeaBookmark', 
        back_populates='bookmark_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='IdeaBookmark.user_id')
    idea_likes = db.relationship('IdeaLike',
        back_populates='liker',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='IdeaLike.user_id')
    
    # Tasks & Projects (Three different relationships - all need unique back_populatess)
    owned_tasks = db.relationship('Task', 
        back_populates='task_owner', 
        lazy='dynamic', 
        foreign_keys='Task.user_id',
        cascade='all, delete-orphan')
    
    created_tasks = db.relationship('Task', 
        back_populates='task_creator', 
        lazy='dynamic', 
        foreign_keys='Task.created_by')
    
    assigned_tasks = db.relationship('Task', 
        back_populates='task_assignee', 
        lazy='dynamic', 
        foreign_keys='Task.assigned_to')
    
    project_goals = db.relationship('ProjectGoal', 
        back_populates='goal_owner', 
        lazy='dynamic', 
        foreign_keys='ProjectGoal.user_id',
        cascade='all, delete-orphan')
    
    # Team & Startup Relationships
    startup_memberships = db.relationship('StartupMember', 
        back_populates='member_user', 
        lazy='dynamic', 
        foreign_keys='StartupMember.user_id',
        cascade='all, delete-orphan')
    
    join_requests = db.relationship('JoinRequest', 
        back_populates='request_user', 
        lazy='dynamic', 
        foreign_keys='JoinRequest.user_id',
        cascade='all, delete-orphan')
    
    # Achievements & Growth
    user_achievements = db.relationship('UserAchievement', 
        back_populates='achievement_owner', 
        lazy='dynamic', 
        foreign_keys='UserAchievement.user_id',
        cascade='all, delete-orphan')
    
    # Change this line in the GrowthMetric relationship:
    growth_metrics = db.relationship('GrowthMetric', 
        back_populates='metric_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='GrowthMetric.user_id')
    
    # Chat & Messaging
    sent_messages = db.relationship('ChatMessage', 
        back_populates='message_sender', 
        lazy='dynamic', 
        foreign_keys='ChatMessage.sender_id',
        cascade='all, delete-orphan')
    
    created_conversations = db.relationship('ChatConversation', 
        back_populates='conversation_creator', 
        lazy='dynamic', 
        foreign_keys='ChatConversation.created_by_id',
        cascade='all, delete-orphan')
    
    conversations = db.relationship(
        'ChatConversation',
        secondary='conversation_participants',
        back_populates='participants',
        lazy='dynamic'
    )

    # Views & Analytics
    resource_views = db.relationship('ResourceView', 
        back_populates='view_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='ResourceView.user_id')
    
    story_views = db.relationship('StoryView', 
        back_populates='view_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='StoryView.user_id')
    
    # Downloads
    resource_downloads = db.relationship('ResourceDownload', 
        back_populates='download_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='ResourceDownload.user_id')
    
    # Suggestions
    suggestions = db.relationship('Suggestion', 
        back_populates='suggestion_author', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='Suggestion.author_id')
    
    # Calendar Events
    calendar_events = db.relationship('CalendarEvent', 
        back_populates='event_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='CalendarEvent.user_id')
    
    # Goal Milestones
    goal_milestones = db.relationship('GoalMilestone', 
        back_populates='milestone_owner', 
        lazy='dynamic', 
        cascade='all, delete-orphan',
        foreign_keys='GoalMilestone.user_id')
    
    sent_friend_requests = db.relationship(
        "FriendRequest",
        foreign_keys="FriendRequest.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )

    received_friend_requests = db.relationship(
        "FriendRequest",
        foreign_keys="FriendRequest.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan",
    )

    
    permissions = db.relationship(
        "UserPermission",
        foreign_keys="[UserPermission.user_id]",
        back_populates="permission_owner",
        cascade="all, delete-orphan"
    )
    user_roles = db.relationship(
        "UserRole",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined"
    )
    transactions = db.relationship("Transaction", back_populates="user")
    
    wallet = db.relationship(
        "UserWallet",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # Wallet/shop relationships (needed by WalletTransaction/ProductPurchase/UserInventory/EventTokenBalance)
    wallet_transactions = db.relationship(
        "WalletTransaction",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    purchases = db.relationship(
        "ProductPurchase",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    inventory = db.relationship(
        "UserInventory",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    event_token_balances = db.relationship(
        "EventTokenBalance",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    startup_views = db.relationship(
        'StartupView',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    contribution_ideas = db.relationship(
        'ContributionIdea',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    idea_comment_likes = db.relationship(
        'IdeaCommentLike',
        back_populates='liker',
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='IdeaCommentLike.user_id'
    )
    # ========== HELPER FUNCTIONS ==========
    
    
    def update_last_activity(self):
        """Update last activity date and maintain streak"""
        from app.services.streak_service import StreakService
        StreakService.update_streak(self.id)
    
    def add_xp_points(self, points: int):
        """Add XP points to user"""
        self.xp_points += points
        db.session.commit()

    def compute_reputation_score(self) -> float:
        """
        Compute and cache reputation score (0-100).
        Execution-based only — money/crystals/ratings never affect this.

        Weights:
          40% — milestone on-time rate
          30% — task on-time rate
          20% — XP points (capped at 5000)
          10% — collaboration breadth (capped at 10 startups)
        """
        score = 0.0

        if self.milestones_completed and self.milestones_completed > 0:
            score += min(self.milestones_on_time / self.milestones_completed, 1.0) * 40

        if self.tasks_completed and self.tasks_completed > 0:
            score += min(self.tasks_on_time / self.tasks_completed, 1.0) * 30

        score += min((self.xp_points or 0) / 5000, 1.0) * 20
        score += min((self.collaborations_count or 0) / 10, 1.0) * 10

        self.reputation_score = round(score, 2)
        db.session.commit()
        return self.reputation_score

    def record_milestone_completed(self, on_time: bool = True):
        """Call when user completes a milestone. Updates reputation."""
        self.milestones_completed = (self.milestones_completed or 0) + 1
        if on_time:
            self.milestones_on_time = (self.milestones_on_time or 0) + 1
        self.compute_reputation_score()

    def record_task_completed(self, on_time: bool = True):
        """Call when user completes a task. Updates reputation."""
        self.tasks_completed = (self.tasks_completed or 0) + 1
        if on_time:
            self.tasks_on_time = (self.tasks_on_time or 0) + 1
        self.compute_reputation_score()

    def record_collaboration(self):
        """Call when user joins a new startup. Updates reputation."""
        self.collaborations_count = (self.collaborations_count or 0) + 1
        self.compute_reputation_score()
    
    def verify_email(self):
        """Mark user's email as verified"""
        self.is_email_verified = True
        db.session.commit()
    
    def update_profile(self, profile_data: dict):
        """Update user profile information"""
        if 'picture' in profile_data:
            self.profile_picture = profile_data['picture']
        if 'bio' in profile_data:
            self.profile_bio = profile_data['bio']
        if 'company' in profile_data:
            self.profile_company = profile_data['company']
        if 'socialLinks' in profile_data:
            self.profile_social_links = profile_data['socialLinks']
        if 'country' in profile_data:
            self.profile_country = profile_data['country']
        if 'city' in profile_data:
            self.profile_city = profile_data['city']
        if 'timezone' in profile_data:
            self.profile_timezone = profile_data['timezone']
            self.pref_timezone = profile_data['timezone']
        
        db.session.commit()
    
    def update_preferences(self, preferences_data: dict):
        print(preferences_data, "UPDATING PREFERENCES")
        """Update user preferences"""
        if 'emailNotifications' in preferences_data:
            self.pref_email_notifications = preferences_data['emailNotifications']
        if 'pushNotifications' in preferences_data:
            self.pref_push_notifications = preferences_data['pushNotifications']
        if 'privacy' in preferences_data:
            self.pref_privacy = Privacy(preferences_data['privacy'])
        if 'language' in preferences_data:
            self.pref_language = preferences_data['language']
        if 'timezone' in preferences_data:
            self.pref_timezone = preferences_data['timezone']
        if 'theme' in preferences_data:
            self.pref_theme = Theme(preferences_data['theme'])
        if 'builderPreferences' in preferences_data:
            self.pref_builder_preferences = preferences_data['builderPreferences']
        db.session.commit()
    def update_notification_settings(self, notification_data: dict):
        """Update notification settings"""
        if 'newComments' in notification_data:
            self.notif_new_comments = notification_data['newComments']
        if 'newLikes' in notification_data:
            self.notif_new_likes = notification_data['newLikes']
        if 'newSuggestions' in notification_data:
            self.notif_new_suggestions = notification_data['newSuggestions']
        if 'joinRequests' in notification_data:
            self.notif_join_requests = notification_data['joinRequests']
        if 'approvals' in notification_data:
            self.notif_approvals = notification_data['approvals']
        if 'storyViews' in notification_data:
            self.notif_story_views = notification_data['storyViews']
        if 'postEngagement' in notification_data:
            self.notif_post_engagement = notification_data['postEngagement']
        if 'emailDigest' in notification_data:
            self.notif_email_digest = EmailDigest(notification_data['emailDigest'])
        
        if 'quietHours' in notification_data:
            quiet_hours = notification_data['quietHours']
            if 'enabled' in quiet_hours:
                self.notif_quiet_hours_enabled = quiet_hours['enabled']
            if 'start' in quiet_hours:
                self.notif_quiet_hours_start = quiet_hours['start']
            if 'end' in quiet_hours:
                self.notif_quiet_hours_end = quiet_hours['end']
        
        db.session.commit()
    
    def set_password(self, password: str):
        """Hash and set user password"""
        self.password = generate_password_hash(password)
        db.session.commit()
    
    def check_password(self, password: str) -> bool:
        """Check if provided password matches the hashed password"""
        return check_password_hash(self.password, password)
        
    def is_active(self):
        """Check if user is active"""
        return self.status == UserStatus.active
    def is_banned(self):
        """Check if user is banned"""
        return self.status == UserStatus.banned
    def is_admin(self):
        """Check if user has admin role"""
        return self.role == UserRoles.admin
    def deactivate(self):
        """Deactivate user account"""
        self.status = UserStatus.inactive
        db.session.commit()
    
    def activate(self):
        """Activate user account"""
        self.status = UserStatus.active
        db.session.commit()
    
    def get_full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    def get_timezone(self):
        """Get user's timezone for message display"""
        from app.utils.timezone_converter import get_user_timezone
        return get_user_timezone(self)
    
    def get_statistics(self):
        """Get comprehensive user statistics"""
        return {
            'total_ideas': self.ideas.count(),
            'total_tasks': self.owned_tasks.count(),
            'completed_tasks': self.owned_tasks.filter_by(status='completed').count(),
            'total_startups': self.startups.count(),
            'total_achievements': self.user_achievements.filter_by(is_completed=True).count(),
            'total_comments': (self.idea_comments.count() + 
                             self.knowledge_comments.count() + 
                             self.post_comments_list.count()),
            'total_likes_received': self._calculate_total_likes_received(),
            'engagement_score': self._calculate_engagement_score()
        }
    
    def _calculate_total_likes_received(self):
        """Calculate total likes received on user's content"""
        total_likes = 0
        total_likes += sum(idea.likes for idea in self.ideas)
        total_likes += sum(knowledge.likes for knowledge in self.knowledge_posts)
        total_likes += self.post_likes.count()
        return total_likes
    
    def _calculate_engagement_score(self):
        """Calculate user engagement score (0-100)"""
        activities = (
            self.ideas.count() * 2 +
            self.owned_tasks.filter_by(status='completed').count() * 1 +
            (self.idea_comments.count() + self.knowledge_comments.count() + self.post_comments_list.count()) * 0.5 +
            self._calculate_total_likes_received() * 0.5
        )
        return min(activities / 10, 100)
    
    def get_recent_activity(self, limit=10):
        activities = []

        try:
            # -------- Tasks --------
            for task in self.owned_tasks.filter_by(status='completed').all():
                if not task.completed_date:
                    continue  # skip broken data safely

                activities.append({
                    "type": "task_completed",
                    "id": task.id,
                    "title": task.title,
                    "timestamp": task.completed_date
                })

            # -------- Ideas --------
            for idea in self.ideas.all():
                if not idea.created_at:
                    continue

                activities.append({
                    "type": "idea_created",
                    "id": idea.id,
                    "title": idea.title,
                    "timestamp": idea.created_at
                })

            # -------- Comments --------
            for comment in self.comments.all():
                if not comment.created_at:
                    continue

                activities.append({
                    "type": "comment_created",
                    "id": comment.id,
                    "content": comment.content,
                    "timestamp": comment.created_at
                })

            # -------- Sort safely --------
            activities.sort(
                key=lambda x: x["timestamp"],
                reverse=True
            )

            return activities[:limit]

        except Exception as e:
            print(
                f"[get_recent_activity] Failed for user {getattr(self, 'id', 'unknown')}"
            )
            return []  # auth MUST never fail because of activity
    def _enum_to_value(self,value):
        return value.value if hasattr(value, "value") else value
    @staticmethod
    def get_user_by_phone_number(phone_number: str):
        return db.session.query(User).filter_by(phone_number=phone_number).first()

    def send_verification_code_to_sms(self):
        import random
        import string
        from app.services.sms_service import SMSService
        
        """Send verification code to user's phone number via SMS"""
        user = User.query.get(self.id)
        if not user.phone_number:
            raise ValueError("User phone number not set")
        
        # Generate random 6-digit code
        verification_code = ''.join(random.choices(string.digits, k=6))
        sms_service = SMSService()
        # Send SMS
        sms_service.send_sms(
            phone_number=user.phone_number,
            message=f"Your verification code is: {verification_code}"
        )
        
        return verification_code
    def to_dict(self, include_password=False, include_statistics=False, include_recent_activity=False, public=False):
        data = {
            'id': self.id,
            'firstName': self.first_name,
            'lastName': self.last_name,
            'fullName': self.get_full_name(),
            'profile_picture': self.profile_picture,
            'status': self._enum_to_value(self.status),
            'role': self._enum_to_value(self.role),
            'xp_points': self.xp_points,
            'streak_days': self.streak_days,
            'last_activity_date': self.last_activity_date.isoformat() if self.last_activity_date else None,
            'active_startups_count': self.active_startups_count,
            'reputation_score': self.reputation_score or 0.0,
            'milestones_completed': self.milestones_completed or 0,
            'milestones_on_time': self.milestones_on_time or 0,
            'tasks_completed': self.tasks_completed or 0,
            'tasks_on_time': self.tasks_on_time or 0,
            'collaborations_count': self.collaborations_count or 0,
            'profile': {
                'picture': self.profile_picture,
                'bio': self.profile_bio,
                'company': self.profile_company,
                'socialLinks': self.profile_social_links or {},
                'country': self.profile_country,
                'city': self.profile_city,
            },
            'builder_plan_id': self.builder_plan_id,
            'founder_plan_id': self.founder_plan_id,
            'createdAt': self.created_at.isoformat(),
            'roles': [ur.role for ur in self.user_roles],
            'startupViews': self.startup_views.count(),
        }
        
        # Private fields — only visible to the user themselves
        if not public:
            data.update({
                'email': self.email,
                'isEmailVerified': self.is_email_verified,
                'lastLogin': self.last_login.isoformat() if self.last_login else None,
                'last_seen': self.last_seen.isoformat() if self.last_seen else (
                    self.last_login.isoformat() if self.last_login else None
                ),
                'updatedAt': self.updated_at.isoformat(),
                'timezone': self.get_timezone(),
                'total_revenue': self.total_revenue,
                'satisfaction_percentage': self.satisfaction_percentage,
                'builder_plan_id': self.builder_plan_id,
                'founder_plan_id': self.founder_plan_id,
                'preferences': {
                    'emailNotifications': self.pref_email_notifications,
                    'pushNotifications': self.pref_push_notifications,
                    'privacy': self._enum_to_value(self.pref_privacy),
                    'language': self.pref_language,
                    'timezone': self.pref_timezone,
                    'theme': self._enum_to_value(self.pref_theme),
                    'builderPreferences': self.pref_builder_preferences
                },
                'notificationSettings': {
                    'newComments': self.notif_new_comments,
                    'newLikes': self.notif_new_likes,
                    'newSuggestions': self.notif_new_suggestions,
                    'joinRequests': self.notif_join_requests,
                    'approvals': self.notif_approvals,
                    'storyViews': self.notif_story_views,
                    'postEngagement': self.notif_post_engagement,
                    'emailDigest': self._enum_to_value(self.notif_email_digest),
                    'quietHours': {
                        'enabled': self.notif_quiet_hours_enabled,
                        'start': self.notif_quiet_hours_start,
                        'end': self.notif_quiet_hours_end
                    }
                },
                'permissions': [perm.to_dict() for perm in self.permissions],
                'credits': self.credits,
                'wallet': self.wallet.to_dict() if self.wallet else None,
            })
        
        if include_password:
            data['password'] = self.password
        
        if include_statistics:
            data['statistics'] = self.get_statistics()
        
        if include_recent_activity:
            data['recentActivity'] = self.get_recent_activity()
        
        return data
    
    def increase_storage_used(self, file_size_mb):
        """ Increase user's used storage when a file is uploaded """
        if not file_size_mb:
            return
        self.storage_used_mb = (self.storage_used_mb or 0) + file_size_mb

    def decrease_storage_used(self, file_size_mb):
        """ Decrease user's used storage when a file is deleted. """
        if not file_size_mb:
            return
        self.storage_used_mb = max((self.storage_used_mb or 0) - file_size_mb, 0)

    def update_storage_used(self, old_file_size_mb, new_file_size_mb):
        """ Update user's used storage when a file is updated/replaced. """
        if not old_file_size_mb or not new_file_size_mb:
            return
        self.storage_used_mb = max((self.storage_used_mb or 0) - old_file_size_mb + new_file_size_mb, 0)
        
    