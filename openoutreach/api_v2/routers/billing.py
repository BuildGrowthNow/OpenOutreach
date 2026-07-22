"""
Billing API endpoints - checkout, portal, status, and plan information.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel

from openoutreach.api_v2.dependencies import get_current_user
from openoutreach.mongodb.models_user import User
from openoutreach.billing.stripe_service import (
    create_or_get_customer,
    create_checkout_session,
    create_portal_session,
    construct_webhook_event,
    update_subscription_price,
    cancel_subscription,
    reactivate_subscription,
    list_invoices,
    create_lifetime_checkout_session,
)
from openoutreach.billing.models import StripePlan
from openoutreach.billing.plans import get_plan, get_all_plans
from openoutreach.billing.config import get_site_config, is_lifetime_deal_active
from openoutreach.billing.webhooks import process_webhook_event
from openoutreach.billing.enforcement import PlanEnforcer
from openoutreach.billing.downgrade_handler import handle_plan_downgrade
from openoutreach.billing.referrals import (
    apply_referral_code,
    get_referral_dashboard,
)
from openoutreach.billing.coupons import (
    Coupon,
    validate_coupon_for_checkout,
)
from openoutreach.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

PLAN_HIERARCHY = ["starter", "lifetime", "pro", "business", "agency", "cloud"]


def _is_plan_upgrade(current_plan: str, new_plan: str) -> bool:
    """Check if plan change is an upgrade."""
    try:
        current_idx = PLAN_HIERARCHY.index(current_plan)
        new_idx = PLAN_HIERARCHY.index(new_plan)
        return new_idx > current_idx
    except ValueError:
        return False


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
    user_status: str


class CheckoutSessionRequest(BaseModel):
    """Request to create checkout session."""
    plan_name: str
    billing_period: str  # 'monthly' or 'annual'
    success_url: str = ""
    cancel_url: str = ""
    coupon_code: Optional[str] = None


class CheckoutSessionResponse(BaseModel):
    """Response with checkout URL."""
    url: str


class PlanChangeRequest(BaseModel):
    """Request to change plan."""
    plan_name: str
    billing_period: str  # 'monthly' or 'annual'


class CloudAddonRequest(BaseModel):
    """Request to add/remove cloud profile seats."""
    quantity: int


class ReferralDashboardResponse(BaseModel):
    """Response for referral dashboard."""
    referral_code: str
    referral_link: str
    referrals_count: int
    credits_earned: str
    credits_earned_cents: int


class CouponValidationRequest(BaseModel):
    """Request to validate a coupon code."""
    coupon_code: str


class CouponValidationResponse(BaseModel):
    """Response for coupon validation."""
    valid: bool
    code: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[int] = None
    message: Optional[str] = None


class ApplyReferralRequest(BaseModel):
    """Request to apply a referral code at signup."""
    referral_code: str


class InvoiceResponse(BaseModel):
    """Response for invoice information."""
    id: str
    number: Optional[str]
    status: str
    amount_paid: int
    amount_due: int
    currency: str
    created: int
    period_start: int
    period_end: int
    paid: bool
    pdf_url: Optional[str]


class FeatureGateResponse(BaseModel):
    """Response when a feature is locked behind a plan upgrade."""
    upgrade_required: bool = True
    required_plan: str
    current_plan: str
    message: str


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
        user_status=user.status,
    )


@router.get("/usage")
async def get_current_usage(
    user_id: str = Depends(get_current_user),
) -> dict[str, int | None]:
    """Get current usage stats and limits for the user."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    from openoutreach.mongodb.connection import get_mongodb_collection

    try:
        profiles_coll = get_mongodb_collection("linkedin_profiles")
        campaigns_coll = get_mongodb_collection("campaigns")

        linkedin_accounts_used = 0
        campaigns_used = 0

        if profiles_coll is not None:
            linkedin_accounts_used = profiles_coll.count_documents({
                "user_id": user_id,
                "is_active": True,
            })

        if campaigns_coll is not None:
            # Count active (non-paused) campaigns — must match PlanEnforcer.can_create_campaign
            campaigns_used = campaigns_coll.count_documents({
                "user_id": user_id,
                "is_paused": False,
            })

        return {
            "linkedin_accounts_used": linkedin_accounts_used,
            "linkedin_accounts_limit": user.linkedin_account_limit,
            "campaigns_used": campaigns_used,
            "campaigns_limit": user.campaign_limit,
        }
    except Exception as e:
        logger.error(f"Failed to get usage: {e}")
        return {
            "linkedin_accounts_used": 0,
            "linkedin_accounts_limit": user.linkedin_account_limit,
            "campaigns_used": 0,
            "campaigns_limit": user.campaign_limit,
        }


