# openoutreach/linkedin/setup/freemium.py
"""Freemium campaign creation from kit config."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def import_freemium_campaign(kit_config: dict):
    """Create or update a freemium Campaign from kit config.

    Adds all active users to the campaign.
    Returns the Campaign instance or None.
    """
    from openoutreach.mongodb.models import Campaign
    from openoutreach.linkedin.models import LinkedInProfile
    from openoutreach.mongodb.connection import get_mongodb_collection

    campaign_name = kit_config.get("campaign_name", "Freemium Outreach")

    # Find or create campaign
    collection = get_mongodb_collection("campaigns")
    if collection is None:
        logger.error("MongoDB collection 'campaigns' not available")
        return None

    existing_doc = collection.find_one({"name": campaign_name})
    if existing_doc:
        # Update existing campaign
        campaign = Campaign.from_dict(existing_doc)
        campaign.product_pitch = kit_config["product_pitch"]
        campaign.campaign_objective = kit_config["campaign_objective"]
        campaign.booking_link = kit_config["booking_link"]
        campaign.is_freemium = True
        campaign.action_fraction = kit_config["action_fraction"]
        campaign.save()
    else:
        # Create new campaign
        campaign = Campaign(
            name=campaign_name,
            product_pitch=kit_config["product_pitch"],
            campaign_objective=kit_config["campaign_objective"],
            booking_link=kit_config["booking_link"],
            is_freemium=True,
            action_fraction=kit_config["action_fraction"],
        )
        campaign.save()

    # Add all active LinkedIn users to this campaign
    profiles = LinkedInProfile.objects.filter(active=True)
    user_ids = [lp.user_id for lp in profiles if lp.user_id]
    if user_ids and hasattr(campaign, 'team_member_ids'):
        campaign.team_member_ids = list(set((campaign.team_member_ids or []) + user_ids))
        campaign.save()

    logger.info(
        "[Freemium] Campaign imported: %s (action_fraction=%.2f)",
        campaign_name,
        kit_config["action_fraction"],
    )
    return campaign


def seed_profiles(session, kit_config: dict):
    """Seed Lead (with embedding) + QUALIFIED Deal for profiles listed in kit config."""
    from openoutreach.mongodb.models import Lead
    from openoutreach.core.db.deals import create_freemium_deal
    from linkedin_cli.url_utils import public_id_to_url

    public_ids = kit_config.get("seed_profiles", [])
    if not public_ids:
        return

    for public_id in public_ids:
        url = public_id_to_url(public_id)

        # Get or create lead
        lead = Lead.get_by_public_id(public_id)
        if not lead:
            lead = Lead(public_identifier=public_id, linkedin_url=url)
            lead.save()

        lead.get_embedding(session)
        create_freemium_deal(session, public_id)
