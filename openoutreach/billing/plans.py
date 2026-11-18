"""
Billing plans as the single source of truth.
All plan definitions centralized here, synced to Stripe dynamically.
"""
import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class PlanDefinition(TypedDict):
    """Type for plan definitions."""
    name: str
    display_name: str
    monthly_price: int
    annual_price: int
    max_linkedin_accounts: int
    max_whatsapp_accounts: int
    max_campaigns: int | None
    features: list[str]


PLANS: list[PlanDefinition] = [
    {
        "name": "starter",
        "display_name": "Starter",
        "monthly_price": 1900,
        "annual_price": 19200,
        "max_linkedin_accounts": 1,
        "max_whatsapp_accounts": 1,
        "max_campaigns": 3,
        "features": [
            "ai_messages",
            "1 LinkedIn account",
            "3 active campaigns",
            "AI-written messages",
            "AI follow-up sequences",
            "Unified inbox",
            "Analytics dashboard",
        ],
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "monthly_price": 4900,
        "annual_price": 49200,
        "max_linkedin_accounts": 1,
        "max_whatsapp_accounts": 1,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "api_access",
            "Everything in Starter",
            "Unlimited campaigns",
        ],
    },
    {
        "name": "business",
        "display_name": "Business",
        "monthly_price": 9900,
        "annual_price": 99600,
        "max_linkedin_accounts": 3,
        "max_whatsapp_accounts": 3,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "api_access",
            "team_members",
            "Everything in Pro",
            "3 LinkedIn accounts",
            "Priority support",
        ],
    },
    {
        "name": "agency",
        "display_name": "Agency",
        "monthly_price": 24900,
        "annual_price": 249600,
        "max_linkedin_accounts": 10,
        "max_whatsapp_accounts": 10,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "api_access",
            "team_members",
            "white_label",
            "Everything in Business",
            "10 LinkedIn accounts",
            "Priority support",
        ],
    },
    {
        "name": "cloud",
        "display_name": "Cloud",
        "monthly_price": 29900,
        "annual_price": 0,
        "max_linkedin_accounts": 1,
        "max_whatsapp_accounts": 1,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "api_access",
            "Fully managed execution",
            "1 LinkedIn account + managed proxy included",
            "AI included (no API key needed)",
            "No desktop app needed",
            "All Pro plan features",
            "Campaign performance reviews & tips",
            "Priority support",
        ],
    },
    {
        "name": "cloud_addon",
        "display_name": "Cloud Add-on",
        "monthly_price": 29900,
        "annual_price": 0,
        "max_linkedin_accounts": 0,
        "max_whatsapp_accounts": 0,
        "max_campaigns": None,
        "features": ["ai_messages", "Managed cloud execution"],
    },
    {
        "name": "lifetime",
        "display_name": "Lifetime Pro",
        "monthly_price": 0,
        "annual_price": 14900,
        "max_linkedin_accounts": 1,
        "max_whatsapp_accounts": 1,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "api_access",
            "Everything in Pro",
            "Lifetime access - pay once",
            "All future updates included",
        ],
    },
]


def get_plan(plan_name: str) -> PlanDefinition | None:
    """Get plan definition by name."""
    for plan in PLANS:
        if plan["name"] == plan_name:
            return plan
    return None


def get_all_plans() -> list[PlanDefinition]:
    """Get all user-facing plans (excludes internal cloud_addon seat product)."""
    return [p for p in PLANS if p["name"] != "cloud_addon"]


def get_upgrade_plans() -> list[PlanDefinition]:
    """Get plans available for new subscriptions (excludes cloud, cloud_addon, lifetime)."""
    return [p for p in PLANS if p["name"] not in ("cloud_addon", "cloud", "lifetime")]


def get_plan_by_display_name(display_name: str) -> PlanDefinition | None:
    """Get plan definition by display name."""
    for plan in PLANS:
        if plan["display_name"] == display_name:
            return plan
    return None


CLOUD_PLAN_NAME = "cloud"
CLOUD_ADDON_PLAN_NAME = "cloud_addon"


def effective_cloud_seat_limit(plan_name: str, cloud_profiles: int) -> int:
    """Return how many browser accounts may run in the cloud.

    The Cloud plan includes one seat; every purchased cloud add-on seat adds
    one more. Cloud seats are a Cloud-plan entitlement; add-on quantities on
    other plans are ignored so a seat always maps to one LinkedIn account.
    """
    if plan_name != CLOUD_PLAN_NAME:
        return 0
    return 1 + max(0, int(cloud_profiles or 0))


def effective_linkedin_account_limit(plan_name: str, cloud_profiles: int, fallback: int) -> int:
    """Return the LinkedIn account limit for a user.

    Cloud plan + extra seats: 1 included account + one per cloud seat.
    Other plans keep their normal plan limit; cloud add-on seats only grant
    cloud execution, not additional LinkedIn accounts.
    """
    if plan_name == CLOUD_PLAN_NAME:
        return 1 + max(0, int(cloud_profiles or 0))
    return int(fallback or 0)


def apply_plan_entitlements(user) -> None:
    """Persist plan-derived limits on a User instance.

    Callers save the user afterwards. Keeping this in one place prevents the
    checkout webhook, plan changes, and admin overrides from drifting apart.
    """
    plan_def = get_plan(user.plan)
    if not plan_def:
        return

    user.linkedin_account_limit = effective_linkedin_account_limit(
        user.plan,
        getattr(user, "cloud_profiles", 0),
        plan_def.get("max_linkedin_accounts", 1),
    )
    user.whatsapp_account_limit = plan_def.get("max_whatsapp_accounts", 1)
    user.campaign_limit = plan_def.get("max_campaigns")
    # Keep the organization mirror in sync with the billing owner. This is
    # additive and best-effort: a mirror failure must never break billing.
    try:
        from openoutreach.organizations.service import sync_org_billing_from_user

        sync_org_billing_from_user(user)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(
            "organization_billing_mirror_skipped user_id=%s exception_type=%s",
            getattr(user, "_id", ""),
            type(exc).__name__,
        )
