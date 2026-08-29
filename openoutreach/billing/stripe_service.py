"""
Stripe API integration service.
Handles product/price sync, customer creation, checkout sessions, and portal sessions.
"""
import json
import logging
from typing import Any, Literal, Optional

import stripe

from openoutreach.config import settings
from openoutreach.billing.plans import PLANS
from openoutreach.billing.models import StripePlan

logger = logging.getLogger(__name__)


_stripe_initialized = False


def init_stripe() -> None:
    """Initialize Stripe with API key."""
    global _stripe_initialized
    if _stripe_initialized:
        return
    if not settings.STRIPE_SECRET_KEY:
        logger.warning("STRIPE_SECRET_KEY not set, Stripe operations will fail")
        return
    stripe.api_key = settings.STRIPE_SECRET_KEY
    _stripe_initialized = True


def sync_stripe_products() -> dict[str, StripePlan]:
    """
    Sync all plans to Stripe, creating/updating products and prices.
    Returns mapping of plan_name → StripePlan with Stripe IDs.
    Idempotent: matches by plan_name metadata.
    """
    init_stripe()

    results: dict[str, StripePlan] = {}

    for plan_def in PLANS:
        plan_name = plan_def["name"]
        logger.info(f"Syncing plan: {plan_name}")

        product = _get_or_create_product(plan_name, plan_def["display_name"])
        if not product:
            logger.error(f"Failed to create product for {plan_name}")
            continue

        stripe_plan = StripePlan(
            plan_name=plan_name,
            stripe_product_id=product.id,
        )

        if plan_name == "cloud_addon":
            price = _create_or_update_price(
                product.id,
                plan_name,
                plan_def["monthly_price"],
                "month",
                False,
            )
            if price:
                stripe_plan.monthly_price_id = price.id
        elif plan_name == "lifetime":
            price = _create_or_update_price(
                product.id,
                plan_name,
                plan_def["annual_price"],
                "one_time",
                False,
            )
            if price:
                stripe_plan.annual_price_id = price.id
        else:
            monthly_price = _create_or_update_price(
                product.id,
                f"{plan_name}_monthly",
                plan_def["monthly_price"],
                "month",
                False,
            )
            if monthly_price:
                stripe_plan.monthly_price_id = monthly_price.id

            annual_price = _create_or_update_price(
                product.id,
                f"{plan_name}_annual",
                plan_def["annual_price"],
                "year",
                False,
            )
            if annual_price:
                stripe_plan.annual_price_id = annual_price.id

        stripe_plan.save()
        results[plan_name] = stripe_plan
        logger.info(f"Synced {plan_name}: product={product.id}")

    return results


def _get_or_create_product(
    plan_name: str,
    display_name: str,
) -> Optional[stripe.Product]:
    """Get or create Stripe product, matching by plan_name metadata."""
    try:
        existing = stripe.Product.search(
            query=f'metadata["plan_name"]:"{plan_name}"',
        )
        if existing.data:
            logger.info(f"Found existing product for {plan_name}")
            return existing.data[0]

        logger.info(f"Creating new product for {plan_name}")
        product = stripe.Product.create(
            name=display_name,
            metadata={"plan_name": plan_name},
        )
        return product
    except stripe.StripeError as e:
        logger.error("Failed to get/create product; plan=%s exception_type=%s", plan_name, type(e).__name__)
        return None


def _create_or_update_price(
    product_id: str,
    price_key: str,
    amount_cents: int,
    interval: Literal["day", "month", "week", "year", "one_time"],
    metered: bool = False,
) -> Optional[stripe.Price]:
    """Create or find Stripe price, matching by product + metadata."""
    if amount_cents == 0 and interval != "one_time":
        logger.info(f"Skipping zero-price for {price_key}")
        return None

    try:
        existing = stripe.Price.search(
            query=f'product:"{product_id}" metadata["price_key"]:"{price_key}"',
        )
        if existing.data:
            for price in existing.data:
                if price.active:
                    logger.info(f"Found existing price for {price_key}")
                    return price

        logger.info(f"Creating new price for {price_key}")

        if interval == "one_time":
            price = stripe.Price.create(
                product=product_id,
                unit_amount=amount_cents,
                currency="usd",
                metadata={"price_key": price_key},
            )
        elif metered:
            price = stripe.Price.create(
                product=product_id,
                recurring={
                    "interval": interval,
                    "usage_type": "metered",
                },
                currency="usd",
                metadata={"price_key": price_key},
            )
        else:
            price = stripe.Price.create(
                product=product_id,
                unit_amount=amount_cents,
                currency="usd",
                recurring={"interval": interval},
                metadata={"price_key": price_key},
            )
        return price
    except stripe.StripeError as e:
        logger.error("Failed to create price; price_key=%s exception_type=%s", price_key, type(e).__name__)
        return None


def create_or_get_customer(
    email: str,
    full_name: str = "",
    metadata: Optional[dict[str, str]] = None,
) -> Optional[stripe.Customer]:
    """Create or get Stripe customer by email."""
    init_stripe()
    try:
        existing = stripe.Customer.search(query=f'email:"{email}"')
        if existing.data:
            logger.info("Found existing customer")
            return existing.data[0]

        logger.info("Creating new customer")
        customer = stripe.Customer.create(
            email=email,
            name=full_name or "",
            metadata=metadata or {},
        )
        return customer
    except stripe.StripeError as e:
        logger.error("Failed to get/create customer; exception_type=%s", type(e).__name__)
        return None


