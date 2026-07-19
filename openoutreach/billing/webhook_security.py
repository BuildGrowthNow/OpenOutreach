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
        except stripe.error.SignatureVerificationError as e:
            logger.warning(f"Invalid webhook signature: {e}")
            return False, f"Invalid signature: {e}"
        except Exception as e:
            logger.error(f"Webhook verification error: {e}")
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
        except stripe.error.SignatureVerificationError as e:
            logger.warning(f"Invalid webhook signature: {e}")
            return None, f"Invalid signature"
        except Exception as e:
            logger.error(f"Webhook construction error: {e}")
            return None, f"Failed to construct event"
