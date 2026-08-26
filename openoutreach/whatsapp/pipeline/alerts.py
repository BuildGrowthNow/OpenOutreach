"""Alerting helpers for WA pipeline scraper failures."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def fire_scrape_zero_results(
    campaign_id: str,
    user_id: str,
    source: str,
    query: str,
) -> None:
    """Fire a campaign_error Notification when a scraper returns 0 raw listings.

    Deduped by (source, campaign_id) so the operator is notified once per
    unacknowledged failure, not on every daemon cycle.
    """
    try:
        from openoutreach.mongodb.connection import get_mongodb_collection
        from openoutreach.mongodb.models_extended import Notification

        notif_col = get_mongodb_collection("notifications")
        if notif_col is None:
            return

        dedup_key = f"scrape_zero_{source}_{campaign_id}"
        if notif_col.find_one({"data.dedup_key": dedup_key, "is_read": False}):
            return

        Notification(
            recipient_id=user_id,
            notification_type=Notification.TYPE_CAMPAIGN_ERROR,
            title=f'Lead scraper "{source}" returned 0 results',
            message=(
                f'The "{source}" scraper found no businesses for query "{query}". '
                f"This usually means the source is temporarily blocked or the query "
                f"returned no matches. Check your campaign settings or try a different "
                f"lead source. The scraper will retry automatically on the next cycle."
            ),
            campaign_id=campaign_id,
            data={"dedup_key": dedup_key, "source": source, "query": query},
        ).save()
        logger.info(
            "alerts: zero-results notification fired for source=%s campaign=%s",
            source, campaign_id,
        )
    except Exception as exc:
        logger.warning("alerts: failed to fire zero-results notification: %s", exc)
