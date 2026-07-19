"""
Billing API endpoints - checkout, portal, status, and plan information.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from openoutreach.api_v2.dependencies import get_current_user
from openoutreach.mongodb.models_user import User
from openoutreach.billing.stripe_service import (
    create_or_get_customer,
    create_checkout_session,
    create_portal_session,
)
from openoutreach.billing.models import StripePlan
from openoutreach.billing.plans import get_plan, get_all_plans
from openoutreach.billing.config import get_site_config, is_lifetime_deal_active
from openoutreach.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])


class PlanResponse(BaseModel):
    """Response model for plan information."""
    name: str
    display_name: str
    monthly_price: int
    annual_price: int
    max_linkedin_accounts: int
    max_campaigns: Optional[int]
    features: list[str]


class BillingStatusResponse(BaseModel):
    """Response for current billing status."""
    plan: str
    subscription_status: str
    billing_period: Optional[str]
    trial_ends_at: Optional[str]
    current_period_end: Optional[str]
    linkedin_account_limit: int
    campaign_limit: Optional[int]
    cloud_profiles: int


class CheckoutSessionRequest(BaseModel):
    """Request to create checkout session."""
    plan_name: str
    billing_period: str  # 'monthly' or 'annual'
    success_url: str = ""
    cancel_url: str = ""


class CheckoutSessionResponse(BaseModel):
    """Response with checkout URL."""
    url: str


@router.get("/plans")
async def list_plans() -> list[PlanResponse]:
    """Get all available plans."""
    plans = get_all_plans()
    return [
        PlanResponse(
            name=p["name"],
            display_name=p["display_name"],
            monthly_price=p["monthly_price"],
            annual_price=p["annual_price"],
            max_linkedin_accounts=p["max_linkedin_accounts"],
            max_campaigns=p["max_campaigns"],
            features=p["features"],
        )
        for p in plans
    ]


@router.get("/lifetime-deal-active")
async def lifetime_deal_active() -> dict[str, bool]:
    """Check if lifetime deal is still active."""
    return {"active": is_lifetime_deal_active()}


@router.get("/status")
async def billing_status(
    user_id: str = Depends(get_current_user),
) -> BillingStatusResponse:
    """Get current user's billing status."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return BillingStatusResponse(
        plan=user.plan,
        subscription_status=user.subscription_status,
        billing_period=user.billing_period,
        trial_ends_at=user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        current_period_end=user.current_period_end.isoformat() if user.current_period_end else None,
        linkedin_account_limit=user.linkedin_account_limit,
        campaign_limit=user.campaign_limit,
        cloud_profiles=user.cloud_profiles,
    )


@router.post("/checkout")
async def create_checkout(
    request: CheckoutSessionRequest,
    user_id: str = Depends(get_current_user),
) -> CheckoutSessionResponse:
    """Create Stripe Checkout session."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    plan = get_plan(request.plan_name)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan")

    if request.billing_period not in ("monthly", "annual"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid billing period")

    try:
        customer = create_or_get_customer(
            email=user.email,
            full_name=user.full_name,
            metadata={"user_id": user._id},
        )
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create Stripe customer",
            )

        if not user.stripe_customer_id:
            user.stripe_customer_id = customer.id
            user.save()

        stripe_plan = StripePlan.get_by_plan(request.plan_name)
        if not stripe_plan:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Plan not configured in Stripe",
            )

        price_id = (
            stripe_plan.monthly_price_id
            if request.billing_period == "monthly"
            else stripe_plan.annual_price_id
        )

        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Plan price not available",
            )

        config = get_site_config()
        trial_days = (
            config.trial_duration_days
            if user.subscription_status == "none"
            else None
        )

        url = create_checkout_session(
            customer_id=customer.id,
            price_id=price_id,
            trial_period_days=trial_days,
            success_url=request.success_url or f"{settings.CORS_ALLOWED_ORIGINS.split(',')[0]}/settings/billing?success=true",
            cancel_url=request.cancel_url or f"{settings.CORS_ALLOWED_ORIGINS.split(',')[0]}/settings/billing?canceled=true",
        )

        if not url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create checkout session",
            )

        return CheckoutSessionResponse(url=url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Checkout creation failed",
        )


@router.post("/portal")
async def create_portal(
    return_url: str = "",
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    """Create Stripe Customer Portal session."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer found",
        )

    try:
        url = create_portal_session(
            customer_id=user.stripe_customer_id,
            return_url=return_url or f"{settings.CORS_ALLOWED_ORIGINS.split(',')[0]}/settings/billing",
        )

        if not url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create portal session",
            )

        return {"url": url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Portal error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Portal creation failed",
        )


@router.get("/usage")
async def get_usage(
    user_id: str = Depends(get_current_user),
) -> dict:
    """Get user's current usage stats."""
    from openoutreach.mongodb.connection import get_mongodb_collection

    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    profiles_collection = get_mongodb_collection("linkedin_profiles")
    linkedin_accounts_used = 0
    if profiles_collection is not None:
        linkedin_accounts_used = profiles_collection.count_documents({
            "user_id": user_id,
            "is_active": True,
        })

    campaigns_collection = get_mongodb_collection("campaigns")
    campaigns_used = 0
    if campaigns_collection is not None:
        campaigns_used = campaigns_collection.count_documents({
            "user_id": user_id,
            "is_paused": False,
        })

    return {
        "linkedin_accounts_used": linkedin_accounts_used,
        "linkedin_accounts_limit": user.linkedin_account_limit,
        "campaigns_used": campaigns_used,
        "campaigns_limit": user.campaign_limit,
    }
