"use client";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

interface ApproachingLimitBannerProps {
  resourceType: "campaigns" | "linkedin_accounts";
  used: number;
  limit: number;
  onUpgradeClick: () => void;
}

export function ApproachingLimitBanner({
  resourceType,
  used,
  limit,
  onUpgradeClick,
}: ApproachingLimitBannerProps) {
  if (limit === null || used < limit) {
    return null;
  }

  const resourceLabel = resourceType === "campaigns" ? "campaigns" : "LinkedIn accounts";

  return (
    <Alert className="bg-amber-50 border-amber-200">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
          <div className="space-y-2">
            <AlertDescription className="text-amber-800">
              <span className="font-semibold">You've used {used}/{limit} {resourceLabel}.</span> Upgrade for unlimited access.
            </AlertDescription>
          </div>
        </div>
      </div>
      <div className="mt-3 ml-8">
        <Button onClick={onUpgradeClick} className="w-full bg-amber-600 hover:bg-amber-700">
          Upgrade Plan
        </Button>
      </div>
    </Alert>
  );
}
