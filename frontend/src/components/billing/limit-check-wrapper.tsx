"use client";

import { ReactNode } from "react";
import { useBilling } from "@/lib/contexts/billing-context";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

interface LimitCheckWrapperProps {
  limitType: "linkedin_accounts" | "campaigns";
  children: ReactNode;
}

export function LimitCheckWrapper({ limitType, children }: LimitCheckWrapperProps) {
  const router = useRouter();
  const { billingStatus, usage } = useBilling();

  if (!billingStatus || !usage) {
    return <>{children}</>;
  }

  const isLinkedInLimit = limitType === "linkedin_accounts";
  const used = isLinkedInLimit ? usage.linkedin_accounts_used : usage.campaigns_used;
  const limit = isLinkedInLimit
    ? billingStatus.linkedin_account_limit
    : billingStatus.campaign_limit;

  if (!limit || used < limit) {
    return <>{children}</>;
  }

  const resourceName = isLinkedInLimit ? "LinkedIn accounts" : "campaigns";

  return (
    <div className="space-y-3">
      <div className="p-4 bg-amber-50 border border-amber-200 rounded-md">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="space-y-2 flex-1">
            <p className="font-semibold text-amber-900">
              You've reached your {resourceName} limit
            </p>
            <p className="text-sm text-amber-800">
              You're using {used}/{limit} {resourceName}. Upgrade your plan for unlimited access.
            </p>
            <Button
              size="sm"
              onClick={() => router.push("/settings/plan")}
              className="mt-2 bg-amber-600 hover:bg-amber-700"
            >
              View Plans
            </Button>
          </div>
        </div>
      </div>
      {children}
    </div>
  );
}
