"""
Stripe webhook event handlers for subscription lifecycle management.
"""
import logging
from datetime import datetime, timezone as tz
from typing import Any, Optional

import stripe

from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.connection import get_mongodb_collection
from openoutreach.billing.emails import (
    send_plan_upgraded,
    send_plan_downgraded,
    send_payment_failed,
    send_trial_expiry_warning,
    send_welcome_email,
    send_lifetime_deal_purchase,
)

logger = logging.getLogger(__name__)


def _get_user_by_stripe_customer(customer_id: str) -> Optional[User]:
    """Get user by Stripe customer ID."""
    collection = get_mongodb_collection("users")
    if collection is None:
        return None
    data = collection.find_one({"stripe_customer_id": customer_id})
    return User.from_dict(data) if data else None


def handle_checkout_session_completed(event: dict[str, Any]) -> None:
    """Handle checkout.session.completed event."""
    session = event["data"]["object"]
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    payment_status = session.get("payment_status")

    if not customer_id:
        logger.warning("checkout.session.completed: no customer_id")
        return

    user = _get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(f"checkout.session.completed: user not found for customer {customer_id}")
        return

    # Increment coupon redemptions if coupon was used
    discount = session.get("total_details", {}).get("breakdown", {}).get("discounts", [])
    if discount and payment_status == "paid":
        from openoutreach.billing.coupons import increment_coupon_redemptions
        # Stripe doesn't directly expose coupon code in session, but we can extract from discount metadata
        # For now, we'll track this via metadata if coupon code was stored during checkout
        coupon_code = session.get("metadata", {}).get("coupon_code")
        if coupon_code:
            increment_coupon_redemptions(coupon_code)

    mode = session.get("mode", "subscription")

    if mode == "payment":
        if payment_status == "paid":
            user.plan = "lifetime"
            user.subscription_status = "active"
            user.billing_period = "lifetime"
            user.current_period_end = None
            user.trial_ends_at = None
            _sync_plan_limits(user)
            user.save()
            try:
                from openoutreach.billing.config import increment_lifetime_buyer_count
                increment_lifetime_buyer_count()
            except Exception as e:
                logger.error(f"Failed to increment lifetime buyer count: {e}")
            try:
                send_lifetime_deal_purchase(user)
            except Exception as e:
                logger.error(f"Failed to send lifetime deal email: {e}")
    else:
        user.stripe_subscription_id = subscription_id

        if subscription_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            if sub:
                user.subscription_status = "trialing" if sub.status == "trialing" else "active"

                plan_name = _get_plan_name_from_subscription(sub)
                if plan_name:
                    user.plan = plan_name

                if sub.trial_start and sub.trial_end:
                    user.trial_ends_at = datetime.fromtimestamp(sub.trial_end, tz=tz.utc)

                if getattr(sub, "current_period_end", None):
                    user.current_period_end = datetime.fromtimestamp(sub.current_period_end, tz=tz.utc)  # type: ignore

                if sub.items and sub.items.data and sub.items.data[0].price.recurring:
                    user.billing_period = "annual" if sub.items.data[0].price.recurring.interval == "year" else "monthly"

                _sync_plan_limits(user)
        else:
            user.subscription_status = "active"

        user.save()
        try:
            send_welcome_email(user)
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")

    logger.info(f"Activated subscription for user {user._id}")


def _sync_plan_limits(user: User) -> None:
    """Sync plan limits from plan definition to user."""
    from openoutreach.billing.plans import get_plan

    plan_def = get_plan(user.plan)
    if not plan_def:
        logger.warning(f"Could not find plan definition for {user.plan}")
        return

    user.linkedin_account_limit = plan_def.get("max_linkedin_accounts", 1)
    user.campaign_limit = plan_def.get("max_campaigns")


