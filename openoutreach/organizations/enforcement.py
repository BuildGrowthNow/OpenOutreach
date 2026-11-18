"""Effective plan and seat resolution for personal users and org members.

A member inherits the workspace owner's plan, cloud seat pool, and limits.
Personal users keep their own plan. When team workspaces are disabled the
resolution is a no-op and every user bills personally.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from openoutreach.billing.plans import (
    effective_cloud_seat_limit,
    effective_linkedin_account_limit,
)
from openoutreach.mongodb.models_user import User
from openoutreach.organizations.access import resolve_org_context
from openoutreach.organizations.service import team_workspaces_enabled

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EffectivePlan:
    plan: str
    cloud_profiles: int
    linkedin_account_limit: int
    whatsapp_account_limit: int
    campaign_limit: Optional[int]
    subscription_status: str
    trial_ends_at: Optional[datetime]
    billing_owner_id: str
    billing_owner_email: Optional[str]
    org_id: Optional[str]
    role: str
    is_billing_owner: bool
    cloud_seat_limit: int

    @property
    def is_active(self) -> bool:
        if self.subscription_status not in ("active", "trialing"):
            return False
        if self.subscription_status == "trialing" and self.trial_ends_at:
            trial_ends = self.trial_ends_at
            if trial_ends.tzinfo is None:
                trial_ends = trial_ends.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > trial_ends:
                return False
        return True


def _personal_plan(user: User) -> EffectivePlan:
    plan = user.plan or "starter"
    cloud_profiles = int(user.cloud_profiles or 0)
    return EffectivePlan(
        plan=plan,
        cloud_profiles=cloud_profiles,
        linkedin_account_limit=effective_linkedin_account_limit(
            plan, cloud_profiles, user.linkedin_account_limit
        ),
        whatsapp_account_limit=int(user.whatsapp_account_limit or 0),
        campaign_limit=user.campaign_limit,
        subscription_status=user.subscription_status or "none",
        trial_ends_at=user.trial_ends_at,
        billing_owner_id=user._id,
        billing_owner_email=user.email,
        org_id=None,
        role="owner",
        is_billing_owner=True,
        cloud_seat_limit=effective_cloud_seat_limit(plan, cloud_profiles),
    )


def resolve_effective_plan(user: User) -> EffectivePlan:
    """Return the plan and limits that apply to ``user`` right now.

    The function is fail-safe: if organization state cannot be read, the
    caller's own billing fields are used. This keeps legacy personal flows
    working during rollout and rollback.
    """
    if not team_workspaces_enabled():
        return _personal_plan(user)
    try:
        ctx = resolve_org_context(user)
        owner = user
        if ctx.org.owner_user_id and ctx.org.owner_user_id != user._id:
            owner = User.get(ctx.org.owner_user_id) or user
        plan = owner.plan or "starter"
        cloud_profiles = int(owner.cloud_profiles or 0)
        if ctx.org.seat_override:
            cloud_profiles = int(ctx.org.cloud_seats or 0)
            plan = ctx.org.plan or plan
        subscription_status = owner.subscription_status or "none"
        if owner.status == "blocked":
            subscription_status = "blocked"
        return EffectivePlan(
            plan=plan,
            cloud_profiles=cloud_profiles,
            linkedin_account_limit=effective_linkedin_account_limit(
                plan, cloud_profiles, owner.linkedin_account_limit
            ),
            whatsapp_account_limit=int(owner.whatsapp_account_limit or 0),
            campaign_limit=owner.campaign_limit,
            subscription_status=subscription_status,
            trial_ends_at=owner.trial_ends_at,
            billing_owner_id=owner._id,
            billing_owner_email=owner.email,
            org_id=ctx.org_id,
            role=ctx.role,
            is_billing_owner=owner._id == user._id,
            cloud_seat_limit=effective_cloud_seat_limit(plan, cloud_profiles),
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning(
            "effective_plan_resolution_failed user_id=%s exception_type=%s",
            user._id,
            type(exc).__name__,
        )
        return _personal_plan(user)
