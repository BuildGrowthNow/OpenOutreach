import { useBilling } from "@/lib/contexts/billing-context";

export type LimitResource = "campaigns" | "linkedin_accounts";

interface PlanLimitResult {
  atLimit: boolean;
  used: number;
  limit: number | null;
  subscriptionActive: boolean;
}

const ACTIVE_STATUSES = new Set(["active", "trialing"]);

export function usePlanLimit(resource: LimitResource): PlanLimitResult {
  const { billingStatus, usage } = useBilling();

  const subscriptionActive = billingStatus
    ? ACTIVE_STATUSES.has(billingStatus.subscription_status)
    : true; // optimistic while loading

  if (!billingStatus || !usage) {
    return { atLimit: false, used: 0, limit: null, subscriptionActive };
  }

  if (resource === "campaigns") {
    const limit = billingStatus.campaign_limit ?? null;
    const used = usage.campaigns_used ?? 0;
    return {
      atLimit: limit !== null && used >= limit,
      used,
      limit,
      subscriptionActive,
    };
  }

  const limit = billingStatus.linkedin_account_limit ?? null;
  const used = usage.linkedin_accounts_used ?? 0;
  return {
    atLimit: limit !== null && used >= limit,
    used,
    limit,
    subscriptionActive,
  };
}
