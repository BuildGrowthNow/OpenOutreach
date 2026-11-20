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
            user.intended_plan = None
            _sync_plan_limits(user)
            user.save()
            try:
                from openoutreach.billing.config import increment_lifetime_buyer_count
                increment_lifetime_buyer_count()
            except Exception as e:
                logger.error("Failed to increment lifetime buyer count; exception_type=%s", type(e).__name__)
            try:
                send_lifetime_deal_purchase(user)
            except Exception as e:
                logger.error("Failed to send lifetime deal email; exception_type=%s", type(e).__name__)
    else:
        user.stripe_subscription_id = subscription_id

        if subscription_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            if sub:
                user.subscription_status = "trialing" if sub.status == "trialing" else "active"

                _sync_subscription_items(user, sub)

                if sub.trial_start and sub.trial_end:
                    user.trial_ends_at = datetime.fromtimestamp(sub.trial_end, tz=tz.utc)

                if getattr(sub, "current_period_end", None):
                    user.current_period_end = datetime.fromtimestamp(sub.current_period_end, tz=tz.utc)  # type: ignore
        else:
            user.subscription_status = "active"

        # Checkout is complete; clear the signup intent even when Stripe
        # returns a subscription object without expanded items.
        user.intended_plan = None
        user.save()
        try:
            send_welcome_email(user)
        except Exception as e:
            logger.error("Failed to send welcome email; exception_type=%s", type(e).__name__)

    logger.info(f"Activated subscription for user {user._id}")


def _sync_plan_limits(user: User) -> None:
    """Sync plan limits from plan definition to user."""
    from openoutreach.billing.plans import apply_plan_entitlements

    apply_plan_entitlements(user)


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
    user.intended_plan = None

    if subscription.get("trial_end"):
        user.trial_ends_at = datetime.fromtimestamp(subscription["trial_end"], tz=tz.utc)

    if subscription.get("current_period_end"):
        user.current_period_end = datetime.fromtimestamp(subscription["current_period_end"], tz=tz.utc)

    _sync_subscription_items(user, subscription)
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
    old_cloud_profiles = user.cloud_profiles
    plan_name = _get_plan_name_from_subscription(subscription)
    if plan_name:
        user.plan = plan_name

    user.intended_plan = None
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

    _sync_subscription_items(user, subscription)

    plan_changed = old_plan != plan_name and bool(plan_name)
    seats_reduced = user.cloud_profiles < old_cloud_profiles
    if plan_changed or seats_reduced:
        prefer_cloud = old_plan == "cloud" or user.plan == "cloud"
        _enforce_linkedin_account_limit(
            user._id,
            user.linkedin_account_limit,
            prefer_execution_mode="cloud" if prefer_cloud else None,
        )
    if plan_changed:
        _enforce_wa_account_limit(user._id, user.whatsapp_account_limit)

    if plan_changed and plan_name:
        try:
            # Determine if upgrade or downgrade based on plan hierarchy
            plan_hierarchy = ["starter", "pro", "lifetime", "business", "agency", "cloud"]
            old_idx = plan_hierarchy.index(old_plan) if old_plan in plan_hierarchy else -1
            new_idx = plan_hierarchy.index(plan_name) if plan_name in plan_hierarchy else -1

            if new_idx > old_idx:
                send_plan_upgraded(user, old_plan, plan_name)
            elif new_idx < old_idx:
                # Downgrade - schedule for period end
                effective_date = datetime.fromtimestamp(subscription.get("current_period_end", 0), tz=tz.utc)
                send_plan_downgraded(user, old_plan, plan_name, effective_date)
        except Exception as e:
            logger.error("Failed to send plan change email; exception_type=%s", type(e).__name__)

    user.save()
    logger.info(f"Updated subscription for user {user._id}")

    if status == "past_due":
        logger.warning(f"Subscription past due for user {user._id}")
        try:
            send_payment_failed(user)
        except Exception as e:
            logger.error("Failed to send payment failed email; exception_type=%s", type(e).__name__)


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
    user.cloud_profiles = 0
    _sync_plan_limits(user)
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
            logger.error("Failed to apply Stripe credit; exception_type=%s", type(e).__name__)
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
        logger.error("Failed to send payment failed email; exception_type=%s", type(e).__name__)


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
        logger.error("Failed to mark event processed; event_id=%s exception_type=%s", event_id, type(e).__name__)


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
        logger.error("Error processing event; event_type=%s exception_type=%s", event_type, type(e).__name__)
        return False


def _get_plan_name_from_subscription(subscription: Any) -> Optional[str]:
    """Extract the base plan name, skipping cloud add-on seat items."""
    items = _subscription_items(subscription)
    product_cache: dict[str, Optional[str]] = {}
    for item in items:
        plan_name = _item_plan_name(item, product_cache)
        if plan_name and plan_name != "cloud_addon":
            return plan_name
    return None


def _subscription_items(subscription: Any) -> list:
    """Return every subscription item, tolerating dict and StripeObject input."""
    items = subscription.get("items") or {}
    if hasattr(items, "get"):
        return list(items.get("data") or [])
    return []


