import { useBilling } from "@/lib/contexts/billing-context";

export function useFeatureAccess(featureName: string): { hasAccess: boolean; requiredPlan: string | null } {
  const { billingStatus } = useBilling();

  if (!billingStatus) {
    return { hasAccess: false, requiredPlan: null };
  }

  const featureMap: Record<string, string> = {
    ai_messages: "starter",
    follow_ups: "starter",
    ai_follow_ups: "starter",
    inbox: "starter",
    analytics: "starter",
    priority_support: "business",
    cloud_execution: "cloud",
  };

  const planHierarchy = ["starter", "pro", "lifetime", "business", "agency", "cloud"];
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
