"use client";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

interface ApproachingLimitBannerProps {
  resourceType: "campaigns" | "linkedin_accounts" | "whatsapp_accounts";
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
  // Show "approaching" warning at 80%+, but only show "at limit" when strictly over —
  // being at exactly the plan limit (e.g. 1/1) is normal operation, not a warning state.
  if (limit === null || limit === 0 || used < limit * 0.8 || used === limit) {
    return null;
  }

  const resourceLabel =
    resourceType === "campaigns"
      ? "campaigns"
      : resourceType === "whatsapp_accounts"
      ? "WhatsApp accounts"
      : "LinkedIn accounts";
  const atLimit = used > limit;

  return (
    <Alert className={atLimit ? "bg-red-50 border-red-200" : "bg-amber-50 border-amber-200"}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className={`h-5 w-5 mt-0.5 ${atLimit ? "text-red-600" : "text-amber-600"}`} />
          <AlertDescription className={atLimit ? "text-red-800" : "text-amber-800"}>
            {atLimit
              ? <><span className="font-semibold">You've reached your {resourceLabel} limit ({used}/{limit}).</span> Upgrade to add more.</>
              : <><span className="font-semibold">Approaching your {resourceLabel} limit ({used}/{limit}).</span> Upgrade before you run out.</>
            }
          </AlertDescription>
        </div>
      </div>
      <div className="mt-3 ml-8">
        <Button
          onClick={onUpgradeClick}
          className={`w-full ${atLimit ? "bg-red-600 hover:bg-red-700" : "bg-amber-600 hover:bg-amber-700"}`}
        >
          Upgrade Plan
        </Button>
      </div>
    </Alert>
  );
}
