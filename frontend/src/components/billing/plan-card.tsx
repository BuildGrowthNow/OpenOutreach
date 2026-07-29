"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check } from "lucide-react";
import { Plan } from "@/lib/api/billing";

interface PlanCardProps {
  plan: Plan;
  isCurrentPlan: boolean;
  isAnnual: boolean;
  isLifetimeDealActive: boolean;
  onSelectPlan: (planName: string, billingPeriod: string) => void;
  isLoading?: boolean;
}

export function PlanCard({
  plan,
  isCurrentPlan,
  isAnnual,
  isLifetimeDealActive,
  onSelectPlan,
  isLoading = false,
}: PlanCardProps) {
  const isLifetime = plan.name === "lifetime";
  const isCloud = plan.name === "cloud";

  // Lifetime: one-time $149. Cloud: always monthly $299. Others: monthly or annual.
  const getDisplayPrice = () => {
    if (isLifetime) return { amount: Math.round(plan.annual_price / 100), suffix: " one-time" };
    if (isCloud) return { amount: Math.round(plan.monthly_price / 100), suffix: "/mo" };
    const amount = isAnnual
      ? Math.round(plan.annual_price / 100 / 12)
      : Math.round(plan.monthly_price / 100);
    return { amount, suffix: isAnnual ? "/mo, billed annually" : "/mo" };
  };

  const savingsPercent =
    !isLifetime && !isCloud && plan.monthly_price > 0 && plan.annual_price > 0
      ? Math.round((1 - plan.annual_price / (plan.monthly_price * 12)) * 100)
      : 0;

  const { amount, suffix } = getDisplayPrice();

  const handleSelect = () => {
    const period = isLifetime ? "lifetime" : isAnnual ? "annual" : "monthly";
    onSelectPlan(plan.name, period);
  };

  return (
    <Card className={`relative flex flex-col ${isCurrentPlan ? "border-emerald-500 border-2" : ""}`}>
      {isCurrentPlan && (
        <Badge className="absolute -top-2 left-4 bg-emerald-600">Current Plan</Badge>
      )}

      <CardHeader>
        <CardTitle>{plan.display_name}</CardTitle>
        <CardDescription>
          {plan.max_linkedin_accounts > 0
            ? `${plan.max_linkedin_accounts} LinkedIn ${plan.max_linkedin_accounts === 1 ? "account" : "accounts"}`
            : "Cloud managed"}
          {plan.max_campaigns ? ` · ${plan.max_campaigns} campaigns` : plan.max_campaigns === null && plan.max_linkedin_accounts > 0 ? " · Unlimited campaigns" : ""}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-6">
        <div>
          <div className="flex items-baseline gap-1">
            <span className="text-4xl font-bold">${amount}</span>
            <span className="text-muted-foreground text-sm">{suffix}</span>
          </div>
          {isAnnual && savingsPercent > 0 && (
            <p className="mt-1 text-sm text-emerald-500">Save {savingsPercent}% vs monthly</p>
          )}
        </div>

        <ul className="space-y-3 flex-1">
          {plan.features.map((feature) => (
            <li key={feature} className="flex gap-3">
              <Check className="h-5 w-5 flex-shrink-0 text-emerald-500" />
              <span className="text-sm">{feature}</span>
            </li>
          ))}
        </ul>

        <Button
          onClick={handleSelect}
          disabled={isCurrentPlan || isLoading}
          variant={isCurrentPlan ? "outline" : "default"}
          className="w-full"
        >
          {isCurrentPlan ? "Current Plan" : isLoading ? "Loading..." : isLifetime ? "Buy Once" : "Select Plan"}
        </Button>
      </CardContent>
    </Card>
  );
}