def handle_customer_subscription_created(event: dict[str, Any]) -> None:
    """Handle customer.subscription.created event."""
    subscription = event["data"]["object"]
    customer_id = subscription.get("customer")

    if not customer_id:
        logger.warning("customer.subscription.created: no customer_id")
        return

    user = _get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(f"customer.subscription.created: user not found for customer {customer_id}")
        return

    plan_name = _get_plan_name_from_subscription(subscription)
    if plan_name:
        user.plan = plan_name

    user.stripe_subscription_id = subscription.get("id")
    user.subscription_status = "trialing" if subscription.get("status") == "trialing" else "active"

    if subscription.get("trial_end"):
        user.trial_ends_at = datetime.fromtimestamp(subscription["trial_end"], tz=tz.utc)

    if subscription.get("current_period_end"):
        user.current_period_end = datetime.fromtimestamp(subscription["current_period_end"], tz=tz.utc)

    if subscription.get("items", {}).get("data"):
        interval = subscription["items"]["data"][0]["price"]["recurring"]["interval"]
        user.billing_period = "annual" if interval == "year" else "monthly"

    _sync_plan_limits(user)
    user.save()
    logger.info(f"Created subscription for user {user._id}")


def handle_customer_subscription_updated(event: dict[str, Any]) -> None:
    """Handle customer.subscription.updated event (plan changes, etc.)."""
    subscription = event["data"]["object"]
    customer_id = subscription.get("customer")

    if not customer_id:
        logger.warning("customer.subscription.updated: no customer_id")
        return

    user = _get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(f"customer.subscription.updated: user not found for customer {customer_id}")
        return

    old_plan = user.plan
    plan_name = _get_plan_name_from_subscription(subscription)
    if plan_name:
        user.plan = plan_name

    status = subscription.get("status")
    if status == "trialing":
        user.subscription_status = "trialing"
    elif status == "active":
        user.subscription_status = "active"
    elif status == "past_due":
        user.subscription_status = "past_due"
    elif status in ("canceled", "incomplete_expired"):
        user.subscription_status = "canceled"

    if subscription.get("trial_end"):
        user.trial_ends_at = datetime.fromtimestamp(subscription["trial_end"], tz=tz.utc)

    if subscription.get("current_period_end"):
        user.current_period_end = datetime.fromtimestamp(subscription["current_period_end"], tz=tz.utc)

    if subscription.get("items", {}).get("data"):
        interval = subscription["items"]["data"][0]["price"]["recurring"]["interval"]
        user.billing_period = "annual" if interval == "year" else "monthly"

    _sync_plan_limits(user)

    if old_plan != plan_name and plan_name:
        _enforce_linkedin_account_limit(user._id, user.linkedin_account_limit)
        if old_plan and plan_name:
            try:
                # Determine if upgrade or downgrade based on plan hierarchy
                plan_hierarchy = ["starter", "pro", "business", "agency", "cloud"]
                old_idx = plan_hierarchy.index(old_plan) if old_plan in plan_hierarchy else -1
                new_idx = plan_hierarchy.index(plan_name) if plan_name in plan_hierarchy else -1

                if new_idx > old_idx:
                    send_plan_upgraded(user, old_plan, plan_name)
                elif new_idx < old_idx:
                    # Downgrade - schedule for period end
                    effective_date = datetime.fromtimestamp(subscription.get("current_period_end", 0), tz=tz.utc)
                    send_plan_downgraded(user, old_plan, plan_name, effective_date)
            except Exception as e:
                logger.error(f"Failed to send plan change email: {e}")

    user.save()
    logger.info(f"Updated subscription for user {user._id}")

    if status == "past_due":
        logger.warning(f"Subscription past due for user {user._id}")
        try:
            send_payment_failed(user)
        except Exception as e:
            logger.error(f"Failed to send payment failed email: {e}")


def handle_customer_subscription_deleted(event: dict[str, Any]) -> None:
    """Handle customer.subscription.deleted event (cancellation)."""
    subscription = event["data"]["object"]
    customer_id = subscription.get("customer")

    if not customer_id:
        logger.warning("customer.subscription.deleted: no customer_id")
        return

    user = _get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(f"customer.subscription.deleted: user not found for customer {customer_id}")
        return

    user.subscription_status = "canceled"
    user.stripe_subscription_id = None
    user.save()

    _deactivate_user_profiles(user._id)
    logger.info(f"Canceled subscription for user {user._id}")


