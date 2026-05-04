from enum import Enum
from app.extensions import db
from app.models.user import User
from sqlalchemy import func
from app.models.startUpMember import StartupMember


class PlanType(Enum):
    FOUNDER_FREE = "founder-free"
    FOUNDER_STARTER = "founder-starter"
    FOUNDER_PRO = "founder-pro"
    FOUNDER_SCALE = "founder-scale"
    FOUNDER_PARTNER = "founder-partner"
    BUILDER_FREE = "builder-free"
    BUILDER_PRO = "builder-pro"
    BUILDER_PLUS = "builder-plus"
    BUILDER_ELITE = "builder-elite"


# Plan configurations based on subscription_plans.py
PLAN_LIMITS = {
    PlanType.FOUNDER_FREE: {
        "max_projects": 1,
        "max_tasks_milestones": 20,
        "max_collaborators": 5,
        "max_file_size_mb": 100,
        "max_total_storage_mb": 1024,
        "ai_credits_monthly": 0,
        "platform_fee_percentage": 0,
        "price": 0,
    },
    PlanType.FOUNDER_STARTER: {
        "max_projects": 3,
        "max_tasks_milestones": 200,
        "max_collaborators": 15,
        "max_file_size_mb": 500,
        "max_total_storage_mb": 20480,
        "ai_credits_monthly": 1000,
        "platform_fee_percentage": 0,
        "price": 4900,
    },
    PlanType.FOUNDER_PRO: {
        "max_projects": 10,
        "max_tasks_milestones": 500,
        "max_collaborators": 40,
        "max_file_size_mb": 1000,
        "max_total_storage_mb": 76800,
        "ai_credits_monthly": 5000,
        "platform_fee_percentage": 0,
        "price": 14900,
    },
    PlanType.FOUNDER_SCALE: {
        "max_projects": float("inf"),
        "max_tasks_milestones": float("inf"),
        "max_collaborators": 100,
        "max_file_size_mb": 2000,
        "max_total_storage_mb": 307200,
        "ai_credits_monthly": 10000,
        "platform_fee_percentage": 0,
        "price": 29900,
    },
    PlanType.FOUNDER_PARTNER: {
        "max_projects": float("inf"),
        "max_tasks_milestones": float("inf"),
        "max_collaborators": 200,
        "max_file_size_mb": float("inf"),
        "max_total_storage_mb": 512000,
        "ai_credits_monthly": 25000,
        "platform_fee_percentage": 0,
        "price": 49900,
    },
    PlanType.BUILDER_FREE: {
        "max_concurrent_projects": 1,
        "max_project_applications": 5,
        "platform_fee_percentage": 20.0,
        "price": 0,
    },
    PlanType.BUILDER_PRO: {
        "max_concurrent_projects": 3,
        "max_project_applications": 15,
        "platform_fee_percentage": 10.0,
        "price": 900,
    },
    PlanType.BUILDER_PLUS: {
        "max_concurrent_projects": float("inf"),
        "max_project_applications": 50,
        "platform_fee_percentage": 5.0,
        "price": 1900,
    },
    PlanType.BUILDER_ELITE: {
        "max_concurrent_projects": float("inf"),
        "max_project_applications": float("inf"),
        "platform_fee_percentage": 2.0,
        "price": 4900,
    },
}


