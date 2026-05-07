"""
SF Collab Notification Templates
Comprehensive notification templates for all system events
Based on SF Collab Notification System Documentation
"""

NOTIFICATION_TEMPLATES = {
    # ============================================
    # 1. ACCOUNT & SYSTEM NOTIFICATIONS
    # ============================================
    "ACCOUNT_CREATED": {
        "type": "info",
        "category": "account",
        "priority": "medium",
        "title": "Welcome to SF Collab! 🎉",
        "message": "Your account has been successfully created. Welcome aboard!",
    },
    "EMAIL_VERIFIED": {
        "type": "success",
        "category": "account",
        "priority": "medium",
        "title": "Email Verified ✓",
        "message": "Your email has been successfully verified.",
    },
    "PASSWORD_CHANGED": {
        "type": "warning",
        "category": "account",
        "priority": "high",
        "title": "Password Changed",
        "message": "Your password was successfully changed. If this wasn't you, please contact support immediately.",
    },
    "PASSWORD_RESET": {
        "type": "info",
        "category": "account",
        "priority": "high",
        "title": "Password Reset Requested",
        "message": "A password reset was requested for your account. If this wasn't you, please secure your account.",
    },
    "NEW_DEVICE_LOGIN": {
        "type": "warning",
        "category": "account",
        "priority": "high",
        "title": "New Device Login",
        "message": "Your account was accessed from a new device in {location}. If this wasn't you, please secure your account.",
    },
    "ACCOUNT_ROLE_UPDATED": {
        "type": "info",
        "category": "account",
        "priority": "high",
        "title": "Account Role Updated",
        "message": "Your account role has been updated to {role}.",
    },
    "PERMISSION_CHANGED": {
        "type": "info",
        "category": "account",
        "priority": "medium",
        "title": "Permissions Updated",
        "message": "Your permissions have been updated.",
    },
    "ACCOUNT_SUSPENDED": {
        "type": "error",
        "category": "account",
        "priority": "critical",
        "title": "Account Suspended",
        "message": "Your account has been suspended. Reason: {reason}",
    },
    "ACCOUNT_REINSTATED": {
        "type": "success",
        "category": "account",
        "priority": "high",
        "title": "Account Reinstated",
        "message": "Your account has been reinstated. Welcome back!",
    },
    "PLATFORM_MAINTENANCE": {
        "type": "warning",
        "category": "system",
        "priority": "high",
        "title": "Scheduled Maintenance",
        "message": "Platform maintenance scheduled for {date}. Expected downtime: {duration}",
    },
    "PLATFORM_DOWNTIME": {
        "type": "error",
        "category": "system",
        "priority": "critical",
        "title": "Platform Downtime",
        "message": "The platform is currently experiencing issues. We're working to resolve this.",
    },
    "TERMS_POLICY_UPDATE": {
        "type": "info",
        "category": "system",
        "priority": "medium",
        "title": "Terms & Policies Updated",
        "message": "Our terms and policies have been updated. Please review the changes.",
    },

    # ============================================
    # 2. COLLABORATION & SOCIAL NOTIFICATIONS
    # ============================================
    "USER_FOLLOWED": {
        "type": "info",
        "category": "social",
        "priority": "low",
        "title": "New Follower",
        "message": "{actor_name} started following you.",
    },
    "USER_MENTIONED": {
        "type": "info",
        "category": "social",
        "priority": "medium",
        "title": "You Were Mentioned",
        "message": "{actor_name} mentioned you in a {entity_type}.",
    },
    "COMMENT_REPLY": {
        "type": "info",
        "category": "social",
        "priority": "medium",
        "title": "New Reply",
        "message": "{actor_name} replied to your comment.",
    },
    "POST_LIKED": {
        "type": "info",
        "category": "social",
        "priority": "low",
        "title": "Your Post Was Liked",
        "message": "{actor_name} liked your post.",
    },
    "POST_REACTED": {
        "type": "info",
        "category": "social",
        "priority": "low",
        "title": "New Reaction",
        "message": "{actor_name} reacted to your {entity_type}.",
    },
    "CONTENT_SHARED": {
        "type": "info",
        "category": "social",
        "priority": "low",
        "title": "Content Shared",
        "message": "{actor_name} shared your content.",
    },
    "NEW_COMMENT": {
        "type": "info",
        "category": "social",
        "priority": "medium",
        "title": "New Comment",
        "message": "{actor_name} commented on your {entity_type}.",
    },
    "NEW_POST_IN_CATEGORY": {
        "type": "info",
        "category": "social",
        "priority": "low",
        "title": "New Post in {category}",
        "message": "New post in a category you follow: {title}",
    },
    "NEW_COMMUNITY_MEMBER": {
        "type": "info",
        "category": "social",
        "priority": "low",
        "title": "New Member Joined",
        "message": "{actor_name} joined {entity_name}.",
    },

    # ============================================
    # 3. IDEAS & INNOVATION NOTIFICATIONS
    # ============================================
    "IDEA_SUBMITTED": {
        "type": "success",
        "category": "idea",
        "priority": "medium",
        "title": "Idea Submitted",
        "message": "Your idea '{title}' has been submitted successfully.",
    },
    "IDEA_FEEDBACK_RECEIVED": {
        "type": "info",
        "category": "idea",
        "priority": "medium",
        "title": "New Feedback on Your Idea",
        "message": "{actor_name} provided feedback on your idea '{title}'.",
    },
    "IDEA_APPROVED": {
        "type": "success",
        "category": "idea",
        "priority": "high",
        "title": "Idea Approved! 🎉",
        "message": "Your idea '{title}' has been approved!",
    },
    "IDEA_REJECTED": {
        "type": "warning",
        "category": "idea",
        "priority": "medium",
        "title": "Idea Not Approved",
        "message": "Your idea '{title}' was not approved. Reason: {reason}",
    },
    "IDEA_FLAGGED": {
        "type": "warning",
        "category": "idea",
        "priority": "high",
        "title": "Idea Flagged",
        "message": "Your idea '{title}' has been flagged for review.",
    },
    "IDEA_STATUS_CHANGED": {
        "type": "info",
        "category": "idea",
        "priority": "medium",
        "title": "Idea Status Updated",
        "message": "Your idea '{title}' status changed from {old_status} to {new_status}.",
    },
    "IDEA_TO_PROJECT": {
        "type": "success",
        "category": "idea",
        "priority": "high",
        "title": "Idea Promoted to Project! 🚀",
        "message": "Your idea '{title}' has been promoted to a project!",
    },
    "IDEA_TO_STARTUP": {
        "type": "success",
        "category": "idea",
        "priority": "high",
        "title": "Idea Became a Startup! 🌟",
        "message": "Your idea '{title}' has evolved into a startup!",
    },
    "IDEA_VOTED": {
        "type": "info",
        "category": "idea",
        "priority": "low",
        "title": "Vote on Your Idea",
        "message": "{actor_name} voted on your idea '{title}'.",
    },
    "IDEA_MILESTONE_REACHED": {
        "type": "success",
        "category": "idea",
        "priority": "medium",
        "title": "Milestone Reached! 🎯",
        "message": "Your idea '{title}' reached {milestone}!",
    },
    "IDEA_COLLABORATION_REQUEST": {
        "type": "info",
        "category": "idea",
        "priority": "high",
        "title": "Collaboration Request",
        "message": "{actor_name} wants to collaborate on your idea '{title}'.",
    },

    # ============================================
    # 4. STARTUP & PROJECT NOTIFICATIONS
    # ============================================
    "STARTUP_CREATED": {
        "type": "success",
        "category": "startup",
        "priority": "high",
        "title": "Startup Created! 🚀",
        "message": "Your startup '{name}' has been successfully created.",
    },
    "STARTUP_PROFILE_UPDATED": {
        "type": "info",
        "category": "startup",
        "priority": "low",
        "title": "Startup Profile Updated",
        "message": "The profile for '{name}' has been updated.",
    },
    "PROJECT_CREATED": {
        "type": "success",
        "category": "project",
        "priority": "medium",
        "title": "Project Created",
        "message": "New project '{name}' has been created.",
    },
    "PROJECT_STATUS_CHANGED": {
        "type": "info",
        "category": "project",
        "priority": "medium",
        "title": "Project Status Changed",
        "message": "Project '{name}' status changed to {status}.",
    },
    "ADDED_TO_STARTUP": {
        "type": "success",
        "category": "startup",
        "priority": "high",
        "title": "Added to Startup",
        "message": "You've been added to '{startup_name}' as {role}.",
    },
    "REMOVED_FROM_STARTUP": {
        "type": "warning",
        "category": "startup",
        "priority": "high",
        "title": "Removed from Startup",
        "message": "You've been removed from '{startup_name}'.",
    },
    "STARTUP_ROLE_ASSIGNED": {
        "type": "info",
        "category": "startup",
        "priority": "high",
        "title": "Role Assigned",
        "message": "You've been assigned the role of {role} in '{startup_name}'.",
    },
    "STARTUP_OWNERSHIP_CHANGED": {
        "type": "warning",
        "category": "startup",
        "priority": "critical",
        "title": "Ownership Changed",
        "message": "Ownership of '{startup_name}' has been transferred to {new_owner}.",
    },
    "STARTUP_LEADERSHIP_CHANGED": {
        "type": "info",
        "category": "startup",
        "priority": "high",
        "title": "Leadership Changed",
        "message": "Leadership changes in '{startup_name}': {changes}",
    },
    "STARTUP_MILESTONE_ACHIEVED": {
        "type": "success",
        "category": "startup",
        "priority": "high",
        "title": "Milestone Achieved! 🎉",
        "message": "'{startup_name}' achieved {milestone}!",
    },

    # ============================================
    # 5. TASK & EXECUTION NOTIFICATIONS
    # ============================================
    "TASK_ASSIGNED": {
        "type": "info",
        "category": "task",
        "priority": "high",
        "title": "New Task Assigned",
        "message": "{actor_name} assigned you a task: '{title}'",
    },
    "TASK_UPDATED": {
        "type": "info",
        "category": "task",
        "priority": "medium",
        "title": "Task Updated",
        "message": "Task '{title}' has been updated.",
    },
    "TASK_COMPLETED": {
        "type": "success",
        "category": "task",
        "priority": "medium",
        "title": "Task Completed ✓",
        "message": "{actor_name} completed task '{title}'.",
    },
    "TASK_OVERDUE": {
        "type": "error",
        "category": "task",
        "priority": "critical",
        "title": "Task Overdue!",
        "message": "Task '{title}' is overdue. Due date was {due_date}.",
    },
    "TASK_REASSIGNED": {
        "type": "info",
        "category": "task",
        "priority": "high",
        "title": "Task Reassigned",
        "message": "Task '{title}' was reassigned to {new_assignee}.",
    },
    "TASK_COMMENT_ADDED": {
        "type": "info",
        "category": "task",
        "priority": "medium",
        "title": "New Task Comment",
        "message": "{actor_name} commented on task '{title}'.",
    },
    "TASK_FILE_ATTACHED": {
        "type": "info",
        "category": "task",
        "priority": "low",
        "title": "File Attached to Task",
        "message": "{actor_name} attached a file to task '{title}'.",
    },
    "TASK_DEADLINE_APPROACHING": {
        "type": "warning",
        "category": "task",
        "priority": "high",
        "title": "Deadline Approaching",
        "message": "Task '{title}' is due {time_until}.",
    },
    "MEETING_SCHEDULED": {
        "type": "info",
        "category": "task",
        "priority": "high",
        "title": "Meeting Scheduled",
        "message": "Meeting '{title}' scheduled for {date}.",
    },
    "MEETING_UPDATED": {
        "type": "info",
        "category": "task",
        "priority": "medium",
        "title": "Meeting Updated",
        "message": "Meeting '{title}' has been updated.",
    },
    "MEETING_CANCELED": {
        "type": "warning",
        "category": "task",
        "priority": "high",
        "title": "Meeting Canceled",
        "message": "Meeting '{title}' scheduled for {date} has been canceled.",
    },

    # ============================================
    # 6. MESSAGING & COMMUNICATION
    # ============================================
    "NEW_DIRECT_MESSAGE": {
        "type": "info",
        "category": "message",
        "priority": "medium",
        "title": "New Message",
        "message": "{actor_name} sent you a message.",
    },
    "NEW_GROUP_MESSAGE": {
        "type": "info",
        "category": "message",
        "priority": "medium",
        "title": "New Group Message",
        "message": "{actor_name} sent a message in {group_name}.",
    },
    "MENTION_IN_CHAT": {
        "type": "info",
        "category": "message",
        "priority": "high",
        "title": "Mentioned in Chat",
        "message": "{actor_name} mentioned you in {chat_name}.",
    },
    "MESSAGE_REQUEST": {
        "type": "info",
        "category": "message",
        "priority": "medium",
        "title": "Message Request",
        "message": "{actor_name} wants to send you a message.",
    },
    "MESSAGE_REACTION": {
        "type": "info",
        "category": "message",
        "priority": "low",
        "title": "Message Reaction",
        "message": "{actor_name} reacted to your message.",
    },
    "VOICE_MESSAGE_RECEIVED": {
        "type": "info",
        "category": "message",
        "priority": "medium",
        "title": "Voice Message",
        "message": "{actor_name} sent you a voice message.",
    },

    # ============================================
    # 7. FILE & RESOURCE NOTIFICATIONS
    # ============================================
    "FILE_UPLOADED": {
        "type": "info",
        "category": "file",
        "priority": "low",
        "title": "File Uploaded",
        "message": "{actor_name} uploaded '{filename}' to {location}.",
    },
    "FILE_UPDATED": {
        "type": "info",
        "category": "file",
        "priority": "low",
        "title": "File Updated",
        "message": "{actor_name} updated '{filename}'.",
    },
    "FILE_DELETED": {
        "type": "warning",
        "category": "file",
        "priority": "medium",
        "title": "File Deleted",
        "message": "{actor_name} deleted '{filename}'.",
    },
    "FILE_ACCESS_GRANTED": {
        "type": "success",
        "category": "file",
        "priority": "medium",
        "title": "Access Granted",
        "message": "You've been granted access to '{filename}'.",
    },
    "FILE_ACCESS_REVOKED": {
        "type": "warning",
        "category": "file",
        "priority": "medium",
        "title": "Access Revoked",
        "message": "Your access to '{filename}' has been revoked.",
    },
    "FILE_COMMENT_ADDED": {
        "type": "info",
        "category": "file",
        "priority": "low",
        "title": "Comment on File",
        "message": "{actor_name} commented on '{filename}'.",
    },
    "FILE_NEW_VERSION": {
        "type": "info",
        "category": "file",
        "priority": "medium",
        "title": "New File Version",
        "message": "A new version of '{filename}' is available.",
    },

    # ============================================
    # 8. REWARDS, POINTS & ECONOMY
    # ============================================
    "POINTS_EARNED": {
        "type": "success",
        "category": "reward",
        "priority": "medium",
        "title": "Points Earned! 🎯",
        "message": "You earned {points} points for {reason}.",
    },
    "POINTS_DEDUCTED": {
        "type": "warning",
        "category": "reward",
        "priority": "medium",
        "title": "Points Deducted",
        "message": "{points} points were deducted. Reason: {reason}",
    },
    "REWARD_CLAIMED": {
        "type": "success",
        "category": "reward",
        "priority": "medium",
        "title": "Reward Claimed!",
        "message": "You claimed the '{reward_name}' reward!",
    },
    "PAYMENT_SENT": {
        "type": "info",
        "category": "payment",
        "priority": "high",
        "title": "Payment Sent",
        "message": "Payment of {amount} sent to {recipient}.",
    },
    "PAYMENT_RECEIVED": {
        "type": "success",
        "category": "payment",
        "priority": "high",
        "title": "Payment Received",
        "message": "You received {amount} from {sender}.",
    },
    "BOUNTY_POSTED": {
        "type": "info",
        "category": "reward",
        "priority": "medium",
        "title": "New Bounty Posted",
        "message": "New bounty available: '{title}' - {amount}",
    },
    "BOUNTY_COMPLETED": {
        "type": "success",
        "category": "reward",
        "priority": "high",
        "title": "Bounty Completed!",
        "message": "You completed bounty '{title}' and earned {amount}!",
    },
    "REVENUE_SHARE_UPDATE": {
        "type": "info",
        "category": "payment",
        "priority": "medium",
        "title": "Revenue Share Update",
        "message": "Your revenue share for {period}: {amount}",
    },
    "CONTRIBUTION_VERIFIED": {
        "type": "success",
        "category": "reward",
        "priority": "medium",
        "title": "Contribution Verified",
        "message": "Your contribution to '{project}' has been verified!",
    },
    "LEVEL_UP": {
        "type": "success",
        "category": "reward",
        "priority": "high",
        "title": "Level Up! 🎉",
        "message": "Congratulations! You reached level {level}!",
    },
    "RANK_UPGRADED": {
        "type": "success",
        "category": "reward",
        "priority": "high",
        "title": "Rank Upgraded! ⭐",
        "message": "Your rank has been upgraded to {rank}!",
    },

    # ============================================
    # 9. GOVERNANCE, MODERATION & TRUST
    # ============================================
    "CONTENT_REPORTED": {
        "type": "warning",
        "category": "moderation",
        "priority": "high",
        "title": "Content Reported",
        "message": "Your content has been reported for {reason}.",
    },
    "REPORT_RESOLVED": {
        "type": "info",
        "category": "moderation",
        "priority": "medium",
        "title": "Report Resolved",
        "message": "Your report about {content_type} has been resolved.",
    },
    "WARNING_ISSUED": {
        "type": "warning",
        "category": "moderation",
        "priority": "critical",
        "title": "Warning Issued",
        "message": "You've received a warning for {reason}.",
    },
    "MODERATION_ACTION_TAKEN": {
        "type": "warning",
        "category": "moderation",
        "priority": "critical",
        "title": "Moderation Action",
        "message": "Action taken on your content: {action}. Reason: {reason}",
    },
    "APPEAL_STATUS_UPDATE": {
        "type": "info",
        "category": "moderation",
        "priority": "high",
        "title": "Appeal Status Update",
        "message": "Your appeal status: {status}",
    },
    "VOTE_STARTED": {
        "type": "info",
        "category": "governance",
        "priority": "high",
        "title": "New Vote",
        "message": "Voting started: '{title}'. Cast your vote!",
    },
    "VOTE_RESULT_ANNOUNCED": {
        "type": "info",
        "category": "governance",
        "priority": "medium",
        "title": "Vote Results",
        "message": "Results for '{title}': {result}",
    },
    "PROPOSAL_ACCEPTED": {
        "type": "success",
        "category": "governance",
        "priority": "high",
        "title": "Proposal Accepted",
        "message": "Your proposal '{title}' has been accepted!",
    },
    "PROPOSAL_REJECTED": {
        "type": "warning",
        "category": "governance",
        "priority": "medium",
        "title": "Proposal Rejected",
        "message": "Your proposal '{title}' was not accepted.",
    },

    # ============================================
    # 10. INVESTOR & FUNDING NOTIFICATIONS
    # ============================================
    "INVESTOR_INTEREST": {
        "type": "success",
        "category": "funding",
        "priority": "high",
        "title": "Investor Interest! 💰",
        "message": "{investor_name} expressed interest in your startup!",
    },
    "PITCH_DECK_VIEWED": {
        "type": "info",
        "category": "funding",
        "priority": "medium",
        "title": "Pitch Deck Viewed",
        "message": "{viewer_name} viewed your pitch deck.",
    },
    "FUNDING_ROUND_OPENED": {
        "type": "info",
        "category": "funding",
        "priority": "high",
        "title": "Funding Round Opened",
        "message": "Funding round opened for '{startup_name}'.",
    },
    "FUNDING_MILESTONE_REACHED": {
        "type": "success",
        "category": "funding",
        "priority": "high",
        "title": "Funding Milestone! 🎯",
        "message": "'{startup_name}' reached {percentage}% of funding goal!",
    },
    "INVESTMENT_RECEIVED": {
        "type": "success",
        "category": "funding",
        "priority": "critical",
        "title": "Investment Received! 💰",
        "message": "Investment of {amount} received from {investor}!",
    },
    "DUE_DILIGENCE_REQUEST": {
        "type": "info",
        "category": "funding",
        "priority": "high",
        "title": "Due Diligence Request",
        "message": "{investor_name} requested due diligence materials.",
    },
    "CAMPAIGN_UPDATE_POSTED": {
        "type": "info",
        "category": "funding",
        "priority": "medium",
        "title": "Campaign Update",
        "message": "New update posted for '{campaign_name}'.",
    },

    # ============================================
    # 11. AI & AUTOMATION NOTIFICATIONS
    # ============================================
    "AI_SUGGESTION_AVAILABLE": {
        "type": "info",
        "category": "ai",
        "priority": "low",
        "title": "AI Suggestion",
        "message": "AI has a suggestion for {context}.",
    },
    "AI_REPORT_READY": {
        "type": "success",
        "category": "ai",
        "priority": "medium",
        "title": "Report Ready",
        "message": "Your AI-generated report for '{title}' is ready.",
    },
    "AUTOMATION_COMPLETED": {
        "type": "success",
        "category": "automation",
        "priority": "low",
        "title": "Automation Completed",
        "message": "Automation '{name}' completed successfully.",
    },
    "AUTOMATION_FAILED": {
        "type": "error",
        "category": "automation",
        "priority": "high",
        "title": "Automation Failed",
        "message": "Automation '{name}' failed. Error: {error}",
    },
    "AI_RECOMMENDATION": {
        "type": "info",
        "category": "ai",
        "priority": "low",
        "title": "AI Recommendation",
        "message": "Based on your activity, we recommend: {recommendation}",
    },
    "SMART_REMINDER": {
        "type": "info",
        "category": "automation",
        "priority": "medium",
        "title": "Reminder",
        "message": "You have inactive {entity_type}: '{title}'",
    },

    # ============================================
    # 12. EVENT & TIME-BASED NOTIFICATIONS
    # ============================================
    "EVENT_CREATED": {
        "type": "info",
        "category": "event",
        "priority": "medium",
        "title": "Event Created",
        "message": "Event '{title}' has been created for {date}.",
    },
    "EVENT_REMINDER": {
        "type": "info",
        "category": "event",
        "priority": "high",
        "title": "Event Reminder",
        "message": "Reminder: '{title}' starts {time_until}.",
    },
    "EVENT_STARTING_SOON": {
        "type": "warning",
        "category": "event",
        "priority": "high",
        "title": "Event Starting Soon!",
        "message": "'{title}' starts in {minutes} minutes!",
    },
    "EVENT_CANCELED": {
        "type": "warning",
        "category": "event",
        "priority": "high",
        "title": "Event Canceled",
        "message": "Event '{title}' scheduled for {date} has been canceled.",
    },
    "DEADLINE_REMINDER": {
        "type": "warning",
        "category": "event",
        "priority": "high",
        "title": "Deadline Reminder",
        "message": "Deadline for '{title}': {time_until}",
    },
    "DAILY_SUMMARY": {
        "type": "info",
        "category": "digest",
        "priority": "low",
        "title": "Daily Summary",
        "message": "Your daily summary for {date} is ready.",
    },
    "WEEKLY_SUMMARY": {
        "type": "info",
        "category": "digest",
        "priority": "low",
        "title": "Weekly Summary",
        "message": "Your weekly summary is ready.",
    },

    # ============================================
    # 13. FRIEND & CONNECTION NOTIFICATIONS
    # ============================================
    "FRIEND_REQUEST_RECEIVED": {
        "type": "info",
        "category": "social",
        "priority": "medium",
        "title": "Friend Request",
        "message": "{actor_name} sent you a friend request.",
    },
    "FRIEND_REQUEST_ACCEPTED": {
        "type": "success",
        "category": "social",
        "priority": "medium",
        "title": "Friend Request Accepted",
        "message": "{actor_name} accepted your friend request.",
    },
    "CONNECTION_REQUEST": {
        "type": "info",
        "category": "social",
        "priority": "medium",
        "title": "Connection Request",
        "message": "{actor_name} wants to connect with you.",
    },

    # ============================================
    # 14. APPLICATION & ACCESS NOTIFICATIONS
    # ============================================
    "APPLICATION_SUBMITTED": {
        "type": "success",
        "category": "application",
        "priority": "medium",
        "title": "Application Submitted",
        "message": "Your application for '{position}' has been submitted.",
    },
    "APPLICATION_APPROVED": {
        "type": "success",
        "category": "application",
        "priority": "high",
        "title": "Application Approved! 🎉",
        "message": "Your application for '{position}' has been approved!",
    },
    "APPLICATION_REJECTED": {
        "type": "warning",
        "category": "application",
        "priority": "medium",
        "title": "Application Status",
        "message": "Your application for '{position}' was not approved.",
    },
    "ACCESS_REQUEST_PENDING": {
        "type": "info",
        "category": "access",
        "priority": "medium",
        "title": "Access Request Pending",
        "message": "Your access request for '{resource}' is pending approval.",
    },
    "ACCESS_GRANTED": {
        "type": "success",
        "category": "access",
        "priority": "high",
        "title": "Access Granted",
        "message": "You've been granted access to '{resource}'.",
    },

    # ============================================
    # 15. MENTORSHIP NOTIFICATIONS
    # ============================================
    "MENTORSHIP_REQUEST_RECEIVED": {
        "type": "info",
        "category": "mentorship",
        "priority": "high",
        "title": "New Mentorship Request",
        "message": "{actor_name} requested mentorship for their project '{project_title}'.",
    },
    "MENTORSHIP_REQUEST_ACCEPTED": {
        "type": "success",
        "category": "mentorship",
        "priority": "high",
        "title": "Mentorship Request Accepted! 🎉",
        "message": "{mentor_name} accepted your mentorship request for '{project_title}'.",
    },
    "MENTORSHIP_REQUEST_DECLINED": {
        "type": "warning",
        "category": "mentorship",
        "priority": "medium",
        "title": "Mentorship Request Declined",
        "message": "{mentor_name} declined your mentorship request. Reason: {reason}",
    },
    "MENTORSHIP_REQUEST_CANCELLED": {
        "type": "info",
        "category": "mentorship",
        "priority": "low",
        "title": "Mentorship Request Cancelled",
        "message": "{actor_name} cancelled their mentorship request.",
    },
    "MENTORSHIP_SESSION_COMPLETED": {
        "type": "success",
        "category": "mentorship",
        "priority": "high",
        "title": "Mentorship Session Completed",
        "message": "Your session with {mentor_name} is complete. Please rate your experience.",
    },
    "MENTORSHIP_SESSION_SUMMARY": {
        "type": "info",
        "category": "mentorship",
        "priority": "medium",
        "title": "Session Summary Available",
        "message": "{mentor_name} added a session summary and action items for you.",
    },
    "MENTORSHIP_RATED": {
        "type": "info",
        "category": "mentorship",
        "priority": "low",
        "title": "Session Rated",
        "message": "{founder_name} rated your mentorship session {rating}/5.",
    },
    "MENTOR_PAYOUT_PROCESSED": {
        "type": "success",
        "category": "mentorship",
        "priority": "high",
        "title": "Mentor Payout Processed 💰",
        "message": "${amount} has been added to your Balance wallet.",
    },
    "VISION_READINESS_IMPROVED": {
        "type": "success",
        "category": "mentorship",
        "priority": "medium",
        "title": "Vision Readiness Improved! 📈",
        "message": "Your vision readiness score improved by {points} points after mentor review.",
    },

    # ============================================
    # 16. MARKETPLACE NOTIFICATIONS
    # ============================================
    "MARKETPLACE_NEW_PURCHASE": {
        "type": "success",
        "category": "marketplace",
        "priority": "high",
        "title": "New Sale! 🎉",
        "message": "{buyer_name} purchased your listing '{listing_title}' for ${amount}.",
    },
    "MARKETPLACE_PURCHASE_CONFIRMED": {
        "type": "success",
        "category": "marketplace",
        "priority": "high",
        "title": "Purchase Successful",
        "message": "You successfully purchased '{listing_title}'. Download is now available.",
    },
    "MARKETPLACE_LISTING_RATED": {
        "type": "info",
        "category": "marketplace",
        "priority": "low",
        "title": "New Rating on Your Listing",
        "message": "{buyer_name} rated '{listing_title}' {rating}/5 stars.",
    },
    "MARKETPLACE_LISTING_REJECTED": {
        "type": "warning",
        "category": "marketplace",
        "priority": "high",
        "title": "Listing Rejected",
        "message": "Your listing '{listing_title}' was rejected. Reason: {reason}",
    },
    "MARKETPLACE_LISTING_PUBLISHED": {
        "type": "success",
        "category": "marketplace",
        "priority": "medium",
        "title": "Listing Published",
        "message": "Your listing '{listing_title}' is now live on the marketplace.",
    },
    "MARKETPLACE_PAYOUT_PROCESSED": {
        "type": "success",
        "category": "marketplace",
        "priority": "high",
        "title": "Marketplace Payout 💰",
        "message": "${amount} from marketplace sales has been added to your Balance wallet.",
    },
    "MARKETPLACE_LISTING_BOOSTED": {
        "type": "info",
        "category": "marketplace",
        "priority": "low",
        "title": "Listing Boost Active",
        "message": "Your listing '{listing_title}' is now boosted for {hours} hours.",
    },

    # ============================================
    # GENERIC/FALLBACK
    # ============================================
    "GENERIC_SUCCESS": {
        "type": "success",
        "category": "system",
        "priority": "low",
        "title": "Success",
        "message": "{message}",
    },
    "GENERIC_INFO": {
        "type": "info",
        "category": "system",
        "priority": "low",
        "title": "Information",
        "message": "{message}",
    },
    "GENERIC_WARNING": {
        "type": "warning",
        "category": "system",
        "priority": "medium",
        "title": "Warning",
        "message": "{message}",
    },
    "GENERIC_ERROR": {
        "type": "error",
        "category": "system",
        "priority": "high",
        "title": "Error",
        "message": "{message}",
    },
}


# Priority levels (from documentation)
PRIORITY_LEVELS = {
    "critical": 4,  # Security, payments, account access
    "high": 3,      # Tasks, deadlines, direct mentions
    "medium": 2,    # Collaboration updates
    "low": 1,       # Likes, follows, general activity
}

# Notification categories
NOTIFICATION_CATEGORIES = [
    "account",
    "system",
    "social",
    "idea",
    "startup",
    "project",
    "task",
    "message",
    "file",
    "reward",
    "payment",
    "moderation",
    "governance",
    "funding",
    "ai",
    "automation",
    "event",
    "digest",
    "application",
    "access",
    "mentorship",
    "marketplace",
]

# Notification types
NOTIFICATION_TYPES = [
    "success",
    "info",
    "warning",
    "error",
]