@router.post("/checkout")
async def create_checkout(
    request: CheckoutSessionRequest,
    user_id: str = Depends(get_current_user),
) -> CheckoutSessionResponse:
    """
    Create Stripe Checkout session.

    For new users (subscription_status=none), this initiates a trial.
    For existing users upgrading, prorations are applied.
    Success redirects to /settings/billing?success=true

    Requires email_verified=True before checkout.
    """
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Enforce email verification before checkout
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required before checkout"
        )

    plan = get_plan(request.plan_name)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan")

    if request.plan_name == "lifetime":
        if request.billing_period != "lifetime":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lifetime deal must use billing_period='lifetime'",
            )
        if not is_lifetime_deal_active():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lifetime deal is no longer active",
            )
    elif request.billing_period not in ("monthly", "annual"):
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
            stripe_plan.annual_price_id
            if request.plan_name == "lifetime"
            else (
                stripe_plan.monthly_price_id
                if request.billing_period == "monthly"
                else stripe_plan.annual_price_id
            )
        )

        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Plan price not available",
            )

        # Use APP_URL from settings for checkout URLs
        app_url = getattr(settings, 'APP_URL', None) or settings.CORS_ALLOWED_ORIGINS.split(',')[0]

        if request.plan_name == "lifetime":
            url = create_lifetime_checkout_session(
                customer_id=customer.id,
                price_id=price_id,
                success_url=request.success_url or f"{app_url}/settings/billing?success=true",
                cancel_url=request.cancel_url or f"{app_url}/settings/billing?canceled=true",
            )
        else:
            config = get_site_config()
            trial_days = None
            if user.subscription_status == "none":
                # Base trial duration
                trial_days = config.trial_duration_days
                # Add referral extension if user was referred
                if user.referrer_id:
                    trial_days += config.referral_trial_extension_days
                    logger.info(f"Applied referral trial extension: {trial_days} days total for {user.email}")

            coupon_id = None
            if request.coupon_code:
                coupon_id = validate_coupon_for_checkout(request.coupon_code)
                if not coupon_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired coupon code",
                    )

            url = create_checkout_session(
                customer_id=customer.id,
                price_id=price_id,
                trial_period_days=trial_days,
                success_url=request.success_url or f"{app_url}/settings/billing?success=true",
                cancel_url=request.cancel_url or f"{app_url}/settings/billing?canceled=true",
                coupon_id=coupon_id,
                coupon_code=request.coupon_code if coupon_id else None,
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
        # Use APP_URL from settings for portal return URL
        app_url = getattr(settings, 'APP_URL', None) or settings.CORS_ALLOWED_ORIGINS.split(',')[0]
        url = create_portal_session(
            customer_id=user.stripe_customer_id,
            return_url=return_url or f"{app_url}/settings/billing",
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




@router.post("/plan-change")
async def change_plan(
    request: PlanChangeRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    """Change user's plan (upgrade or downgrade)."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found",
        )

    plan = get_plan(request.plan_name)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan")

    if request.billing_period not in ("monthly", "annual"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid billing period")

    try:
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

        is_upgrade = _is_plan_upgrade(user.plan, request.plan_name)
        proration_behavior = "create_prorations" if is_upgrade else "none"

        updated_sub = update_subscription_price(
            user.stripe_subscription_id,
            price_id,
            proration_behavior=proration_behavior,
        )

        if not updated_sub:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update subscription",
            )

        old_limit = user.linkedin_account_limit
        user.plan = request.plan_name
        user.billing_period = request.billing_period
        new_limit = plan["max_linkedin_accounts"]
        user.linkedin_account_limit = new_limit
        user.campaign_limit = plan["max_campaigns"]
        user.save()

        if not is_upgrade and new_limit < old_limit:
            handle_plan_downgrade(user, new_limit)

        return {"status": "success", "message": "Plan changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plan change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Plan change failed",
        )


@router.post("/cloud-addon")
async def update_cloud_addon(
    request: CloudAddonRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, int]:
    """Update cloud addon profile count via Stripe subscription."""
    import stripe as _stripe

    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if request.quantity < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity must be >= 0")

    if not user.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription. Subscribe to a plan first.",
        )

    stripe_plan = StripePlan.get_by_plan("cloud_addon")
    if not stripe_plan or not stripe_plan.monthly_price_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cloud addon not configured in Stripe",
        )

    try:
        subscription = _stripe.Subscription.retrieve(user.stripe_subscription_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not retrieve subscription",
            )

        addon_item = None
        for item in subscription.items.data:
            if item.price.id == stripe_plan.monthly_price_id:
                addon_item = item
                break

        if request.quantity == 0 and addon_item:
            _stripe.SubscriptionItem.delete(addon_item.id, proration_behavior="create_prorations")
        elif request.quantity > 0 and addon_item:
            _stripe.SubscriptionItem.modify(
                addon_item.id,
                quantity=request.quantity,
                proration_behavior="create_prorations",
            )
        elif request.quantity > 0:
            _stripe.SubscriptionItem.create(
                subscription=user.stripe_subscription_id,
                price=stripe_plan.monthly_price_id,
                quantity=request.quantity,
                proration_behavior="create_prorations",
            )

        user.cloud_profiles = request.quantity
        user.save()
        return {"cloud_profiles": user.cloud_profiles}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cloud addon error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update cloud addon",
        )


@router.post("/cancel-subscription")
async def cancel_sub(
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    """Cancel user's subscription at end of current billing period."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription to cancel",
        )

    try:
        cancel_subscription(user.stripe_subscription_id, immediate=False)
        return {"status": "scheduled_for_cancellation"}
    except Exception as e:
        logger.error(f"Cancel subscription error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription",
        )


@router.post("/reactivate-subscription")
async def reactivate_sub(
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    """Reactivate a subscription scheduled for cancellation."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No subscription to reactivate",
        )

    try:
        reactivate_subscription(user.stripe_subscription_id)
        return {"status": "reactivated"}
    except Exception as e:
        logger.error(f"Reactivate subscription error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate subscription",
        )


@router.get("/invoices")
async def get_invoices(
    user_id: str = Depends(get_current_user),
) -> list[InvoiceResponse]:
    """Get user's recent invoices."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.stripe_customer_id:
        return []

    try:
        invoices = list_invoices(user.stripe_customer_id, limit=10)
        return [
            InvoiceResponse(
                id=inv.id,
                number=inv.number,
                status=inv.status or "unknown",
                amount_paid=inv.amount_paid,
                amount_due=inv.amount_due,
                currency=inv.currency,
                created=inv.created,
                period_start=inv.period_start,
                period_end=inv.period_end,
                paid=getattr(inv, "paid", inv.status == "paid"),
                pdf_url=inv.invoice_pdf,
            )
            for inv in invoices
        ]
    except Exception as e:
        logger.error(f"Failed to get invoices: {e}")
        return []


@router.get("/feature-check/{feature_name}")
async def check_feature(
    feature_name: str,
    user_id: str = Depends(get_current_user),
) -> dict[str, bool]:
    """Check if user has access to a specific feature."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    has_access = PlanEnforcer.has_feature(user, feature_name)
    return {"has_access": has_access}


@router.get("/referral/dashboard")
async def get_referral_info(
    user_id: str = Depends(get_current_user),
) -> ReferralDashboardResponse:
    """Get user's referral dashboard information."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    dashboard = get_referral_dashboard(user)
    return ReferralDashboardResponse(**dashboard)


@router.post("/coupons/validate")
async def validate_coupon(
    request_body: CouponValidationRequest,
    user_id: str = Depends(get_current_user),
) -> CouponValidationResponse:
    """Validate a coupon code before checkout."""
    coupon_code = request_body.coupon_code.upper()
    coupon = Coupon.get_by_code(coupon_code)

    if not coupon or not coupon.is_valid():
        return CouponValidationResponse(
            valid=False,
            message="Coupon code is invalid or expired"
        )

    return CouponValidationResponse(
        valid=True,
        code=coupon.code,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
    )


@router.post("/referral/apply")
async def apply_referral(
    request_body: ApplyReferralRequest,
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    """Apply a referral code to current user's account."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.referrer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Referral code already applied to this account"
        )

    referrer = apply_referral_code(user, request_body.referral_code)
    if not referrer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid referral code or cannot use your own code"
        )

    user.save()
    return {
        "status": "success",
        "message": "Referral code applied successfully!"
    }


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Handle Stripe webhooks."""
    body = await request.body()
    signature = request.headers.get("stripe-signature", "")

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    event = construct_webhook_event(body.decode("utf-8"), signature)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    if process_webhook_event(event):
        return {"status": "success"}

    return {"status": "unhandled"}
