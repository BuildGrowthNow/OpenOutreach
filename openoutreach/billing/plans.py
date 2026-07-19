"""
Billing plans as the single source of truth.
All plan definitions centralized here, synced to Stripe dynamically.
"""
from typing import TypedDict


class PlanDefinition(TypedDict):
    """Type for plan definitions."""
    name: str
    display_name: str
    monthly_price: int
    annual_price: int
    max_linkedin_accounts: int
    max_campaigns: int | None
    features: list[str]


PLANS: list[PlanDefinition] = [
    {
        "name": "starter",
        "display_name": "Starter",
        "monthly_price": 1900,
        "annual_price": 16000,
        "max_linkedin_accounts": 1,
        "max_campaigns": 3,
        "features": ["ai_messages", "follow_ups", "inbox", "analytics"],
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "monthly_price": 4900,
        "annual_price": 41000,
        "max_linkedin_accounts": 1,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "follow_ups",
            "inbox",
            "analytics",
            "voice_notes",
            "ai_follow_ups",
            "sales_navigator",
            "api_access",
        ],
    },
    {
        "name": "business",
        "display_name": "Business",
        "monthly_price": 9900,
        "annual_price": 82000,
        "max_linkedin_accounts": 3,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "follow_ups",
            "inbox",
            "analytics",
            "voice_notes",
            "ai_follow_ups",
            "sales_navigator",
            "api_access",
            "team_members",
            "workspace_management",
            "priority_support",
        ],
    },
    {
        "name": "agency",
        "display_name": "Agency",
        "monthly_price": 24900,
        "annual_price": 207000,
        "max_linkedin_accounts": 10,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "follow_ups",
            "inbox",
            "analytics",
            "voice_notes",
            "ai_follow_ups",
            "sales_navigator",
            "api_access",
            "team_members",
            "workspace_management",
            "priority_support",
            "white_label",
            "custom_domain",
        ],
    },
    {
        "name": "cloud_addon",
        "display_name": "Cloud Add-on",
        "monthly_price": 3900,
        "annual_price": 0,
        "max_linkedin_accounts": 0,
        "max_campaigns": None,
        "features": ["cloud_execution"],
    },
    {
        "name": "lifetime",
        "display_name": "Lifetime Pro",
        "monthly_price": 0,
        "annual_price": 14900,
        "max_linkedin_accounts": 1,
        "max_campaigns": None,
        "features": [
            "ai_messages",
            "follow_ups",
            "inbox",
            "analytics",
            "voice_notes",
            "ai_follow_ups",
            "sales_navigator",
            "api_access",
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
    """Get all plans (excluding internal ones like cloud_addon)."""
    return [p for p in PLANS if p["name"] not in ("cloud_addon", "lifetime")]


def get_plan_by_display_name(display_name: str) -> PlanDefinition | None:
    """Get plan definition by display name."""
    for plan in PLANS:
        if plan["display_name"] == display_name:
            return plan
    return None
