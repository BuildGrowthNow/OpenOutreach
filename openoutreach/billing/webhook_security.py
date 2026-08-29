"""
Webhook signature verification for Stripe events.
Prevents fake/spoofed events from being processed.
"""
import logging
from typing import Any

import stripe

from openoutreach.config import settings

logger = logging.getLogger(__name__)


class WebhookSignatureValidator:
    """Validates Stripe webhook signatures."""

    @staticmethod
    def verify_signature(payload: bytes, sig_header: str) -> tuple[bool, str | None]:
        """
        Verify Stripe webhook signature.
        Returns (is_valid, error_message).
        """
        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.error("STRIPE_WEBHOOK_SECRET not configured")
            return False, "Webhook secret not configured"

        try:
            stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET,
            )
            return True, None
        except stripe.SignatureVerificationError as e:
            logger.warning("Invalid webhook signature; exception_type=%s", type(e).__name__)
            return False, f"Invalid signature: {e}"
        except Exception as e:
            logger.error("Webhook verification error; exception_type=%s", type(e).__name__)
            return False, f"Verification error: {e}"

    @staticmethod
    def construct_event(payload: bytes, sig_header: str) -> tuple[Any | None, str | None]:
        """
        Construct and verify a Stripe event.
        Returns (event, error_message).
        """
        if not settings.STRIPE_WEBHOOK_SECRET:
            return None, "Webhook secret not configured"

        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET,
            )
            return event, None
        except stripe.SignatureVerificationError as e:
            logger.warning("Invalid webhook signature; exception_type=%s", type(e).__name__)
            return None, "Invalid signature"
        except Exception as e:
            logger.error("Webhook construction error; exception_type=%s", type(e).__name__)
            return None, "Failed to construct event"