def _apply_referral_credit(user: User, invoice: dict[str, Any]) -> None:
    """Apply referral credits when a referred user makes first payment."""
    if not user.referrer_id:
        return

    # Only apply credit once - check if already credited
    if user.referral_credit_applied:
        return

    # Only apply on first payment - check if this is NOT a renewal
    billing_reason = invoice.get("billing_reason")
    if billing_reason != "subscription_create":
        logger.debug(f"Skipping referral credit for {user.email}: billing_reason={billing_reason}")
        return

    from openoutreach.billing.referrals import ReferralCode

    referrer = User.get(user.referrer_id)
    if not referrer:
        logger.warning(f"Referrer not found: {user.referrer_id}")
        return

    ref_code = ReferralCode.get_by_user_id(referrer._id)
    if not ref_code or not ref_code.code:
        return

    if not ReferralCode.increment_usage(ref_code.code):
        return

    if referrer.stripe_customer_id:
        try:
            stripe.Customer.create_balance_transaction(
                referrer.stripe_customer_id,
                amount=-1900,
                currency="usd",
                description=f"Referral credit from {user.email}",
            )
            logger.info(f"Applied $19 Stripe credit to {referrer.email} from new user {user.email}")
        except stripe.StripeError as e:
            logger.error(f"Failed to apply Stripe credit to {referrer.email}: {e}")
            return
    else:
        logger.warning(f"Referrer {referrer.email} has no Stripe customer ID, credit tracked locally only")

    # Mark credit as applied to prevent duplicate credits on renewals
    user.referral_credit_applied = True
    user.save()


def handle_invoice_payment_succeeded(event: dict[str, Any]) -> None:
    """Handle invoice.payment_succeeded event."""
    invoice = event["data"]["object"]
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")

    if not customer_id:
        logger.warning("invoice.payment_succeeded: no customer_id")
        return

    user = _get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(f"invoice.payment_succeeded: user not found for customer {customer_id}")
        return

    if subscription_id:
        sub = stripe.Subscription.retrieve(subscription_id)
        if sub and getattr(sub, "current_period_end", None):
            user.current_period_end = datetime.fromtimestamp(sub.current_period_end, tz=tz.utc)  # type: ignore

    user.subscription_status = "active"
    user.save()

    _apply_referral_credit(user, invoice)

    logger.info(f"Payment succeeded for user {user._id}")


def handle_invoice_payment_failed(event: dict[str, Any]) -> None:
    """Handle invoice.payment_failed event."""
    invoice = event["data"]["object"]
    customer_id = invoice.get("customer")

    if not customer_id:
        logger.warning("invoice.payment_failed: no customer_id")
        return

    user = _get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(f"invoice.payment_failed: user not found for customer {customer_id}")
        return

    user.subscription_status = "past_due"
    user.save()
    logger.warning(f"Payment failed for user {user._id}")

    try:
        send_payment_failed(user)
    except Exception as e:
        logger.error(f"Failed to send payment failed email: {e}")


def _is_event_processed(event_id: str) -> bool:
    """Check if a webhook event has already been processed (idempotency)."""
    webhook_events = get_mongodb_collection("webhook_events")
    if webhook_events is None:
        return False

    existing = webhook_events.find_one({"stripe_event_id": event_id})
    return existing is not None


def _mark_event_processed(event_id: str) -> None:
    """Mark a webhook event as processed."""
    webhook_events = get_mongodb_collection("webhook_events")
    if webhook_events is None:
        return

    try:
        webhook_events.insert_one({
            "stripe_event_id": event_id,
            "processed_at": datetime.now(tz.utc),
        })
    except Exception as e:
        logger.error(f"Failed to mark event {event_id} as processed: {e}")


