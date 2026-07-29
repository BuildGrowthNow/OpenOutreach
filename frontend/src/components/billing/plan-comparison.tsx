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
import { Fragment } from "react";
import { Plan } from "@/lib/api/billing";

interface PlanComparisonProps {
  plans: Plan[];
  currentPlan: string;
}

type PlanKey = "starter" | "pro" | "business" | "agency" | "cloud" | "lifetime";

interface FeatureRow {
  name: string;
  plans: Partial<Record<PlanKey, boolean>>;
}

interface FeatureCategory {
  name: string;
  rows: FeatureRow[];
}

const CATEGORIES: FeatureCategory[] = [
  {
    name: "Outreach",
    rows: [
      { name: "AI-written messages", plans: { starter: true, pro: true, business: true, agency: true, cloud: true, lifetime: true } },
      { name: "Automated follow-ups", plans: { starter: true, pro: true, business: true, agency: true, cloud: true, lifetime: true } },
      { name: "AI follow-up sequences", plans: { starter: false, pro: true, business: true, agency: true, cloud: true, lifetime: true } },
      { name: "Unified inbox", plans: { starter: true, pro: true, business: true, agency: true, cloud: true, lifetime: true } },
    ],
  },
  {
    name: "Campaigns",
    rows: [
      { name: "Active campaigns", plans: { starter: true, pro: true, business: true, agency: true, cloud: true, lifetime: true } },
      { name: "Analytics dashboard", plans: { starter: true, pro: true, business: true, agency: true, cloud: true, lifetime: true } },
    ],
  },
  {
    name: "Cloud",
    rows: [
      { name: "Managed cloud execution", plans: { starter: false, pro: false, business: false, agency: false, cloud: true, lifetime: false } },
      { name: "Priority support", plans: { starter: false, pro: false, business: true, agency: true, cloud: true, lifetime: false } },
    ],
  },
];

const PLAN_ORDER: PlanKey[] = ["starter", "pro", "business", "agency", "lifetime", "cloud"];

export function PlanComparison({ plans, currentPlan }: PlanComparisonProps) {
  const orderedPlans = PLAN_ORDER
    .map((key) => plans.find((p) => p.name === key))
    .filter((p): p is Plan => !!p);

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="min-w-[200px]">Feature</TableHead>
            {orderedPlans.map((plan) => (
              <TableHead key={plan.name} className="text-center min-w-[100px]">
                <span className={plan.name === "cloud" ? "text-sky-400" : plan.name === "pro" ? "text-emerald-400" : ""}>
                  {plan.display_name}
                </span>
                {plan.name === currentPlan && (
                  <div className="text-xs text-muted-foreground mt-1">Current</div>
                )}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {/* LinkedIn accounts row */}
          <TableRow className="bg-muted/50">
            <TableCell className="font-semibold">LinkedIn Accounts</TableCell>
            {orderedPlans.map((plan) => (
              <TableCell key={plan.name} className="text-center font-medium">
                {plan.max_linkedin_accounts === 0 ? "1 (managed)" : plan.max_linkedin_accounts}
              </TableCell>
            ))}
          </TableRow>
          {/* Campaigns row */}
          <TableRow>
            <TableCell className="font-semibold">Campaigns</TableCell>
            {orderedPlans.map((plan) => (
              <TableCell key={plan.name} className="text-center font-medium">
                {plan.max_campaigns === null ? "Unlimited" : plan.max_campaigns}
              </TableCell>
            ))}
          </TableRow>

          {CATEGORIES.map((category) => (
            <Fragment key={category.name}>
              <TableRow className="bg-muted/50">
                <TableCell colSpan={orderedPlans.length + 1} className="font-semibold text-muted-foreground text-xs uppercase tracking-wide">
                  {category.name}
                </TableCell>
              </TableRow>
              {category.rows.map((row) => (
                <TableRow key={row.name}>
                  <TableCell>{row.name}</TableCell>
                  {orderedPlans.map((plan) => {
                    const has = row.plans[plan.name as PlanKey] ?? false;
                    return (
                      <TableCell key={plan.name} className="text-center">
                        {has ? (
                          <Check className={`h-4 w-4 mx-auto ${plan.name === "cloud" ? "text-sky-400" : "text-emerald-500"}`} />
                        ) : (
                          <X className="h-4 w-4 text-zinc-700 mx-auto" />
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
