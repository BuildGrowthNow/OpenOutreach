import { useBilling } from "@/lib/contexts/billing-context";

export function useFeatureAccess(featureName: string): { hasAccess: boolean; requiredPlan: string | null } {
  const { billingStatus } = useBilling();

  if (!billingStatus) {
    return { hasAccess: false, requiredPlan: null };
  }

  const featureMap: Record<string, string> = {
    ai_messages: "starter",
    voice_notes: "pro",
    ai_follow_ups: "pro",
    sales_navigator: "pro",
    api_access: "pro",
    team_members: "business",
    white_label: "agency",
    custom_domain: "agency",
  };

  const planHierarchy = ["starter", "pro", "business", "agency", "cloud"];
  const requiredPlan = featureMap[featureName];

  if (!requiredPlan) {
    return { hasAccess: true, requiredPlan: null };
  }

  // Lifetime plan is equivalent to Pro tier
  const userPlan = billingStatus.plan === "lifetime" ? "pro" : billingStatus.plan;

  const currentPlanIndex = planHierarchy.indexOf(userPlan);
  const requiredPlanIndex = planHierarchy.indexOf(requiredPlan);

  const hasAccess =
    billingStatus.subscription_status === "active" ||
    billingStatus.subscription_status === "trialing"
      ? currentPlanIndex >= requiredPlanIndex
      : false;

  return { hasAccess, requiredPlan: !hasAccess ? requiredPlan : null };
}