def _item_plan_name(item: Any, product_cache: dict[str, Optional[str]]) -> Optional[str]:
    """Resolve a subscription item's plan from price metadata or its product.

    Price keys written by ``sync_stripe_products`` are ``<plan>_monthly``,
    ``<plan>_annual``, ``cloud_addon``, or ``lifetime``. Product metadata is
    the authoritative fallback for prices created elsewhere.
    """
    price = item.get("price") or {}
    metadata = price.get("metadata") or {}
    price_key = metadata.get("price_key")
    if price_key:
        if price_key == "cloud_addon":
            return "cloud_addon"
        for suffix in ("_monthly", "_annual"):
            if price_key.endswith(suffix):
                return price_key[: -len(suffix)]
        if price_key == "lifetime":
            return "lifetime"

    product_id = price.get("product")
    if not product_id:
        return None
    if product_id not in product_cache:
        try:
            product = stripe.Product.retrieve(product_id)
            product_cache[product_id] = product.metadata.get("plan_name")  # type: ignore[union-attr]
        except stripe.StripeError as e:
            logger.error("Failed to retrieve product; exception_type=%s", type(e).__name__)
            product_cache[product_id] = None
    return product_cache[product_id]


def _sync_subscription_items(user: User, subscription: Any) -> None:
    """Sync the base plan, billing period, and cloud seat quantity.

    Reads every subscription item: the first non-add-on item is the plan and
    every ``cloud_addon`` item contributes its quantity to ``cloud_profiles``.
    ``cloud_addon`` is never treated as a plan.
    """
    base_plan: Optional[str] = None
    billing_period: Optional[str] = None
    cloud_seats = 0
    product_cache: dict[str, Optional[str]] = {}

    for item in _subscription_items(subscription):
        plan_name = _item_plan_name(item, product_cache)
        if plan_name == "cloud_addon":
            cloud_seats += int(item.get("quantity") or 0)
            continue
        if plan_name and base_plan is None:
            base_plan = plan_name
            recurring = (item.get("price") or {}).get("recurring") or {}
            interval = recurring.get("interval")
            if interval:
                billing_period = "annual" if interval == "year" else "monthly"

    if base_plan:
        user.plan = base_plan
    if billing_period:
        user.billing_period = billing_period
    user.cloud_profiles = cloud_seats
    _sync_plan_limits(user)



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
        logger.error("Failed to send trial expiry warning email; exception_type=%s", type(e).__name__)

    logger.info(f"Sent trial expiry warning for user {user._id}")


def _deactivate_user_profiles(user_id: str) -> None:
    """Deactivate LinkedIn profiles on subscription cancel/expire.

    For a workspace owner this includes profiles owned by active members, so a
    cancelled workspace cannot keep running accounts on the owner's plan.
    """
    profiles_collection = get_mongodb_collection("linkedin_profiles")
    if profiles_collection is None:
        logger.warning("Could not deactivate profiles: collection not available")
        return

    query: dict = {"user_id": user_id, "is_active": True}
    try:
        from openoutreach.billing.seats import org_ids_owned_by
        from openoutreach.organizations.service import team_workspaces_enabled

        if team_workspaces_enabled():
            org_ids = org_ids_owned_by(user_id)
            query = {
                "$or": [
                    {"org_id": {"$in": org_ids}},
                    # Only legacy personal rows. A bare user_id match would
                    # also pause team profiles a member created while they
                    # still had their own personal subscription.
                    {"org_id": {"$exists": False}, "user_id": user_id},
                    {"org_id": None, "user_id": user_id},
                ],
                "is_active": True,
            }
    except Exception:
        pass

    try:
        profile_ids = [
            str(doc["_id"])
            for doc in profiles_collection.find(query, {"_id": 1})
        ]
        result = profiles_collection.update_many(
            query,
            {
                "$set": {
                    "is_active": False,
                    "active": False,
                    "daemon_status": "seat_required",
                }
            },
        )
        logger.info(f"Deactivated {result.modified_count} profiles for user {user_id}")
    except Exception as e:
        logger.error("Failed to deactivate profiles; user_id=%s exception_type=%s", user_id, type(e).__name__)
        return

    # A cancelled subscription must not leave paid Massive sub-accounts
    # enabled. Keep the proxy bound to the same profile so a later
    # re-subscription can re-enable it, but stop provider spend now.
    for profile_id in profile_ids:
        try:
            from openoutreach.proxies.provisioning import disable_massive_for_profile

            disable_massive_for_profile(profile_id, reason="subscription_canceled")
        except Exception as exc:  # pragma: no cover - cancellation must finish
            logger.debug(
                "Could not disable Massive sub-account for profile_id=%s exception_type=%s",
                profile_id,
                type(exc).__name__,
            )


def _enforce_wa_account_limit(user_id: str, limit: int) -> None:
    """Delete excess WhatsApp profiles beyond the account limit."""
    wa_collection = get_mongodb_collection("whatsapp_profiles")
    if wa_collection is None:
        logger.warning("Could not enforce WA account limits: collection not available")
        return

    try:
        profiles = list(
            wa_collection.find(
                {"user_id": user_id},
                sort=[("created_at", 1)],
            )
        )

        if len(profiles) > limit:
            excess = profiles[limit:]
            excess_ids = [p["_id"] for p in excess]
            wa_collection.delete_many({"_id": {"$in": excess_ids}})
            logger.info(f"Deleted {len(excess)} excess WA profiles for user {user_id}")
    except Exception as e:
        logger.error("Failed to enforce WA account limits; user_id=%s exception_type=%s", user_id, type(e).__name__)


def _enforce_linkedin_account_limit(
    user_id: str,
    limit: int,
    *,
    prefer_execution_mode: str | None = None,
) -> None:
    """Pause excess LinkedIn profiles beyond the account limit."""
    from openoutreach.billing.downgrade_handler import pause_excess_linkedin_profiles

    pause_excess_linkedin_profiles(
        user_id,
        limit,
        prefer_execution_mode=prefer_execution_mode,
    )