def process_webhook_event(event: dict[str, Any]) -> bool:
    """
    Process a Stripe webhook event.
    Returns True if handled successfully, False if skipped/unknown.
    """
    event_id: Optional[str] = event.get("id")
    event_type: Optional[str] = event.get("type")

    if not event_type:
        logger.warning("Webhook event missing type field")
        return False

    if event_id and _is_event_processed(event_id):
        logger.debug(f"Event {event_id} already processed, skipping")
        return True

    logger.info(f"Processing webhook event: {event_type}")

    handlers: dict[str, Any] = {
        "checkout.session.completed": handle_checkout_session_completed,
        "customer.subscription.created": handle_customer_subscription_created,
        "customer.subscription.updated": handle_customer_subscription_updated,
        "customer.subscription.deleted": handle_customer_subscription_deleted,
        "customer.subscription.trial_will_end": handle_customer_subscription_trial_will_end,
        "invoice.payment_succeeded": handle_invoice_payment_succeeded,
        "invoice.payment_failed": handle_invoice_payment_failed,
    }

    handler = handlers.get(event_type)
    if not handler:
        logger.debug(f"No handler for event type: {event_type}")
        return False

    try:
        handler(event)
        if event_id:
            _mark_event_processed(event_id)
        return True
    except Exception as e:
        logger.error(f"Error processing event {event_type}: {e}", exc_info=True)
        return False


def _get_plan_name_from_subscription(subscription: Any) -> Optional[str]:
    """Extract plan name from Stripe subscription object."""
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None

    product_id: Optional[str] = items[0].get("price", {}).get("product")
    if not product_id:
        return None

    try:
        product = stripe.Product.retrieve(product_id)
        return product.metadata.get("plan_name")  # type: ignore
    except stripe.StripeError as e:
        logger.error(f"Failed to retrieve product {product_id}: {e}")
        return None


def handle_customer_subscription_trial_will_end(event: dict[str, Any]) -> None:
    """Handle customer.subscription.trial_will_end event (1 day before trial end)."""
    subscription = event["data"]["object"]
    customer_id = subscription.get("customer")

    if not customer_id:
        logger.warning("customer.subscription.trial_will_end: no customer_id")
        return

    user = _get_user_by_stripe_customer(customer_id)
    if not user:
        logger.warning(f"customer.subscription.trial_will_end: user not found for customer {customer_id}")
        return

    try:
        send_trial_expiry_warning(user, 1)
    except Exception as e:
        logger.error(f"Failed to send trial expiry warning email: {e}")

    logger.info(f"Sent trial expiry warning for user {user._id}")


def _deactivate_user_profiles(user_id: str) -> None:
    """Deactivate all LinkedIn profiles for a user on subscription cancel/expire."""
    profiles_collection = get_mongodb_collection("linkedin_profiles")
    if profiles_collection is None:
        logger.warning("Could not deactivate profiles: collection not available")
        return

    try:
        result = profiles_collection.update_many(
            {"user_id": user_id, "is_active": True},
            {"$set": {"is_active": False}},
        )
        logger.info(f"Deactivated {result.modified_count} profiles for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to deactivate profiles for user {user_id}: {e}")


def _enforce_linkedin_account_limit(user_id: str, limit: int) -> None:
    """Deactivate excess LinkedIn profiles beyond the account limit."""
    profiles_collection = get_mongodb_collection("linkedin_profiles")
    if profiles_collection is None:
        logger.warning("Could not enforce account limits: collection not available")
        return

    try:
        active_profiles = list(
            profiles_collection.find(
                {"user_id": user_id, "is_active": True},
                sort=[("created_at", 1)],
            )
        )

        if len(active_profiles) > limit:
            excess_profiles = active_profiles[limit:]
            excess_ids = [p["_id"] for p in excess_profiles]

            profiles_collection.update_many(
                {"_id": {"$in": excess_ids}},
                {"$set": {"is_active": False}},
            )
            logger.info(f"Deactivated {len(excess_profiles)} excess profiles for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to enforce account limits for user {user_id}: {e}")