def get_user_plan_type(user: User) -> PlanType:
    """Get the plan type for a user based on plan_id"""
    if not user.founder_plan_id and not user.builder_plan_id:
        return PlanType.FOUNDER_FREE
    print(
        f"User {user.id} - Founder Plan: {user.founder_plan_id}, Builder Plan: {user.builder_plan_id}"
    )
    plan_mapping = {
        # Standard plans
        "founder-free": PlanType.FOUNDER_FREE,
        "founder-starter": PlanType.FOUNDER_STARTER,
        "founder-pro": PlanType.FOUNDER_PRO,
        "founder-scale": PlanType.FOUNDER_SCALE,
        "founder-partner": PlanType.FOUNDER_PARTNER,
        "builder-free": PlanType.BUILDER_FREE,
        "builder-pro": PlanType.BUILDER_PRO,
        "builder-plus": PlanType.BUILDER_PLUS,
        "builder-elite": PlanType.BUILDER_ELITE,
        # Crowdfunding plans map to their standard equivalents
        "crowdfunding-founder-explorer": PlanType.FOUNDER_STARTER,
        "crowdfunding-founder-starter-supporter": PlanType.FOUNDER_STARTER,
        "crowdfunding-founder-pro": PlanType.FOUNDER_PRO,
        "crowdfunding-founder-power": PlanType.FOUNDER_SCALE,
        "crowdfunding-founder-champion": PlanType.FOUNDER_SCALE,
        "crowdfunding-founder-patron": PlanType.FOUNDER_PARTNER,
        "crowdfunding-founding-partner": PlanType.FOUNDER_PARTNER,
        "crowdfunding-strategic-supporter": PlanType.FOUNDER_PARTNER,
        "crowdfunding-builder-supporter": PlanType.BUILDER_PRO,
        "crowdfunding-builder-early": PlanType.BUILDER_PRO,
        "crowdfunding-builder-starter": PlanType.BUILDER_PLUS,
        "crowdfunding-builder-pro-supporter": PlanType.BUILDER_PLUS,
        "crowdfunding-builder-power-supporter": PlanType.BUILDER_ELITE,
        "crowdfunding-builder-champion": PlanType.BUILDER_ELITE,
        "crowdfunding-builder-patron": PlanType.BUILDER_ELITE,
    }
    if user.founder_plan_id:
        plan_id = user.founder_plan_id
    elif user.builder_plan_id:
        plan_id = user.builder_plan_id
    else:
        plan_id = "founder-free"

    return plan_mapping.get(plan_id.lower(), PlanType.FOUNDER_FREE)


def get_plan_limits(user: User) -> dict:
    """Get plan limits for a user"""
    plan_type = get_user_plan_type(user)
    return PLAN_LIMITS[plan_type]


def can_create_project(user: User) -> bool:
    """Check if user can create a new project"""
    plan_limits = get_plan_limits(user)

    current_projects = user.startups.count()
    return current_projects < plan_limits["max_projects"]


def can_add_collaborator(user: User) -> bool:
    plan_limits = get_plan_limits(user)

    current_collaborators = (
        db.session.query(func.count(StartupMember.id))
        .join(StartupMember.member_startup)
        .filter(
            StartupMember.user_id == user.id
            and StartupMember.member_startup.creator_id == user.id
        )
        .scalar()
    )
    return current_collaborators < plan_limits["max_collaborators"]


def can_create_task_or_milestone(user: User) -> bool:
    """Check if user can create tasks or milestones based on plan"""
    plan_limits = get_plan_limits(user)
    # Assuming tasks and milestones share the same limit as projects for simplicity
    current_tasks_milestones = user.created_tasks.count() + user.project_goals.count()
    return current_tasks_milestones < plan_limits["max_tasks_milestones"]


def can_update_file(
    user: User, old_file_size_mb: float, new_file_size_mb: float
) -> bool:
    """Check if user can update a file of given size"""
    plan_limits = get_plan_limits(user)

    if new_file_size_mb > plan_limits["max_file_size_mb"]:
        return False, "File exceeds per-file limit"
    if (
        user.storage_used_mb + (new_file_size_mb - old_file_size_mb)
        > plan_limits["max_total_storage_mb"]
    ):
        return False, "Total storage limit exceeded"
    return True


def can_upload_file(user: User, file_size_mb: float) -> tuple[bool, str | None]:
    """Check if user can upload a file of given size"""
    plan_limits = get_plan_limits(user)

    if file_size_mb > plan_limits["max_file_size_mb"]:
        return False, "File exceeds per-file limit"
    if user.storage_used_mb + file_size_mb > plan_limits["max_total_storage_mb"]:
        return False, "Total storage limit exceeded"
    return True, None


def consume_ai_credits(user: User, amount: int) -> bool:
    """Consume AI credits for a user"""
    if getattr(user, "wallet", None) and (user.wallet.credits or 0) >= amount:
        user.wallet.spend_credits(amount, description="Consumed AI Credits")
        db.session.commit()
        return True
    return False


def get_remaining_ai_credits(user: User) -> int:
    """Get remaining AI credits for user"""
    if getattr(user, "wallet", None):
        return user.wallet.credits or 0
    return 0


def calculate_platform_fee(user: User, amount: float) -> float:
    """Calculate platform fee based on user's plan"""
    plan_limits = get_plan_limits(user)
    fee_percentage = plan_limits["platform_fee_percentage"]
    return amount * (fee_percentage / 100)


def get_net_amount_after_fee(user: User, gross_amount: float) -> float:
    """Calculate net amount after platform fee"""
    fee = calculate_platform_fee(user, gross_amount)
    return gross_amount - fee