def create_checkout_session(
    customer_id: str,
    price_id: str,
    trial_period_days: Optional[int] = None,
    success_url: str = "",
    cancel_url: str = "",
    coupon_id: Optional[str] = None,
    coupon_code: Optional[str] = None,
) -> Optional[str]:
    """Create Stripe Checkout session, returns session URL."""
    init_stripe()
    try:
        params: dict[str, Any] = {
            "customer": customer_id,
            "mode": "subscription",
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }

        if trial_period_days and trial_period_days > 0:
            params["subscription_data"] = {
                "trial_period_days": trial_period_days,
            }

        if coupon_id:
            params["discounts"] = [{"coupon": coupon_id}]

        # Store coupon code in metadata for webhook tracking
        if coupon_code:
            params["metadata"] = {"coupon_code": coupon_code}

        session = stripe.checkout.Session.create(**params)
        logger.info(f"Created checkout session: {session.id}")
        return session.url
    except stripe.StripeError as e:
        logger.error("Failed to create checkout session; exception_type=%s", type(e).__name__)
        return None


def create_portal_session(customer_id: str, return_url: str = "") -> Optional[str]:
    """Create Stripe Customer Portal session URL."""
    init_stripe()
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url or "https://outreach.lengrowth.com/settings/billing",
        )
        logger.info(f"Created portal session for {customer_id}")
        return session.url
    except stripe.StripeError as e:
        logger.error("Failed to create portal session; exception_type=%s", type(e).__name__)
        return None


def get_subscription(subscription_id: str) -> Optional[stripe.Subscription]:
    """Get Stripe subscription by ID."""
    try:
        return stripe.Subscription.retrieve(subscription_id)
    except stripe.StripeError as e:
        logger.error("Failed to get subscription; exception_type=%s", type(e).__name__)
        return None


def get_customer(customer_id: str) -> Optional[stripe.Customer]:
    """Get Stripe customer by ID."""
    try:
        return stripe.Customer.retrieve(customer_id)
    except stripe.StripeError as e:
        logger.error("Failed to get customer; exception_type=%s", type(e).__name__)
        return None


def construct_webhook_event(body: str, signature: str) -> Optional[dict[str, Any]]:
    """Verify and construct webhook event from Stripe.

    Returns a plain dict (not a StripeObject) so downstream handlers can use
    standard dict operations (.get(), [] access, etc.).
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return None

    try:
        stripe.Webhook.construct_event(
            body,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
        return json.loads(body)
    except (ValueError, stripe.SignatureVerificationError) as e:
        logger.error("Webhook signature verification failed; exception_type=%s", type(e).__name__)
        return None


def update_subscription_price(
    subscription_id: str,
    new_price_id: str,
    proration_behavior: Literal["always_invoice", "create_prorations", "none"] = "create_prorations",
) -> Optional[stripe.Subscription]:
    """
    Update subscription to a new price ID.
    proration_behavior: 'create_prorations' (upgrade), 'none' (downgrade at period end), 'always_invoice'
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        if not subscription or not subscription.items.data:
            logger.error(f"Subscription {subscription_id} not found or has no items")
            return None

        item_id = subscription.items.data[0].id
        updated_sub = stripe.Subscription.modify(
            subscription_id,
            items=[
                {
                    "id": item_id,
                    "price": new_price_id,
                }
            ],
            proration_behavior=proration_behavior,
        )
        logger.info(f"Updated subscription {subscription_id} with new price")
        return updated_sub
    except stripe.StripeError as e:
        logger.error("Failed to update subscription; exception_type=%s", type(e).__name__)
        return None


def cancel_subscription(subscription_id: str, immediate: bool = False) -> Optional[stripe.Subscription]:
    """Cancel a subscription."""
    try:
        if immediate:
            canceled_sub = stripe.Subscription.delete(subscription_id)  # type: ignore
        else:
            canceled_sub = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
        logger.info(f"Canceled subscription {subscription_id}")
        return canceled_sub
    except stripe.StripeError as e:
        logger.error("Failed to cancel subscription; exception_type=%s", type(e).__name__)
        return None


def reactivate_subscription(subscription_id: str) -> Optional[stripe.Subscription]:
    """Reactivate a subscription that was set to cancel at period end."""
    try:
        reactivated_sub = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False,
        )
        logger.info(f"Reactivated subscription {subscription_id}")
        return reactivated_sub
    except stripe.StripeError as e:
        logger.error("Failed to reactivate subscription; exception_type=%s", type(e).__name__)
        return None


def list_invoices(customer_id: str, limit: int = 10) -> list[stripe.Invoice]:
    """Get recent invoices for a customer."""
    try:
        invoices = stripe.Invoice.list(customer=customer_id, limit=limit)
        return invoices.data if invoices else []
    except stripe.StripeError as e:
        logger.error("Failed to list invoices; exception_type=%s", type(e).__name__)
        return []


def create_lifetime_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str = "",
    cancel_url: str = "",
) -> Optional[str]:
    """Create one-time checkout session for lifetime deal."""
    init_stripe()
    try:
        params: dict[str, Any] = {
            "customer": customer_id,
            "mode": "payment",
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }

        session = stripe.checkout.Session.create(**params)
        logger.info(f"Created lifetime deal checkout session: {session.id}")
        return session.url
    except stripe.StripeError as e:
        logger.error("Failed to create lifetime checkout session; exception_type=%s", type(e).__name__)
        return None
