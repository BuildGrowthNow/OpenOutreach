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
  const displayPrice = isAnnual ? plan.annual_price : plan.monthly_price;
  const savingsPercent = plan.monthly_price > 0 && plan.annual_price > 0
    ? Math.round((1 - plan.annual_price / plan.monthly_price) * 100)
    : 0;

  return (
    <Card
      className={`relative flex flex-col ${
        isCurrentPlan ? "border-blue-500 border-2" : ""
      }`}
    >
      {isCurrentPlan && (
        <Badge className="absolute -top-2 left-4 bg-blue-500">
          Current Plan
        </Badge>
      )}

      <CardHeader>
        <CardTitle>{plan.display_name}</CardTitle>
        <CardDescription>
          {plan.max_linkedin_accounts} LinkedIn{" "}
          {plan.max_linkedin_accounts === 1 ? "account" : "accounts"}
          {plan.max_campaigns && ` • ${plan.max_campaigns} campaigns`}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-6">
        <div>
          <div className="flex items-baseline gap-1">
            <span className="text-4xl font-bold">${displayPrice}</span>
            <span className="text-muted-foreground">/mo</span>
          </div>
          {isAnnual && savingsPercent > 0 && (
            <p className="mt-2 text-sm text-green-600">
              Save {savingsPercent}% billed annually
            </p>
          )}
        </div>

        <ul className="space-y-3 flex-1">
          {plan.features.map((feature) => (
            <li key={feature} className="flex gap-3">
              <Check className="h-5 w-5 flex-shrink-0 text-green-600" />
              <span className="text-sm">{feature}</span>
            </li>
          ))}
        </ul>

        <Button
          onClick={() => {
            const period = plan.name === "lifetime" ? "lifetime" : isAnnual ? "annual" : "monthly";
            onSelectPlan(plan.name, period);
          }}
          disabled={isCurrentPlan || isLoading}
          variant={isCurrentPlan ? "outline" : "default"}
          className="w-full"
        >
          {isCurrentPlan ? "Current Plan" : isLoading ? "Loading..." : "Select Plan"}
        </Button>
      </CardContent>
    </Card>
  );
}
