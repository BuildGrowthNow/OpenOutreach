import { useBilling } from "@/lib/contexts/billing-context";

export function useFeatureAccess(featureName: string): { hasAccess: boolean; requiredPlan: string | null } {
  const { billingStatus } = useBilling();

  if (!billingStatus) {
    return { hasAccess: false, requiredPlan: null };
  }

  const featureMap: Record<string, string> = {
    ai_messages: "starter",
    follow_ups: "starter",
    inbox: "starter",
    analytics: "starter",
    voice_notes: "pro",
    ai_follow_ups: "pro",
    sales_navigator: "pro",
    api_access: "pro",
    team_members: "business",
    workspace_management: "business",
    priority_support: "business",
    white_label: "agency",
    custom_domain: "agency",
    cloud_execution: "cloud",
    campaign_management: "cloud",
  };

  const planHierarchy = ["starter", "pro", "business", "agency", "cloud", "lifetime"];
  const requiredPlan = featureMap[featureName];

  if (!requiredPlan) {
    return { hasAccess: true, requiredPlan: null };
  }

  const currentPlanIndex = planHierarchy.indexOf(billingStatus.plan);
  const requiredPlanIndex = planHierarchy.indexOf(requiredPlan);

  const hasAccess =
    billingStatus.subscription_status === "active" ||
    billingStatus.subscription_status === "trialing"
      ? currentPlanIndex >= requiredPlanIndex
      : false;

  return { hasAccess, requiredPlan: !hasAccess ? requiredPlan : null };
}
