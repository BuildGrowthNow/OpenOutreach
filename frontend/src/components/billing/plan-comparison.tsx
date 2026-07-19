"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Check, X } from "lucide-react";
import { Plan } from "@/lib/api/billing";

interface PlanComparisonProps {
  plans: Plan[];
  currentPlan: string;
}

const featureCategories = [
  {
    name: "Automation",
    features: [
      "AI messages",
      "Automated follow-ups",
      "Voice notes",
    ],
  },
  {
    name: "Data & Tools",
    features: ["Sales Navigator", "Unified inbox", "Analytics"],
  },
  {
    name: "Team & Support",
    features: ["Team members", "Priority support", "White-label"],
  },
];

export function PlanComparison({ plans, currentPlan }: PlanComparisonProps) {
  const hasFeature = (plan: Plan, feature: string): boolean => {
    const featureLower = feature.toLowerCase();
    return plan.features.some((f) => f.toLowerCase().includes(featureLower));
  };

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="min-w-200">Feature</TableHead>
            {plans.map((plan) => (
              <TableHead key={plan.name} className="text-center min-w-32">
                {plan.display_name}
                {plan.name === currentPlan && (
                  <div className="text-xs text-muted-foreground mt-1">
                    Current
                  </div>
                )}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {featureCategories.map((category) => (
            <TableRow key={category.name} className="bg-muted/50">
              <TableCell colSpan={plans.length + 1} className="font-semibold">
                {category.name}
              </TableCell>
            </TableRow>
          ))}
          {featureCategories.map((category) =>
            category.features.map((feature) => (
              <TableRow key={feature}>
                <TableCell>{feature}</TableCell>
                {plans.map((plan) => (
                  <TableCell key={plan.name} className="text-center">
                    {hasFeature(plan, feature) ? (
                      <Check className="h-4 w-4 text-green-600 mx-auto" />
                    ) : (
                      <X className="h-4 w-4 text-gray-300 mx-auto" />
                    )}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
          <TableRow className="bg-muted/50">
            <TableCell className="font-semibold">LinkedIn Accounts</TableCell>
            {plans.map((plan) => (
              <TableCell key={plan.name} className="text-center font-medium">
                {plan.max_linkedin_accounts}
              </TableCell>
            ))}
          </TableRow>
          <TableRow>
            <TableCell className="font-semibold">Campaigns</TableCell>
            {plans.map((plan) => (
              <TableCell key={plan.name} className="text-center font-medium">
                {plan.max_campaigns === null ? "Unlimited" : plan.max_campaigns}
              </TableCell>
            ))}
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
