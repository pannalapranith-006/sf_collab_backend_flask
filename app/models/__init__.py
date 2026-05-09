from .user import User
from .userAchievement import UserAchievement
from .startup import Startup, StartupView
from .startUpMember import StartupMember
from .growthMetric import GrowthMetric
from .achievement import Achievement
from .calendarEvent import CalendarEvent
from .chatConversation import ChatConversation
from .chatMessage import ChatMessage
from .goalMilstone import GoalMilestone
from .idea import Idea
from .ideaBookmark import IdeaBookmark
from .ideaComment import IdeaComment
from .joinRequest import JoinRequest
from .projectGoal import ProjectGoal
from .startupBookmark import StartupBookmark
from .task import Task
from .teamPerformance import TeamPerformance
from .knowledge import Knowledge
from .knowledgeBookmark import KnowledgeBookmark
from .knowledgeComment import KnowledgeComment
from .notification import Notification
from .post import Post
from .postLike import PostLike
from .postComment import PostComment
from .postMedia import PostMedia
from .teamMember import TeamMember
from .suggestion import Suggestion
from .storyView import StoryView
from .story import Story
from .ResourceView import ResourceView
from .ResourceLike import ResourceLike
from .ResourceDownload import ResourceDownload
from .refreshToken import RefreshToken
from .waitlist import Waitlist
from .planVersion import PlanVersion
from .businessPlan import BusinessPlan
from .planSection import PlanSection

from .builder import BuilderProfile, BuilderSkill, BuilderPortfolio, BuilderApplication, SavedStartup, ApplicationStatus
from .outreach_email_account import OutreachEmailAccount
from .outreach_campaign import OutreachCampaign
from .outreach_contact import OutreachContact
from .outreach_sendjobs import OutreachSendJob
from .outreach_draft import OutreachDraft
from .pitch_deck import PitchDeck
from .UserWallet import UserWallet
from .WalletTransaction import WalletTransaction
from .virtual_product import VirtualProduct
from .product_purchase import ProductPurchase
from .user_inventory import UserInventory
from .EventTokenBalance import EventTokenBalance
from .aiNews import AINewsArticle
from .vision import Vision
from .collaboration_request import CollaborationRequest
from .ideaCollabRequest import IdeaCollabRequest
from .startup_rating import StartupRating
from .marketplace_category import MarketplaceCategory
from .marketplace_listing import MarketplaceListing
from .marketplace_seller import Seller

# Economy Layer 2
from .Balance import Balance, BalanceTransaction
from .EscrowTransaction import EscrowTransaction

# Economy Layer 3
from .Crystal import CrystalWallet, CrystalTransaction, VisibilityBoost

from .marketplace_purchase import MarketplacePurchase
from .mentor import MentorProfile, MentorSession, MentorshipRequest

# ── SF Drive (old) — tables: sf_folders, sf_files, sf_tags ───────────────────
# FIX: these use DIFFERENT table names from the new drive_* module:
#   sfdrivefolder.Folder  → sf_folders   (NOT drive_folders)
#   sfdrive_file.SFFile   → sf_files     (NOT drive_files)
#   sfdrive_tag.Tag       → sf_tags      (NOT drive_*)
# Safe to import — no table conflict with new Drive module.
from .sfdrivefolder import Folder
from .sfdrive_file import SFFile
from .sfdrive_tag import Tag

# ── SF Drive (new) — tables: drive_folders, drive_files, etc. ────────────────
# FIX: drive_file.DriveFile (table: drive_files) was being registered twice —
# once when a route module imported it directly, and again here. This caused:
#   "Table 'drive_files' is already defined for this MetaData instance"
# Solution: do NOT import drive_file here. The route modules that need DriveFile
# import it directly from app.models.drive_file, which is fine as long as this
# __init__.py does not also import it (Python caches the module but SQLAlchemy
# re-runs table registration on class definition if the class body is executed
# twice — which happens when the same module is imported under two different
# paths, e.g. 'app.models.drive_file' vs '.drive_file').
from .drive_folder import DriveFolder
# from .drive_file import DriveFile, DriveFileVersion  ← DO NOT import here
from .drive_permission import DriveFilePermission
# FIX: DriveFileRelation lives in drive_file_relation.py, not drive_permission.py
from .drive_file_relation import DriveFileRelation
from .drive_audit_log import DriveAuditLog

# ── ERP Module ────────────────────────────────────────────────────────────────
from .attendance import Attendance
from .alert import Alert, AlertType, AlertPriority, WorkspaceAlertConfig
from .erp_support import DailyUpdate, Holiday, UserUpdateStreak

# FIX: AnalyticsSnapshot imported once from its canonical source (erp_activity).
# Removed all duplicate imports from .analytics and redundant erp_activity lines.
from .erp_activity import UserActivity, ActivityMonitorJobHealth, AnalyticsSnapshot