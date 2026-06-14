# openoutreach/linkedin/services/ghost_mode.py
"""Ghost Mode interceptor for safe testing without sending real LinkedIn actions."""
from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Dict, Optional, List, Any

from django.utils import timezone

from openoutreach.linkedin.models.ghost_mode import GhostCampaign, GhostSimulationLog

logger = logging.getLogger(__name__)


class GhostModeInterceptor:
    """Intercepts LinkedIn actions for ghost mode testing."""

    def __init__(self, campaign: GhostCampaign):
        self.campaign = campaign
        self.enabled = campaign.is_active

    def can_proceed(self, action_type: str) -> bool:
        """Check if action should proceed (normal mode) or be intercepted (ghost mode)."""
        if not self.enabled:
            return True  # Not in ghost mode, proceed normally

        if action_type in ["search", "qualify", "connect", "message", "follow_up"]:
            return False  # Ghost mode - don't actually perform

        return True

    def simulate_action(
        self,
        action_type: str,
        target_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Simulate an action in ghost mode."""
        if not self.enabled:
            return {"success": False, "error": "Ghost mode not enabled"}

        simulation_start = timezone.now()

        # Simulate different action types
        if action_type == "search":
            result = self._simulate_search(target_data)
        elif action_type == "qualify":
            result = self._simulate_qualify(target_data, context)
        elif action_type == "connect":
            result = self._simulate_connect(target_data)
        elif action_type == "message":
            result = self._simulate_message(target_data)
        elif action_type == "follow_up":
            result = self._simulate_follow_up(target_data, context)
        else:
            result = {"success": True, "message": f"Simulated {action_type}"}

        simulation_duration = (timezone.now() - simulation_start).total_seconds()

        # Log simulation
        GhostSimulationLog.objects.create(
            ghost_campaign=self.campaign,
            action_type=action_type,
            target_url=target_data.get("linkedin_url", ""),
            target_name=target_data.get("name", "Unknown"),
            result_data=result,
            rating=result.get("rating", None),
            score=result.get("score", None),
            started_at=simulation_start,
            completed_at=timezone.now(),
            simulated_action={
                "action_type": action_type,
                "target": target_data,
                "context": context,
                "duration_seconds": simulation_duration,
            },
        )

        # Update campaign stats
        self._update_campaign_stats(action_type, result)

        return result

    def _simulate_search(self, target_data: Dict) -> Dict:
        """Simulate lead search."""
        # Return simulated results based on search keywords
        search_keywords = target_data.get("keywords", [])

        # Simulate finding 5-10 leads
        num_leads = random.randint(5, 10)

        leads = []
        for i in range(num_leads):
            leads.append({
                "name": f"Lead_{i+1}",
                "public_identifier": f"lead{i+1}",
                "linkedin_url": f"https://linkedin.com/in/lead{i+1}",
                "company": random.choice(["Company A", "Company B", "Company C"]),
                "job_title": random.choice(["Manager", "Director", "VP", "Founder"]),
                "industry": random.choice(["Tech", "Marketing", "Sales", "Finance"]),
                "match_score": random.uniform(0.3, 0.9),
                "match_reason": f"Match found for keyword: {random.choice(search_keywords) if search_keywords else 'general'}",
            })

        return {
            "success": True,
            "leads_found": len(leads),
            "leads": leads,
        }

    def _simulate_qualify(self, target_data: Dict, context: Optional[Dict]) -> Dict:
        """Simulate lead qualification."""
        # Simulate qualification based on profile data
        profile = target_data.get("profile", {})

        # Mock qualification logic
        score = random.uniform(0.4, 0.95)
        is_qualified = score > 0.6

        return {
            "success": True,
            "is_qualified": is_qualified,
            "score": score,
            "rating": "good" if is_qualified else "poor",
            "reason": "Profile matches target criteria",
            "simulated_rating": random.randint(1, 5),
        }

    def _simulate_connect(self, target_data: Dict) -> Dict:
        """Simulate connection request."""
        return {
            "success": True,
            "status": "sent",  # Would be "pending" in real mode
            "connection_degree": 1,
            "delay_hours": 48,  # Simulated delay
        }

    def _simulate_message(self, target_data: Dict) -> Dict:
        """Simulate sending a message."""
        message_text = target_data.get("message", "")

        # Simulate response probability
        response_probability = target_data.get("response_probability", 0.35)
        will_response = random.random() < response_probability

        return {
            "success": True,
            "message_sent": True,
            "message_id": f"msg_{timezone.now().timestamp():.0f}",
            "will_response": will_response,
            "simulated_delay_hours": 24 if will_response else None,
            "simulated_response_content": "Thanks for connecting!" if will_response else None,
        }

    def _simulate_follow_up(self, target_data: Dict, context: Optional[Dict]) -> Dict:
        """Simulate follow-up message."""
        days_since = target_data.get("days_since_connect", 3)

        # Simulate follow-up success based on timing
        best_timing = days_since in [2, 3, 5]

        return {
            "success": True,
            "follow_up_sent": True,
            "timing_score": "optimal" if best_timing else "acceptable",
            "will_response": random.random() < 0.5,
        }

    def _update_campaign_stats(self, action_type: str, result: Dict) -> None:
        """Update ghost campaign statistics."""
        if action_type == "search":
            self.campaign.leads_processed += result.get("leads_found", 0)
        elif action_type == "connect":
            self.campaign.connections_simulated += 1
        elif action_type == "message":
            self.campaign.messages_simulated += 1
        elif action_type == "qualify":
            if result.get("is_qualified"):
                self.campaign.conversions_simulated += 1

        # Update average rating/score
        all_logs = GhostSimulationLog.objects.filter(ghost_campaign=self.campaign)
        ratings = [log.rating for log in all_logs if log.rating is not None]
        scores = [log.score for log in all_logs if log.score is not None]

        if ratings:
            self.campaign.avg_rating = sum(ratings) / len(ratings)
        if scores:
            self.campaign.avg_score = sum(scores) / len(scores)

        self.campaign.save()


def ghost_interceptor(campaign: GhostCampaign) -> GhostModeInterceptor:
    """Create a ghost mode interceptor for a campaign."""
    return GhostModeInterceptor(campaign)