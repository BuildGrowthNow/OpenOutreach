"use client";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

interface PastDueBannerProps {
  subscriptionStatus: string;
  onManageClick: () => void;
}

export function PastDueBanner({
  subscriptionStatus,
  onManageClick,
}: PastDueBannerProps) {
  if (subscriptionStatus !== "past_due") {
    return null;
  }

  return (
    <Alert className="bg-red-50 border-red-200">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5" />
          <div className="space-y-2">
            <AlertDescription className="text-red-800">
              <span className="font-semibold">Payment failed.</span> Update your payment method to avoid service interruption.
            </AlertDescription>
          </div>
        </div>
      </div>
      <div className="mt-3 ml-8">
        <Button onClick={onManageClick} className="w-full bg-red-600 hover:bg-red-700">
          Update Payment Method
        </Button>
      </div>
    </Alert>
  );
}
