"""
Stripe webhook event handlers for subscription lifecycle management.
"""
import logging
from datetime import datetime, timezone as tz
from typing import Any, Optional

import stripe

from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.connection import get_mongodb_collection

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

    mode = session.get("mode", "subscription")

    if mode == "payment":
        if payment_status == "paid":
            user.plan = "lifetime"
            user.subscription_status = "active"
            user.billing_period = "lifetime"
            user.current_period_end = None
            user.trial_ends_at = None
            _sync_plan_limits(user)
    else:
        user.stripe_subscription_id = subscription_id
        user.subscription_status = "trialing" if session.get("mode") == "subscription" else "active"

        if subscription_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            if sub:
                plan_name = _get_plan_name_from_subscription(sub)
                if plan_name:
                    user.plan = plan_name

                if sub.trial_start and sub.trial_end:
                    user.trial_ends_at = datetime.fromtimestamp(sub.trial_end, tz=tz.utc)

                if sub.current_period_end:
                    user.current_period_end = datetime.fromtimestamp(sub.current_period_end, tz=tz.utc)

                user.billing_period = "annual" if sub.items.data[0].price.recurring.interval == "year" else "monthly"
                _sync_plan_limits(user)

    user.save()
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

    user.save()
    logger.info(f"Updated subscription for user {user._id}")

    if status == "past_due":
        logger.warning(f"Subscription past due for user {user._id}")


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
        if sub and sub.current_period_end:
            user.current_period_end = datetime.fromtimestamp(sub.current_period_end, tz=tz.utc)

    user.subscription_status = "active"
    user.save()
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


def _get_plan_name_from_subscription(subscription: dict[str, Any]) -> Optional[str]:
    """Extract plan name from Stripe subscription object."""
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None

    product_id: Optional[str] = items[0].get("price", {}).get("product")
    if not product_id:
        return None

    try:
        product = stripe.Product.retrieve(product_id)
        return product.metadata.get("plan_name")
    except stripe.error.StripeError as e:
        logger.error(f"Failed to retrieve product {product_id}: {e}")
        return None


def _deactivate_user_profiles(user_id: str) -> None:
    """Deactivate all LinkedIn profiles for a user."""
    profiles_collection = get_mongodb_collection("linkedin_profiles")
    if profiles_collection is None:
        logger.warning("Could not deactivate profiles: collection not available")
        return

    try:
        profiles_collection.update_many(
            {"user_id": user_id},
            {"$set": {"is_active": False}},
        )
        logger.info(f"Deactivated all profiles for user {user_id}")
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
            excess_count = len(active_profiles) - limit
            excess_profiles = active_profiles[:excess_count]
            excess_ids = [p["_id"] for p in excess_profiles]

            profiles_collection.update_many(
                {"_id": {"$in": excess_ids}},
                {"$set": {"is_active": False}},
            )
            logger.info(f"Deactivated {excess_count} excess profiles for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to enforce account limits for user {user_id}: {e}")
