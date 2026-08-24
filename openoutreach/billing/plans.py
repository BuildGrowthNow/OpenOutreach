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
            "Fully managed execution",
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
        "features": ["Managed cloud execution"],
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
            "Everything in Pro",
            "Lifetime access — pay once",
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
