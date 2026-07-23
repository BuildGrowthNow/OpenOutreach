"use client";

import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Clock, X } from "lucide-react";

interface TrialBannerProps {
  trialEndsAt: string | null;
  subscriptionStatus: string;
  onUpgradeClick: () => void;
}

export function TrialBanner({
  trialEndsAt,
  subscriptionStatus,
  onUpgradeClick,
}: TrialBannerProps) {
  const [daysRemaining, setDaysRemaining] = useState<number | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!trialEndsAt || subscriptionStatus !== "trialing") {
      return;
    }

    const updateDaysRemaining = () => {
      const now = new Date();
      const endDate = new Date(trialEndsAt);
      const days = Math.ceil(
        (endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
      );
      setDaysRemaining(Math.max(0, days));
    };

    updateDaysRemaining();
    const interval = setInterval(updateDaysRemaining, 60000); // Update every minute

    return () => clearInterval(interval);
  }, [trialEndsAt, subscriptionStatus]);

  if (!trialEndsAt || subscriptionStatus !== "trialing" || dismissed) {
    return null;
  }

  const isLastDay = daysRemaining === 0 || daysRemaining === 1;
  const isDayOf = daysRemaining === 0;

  return (
    <Alert className={isLastDay ? "bg-red-600 border-red-700" : "bg-emerald-600 border-emerald-700"}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {isDayOf ? (
            <AlertTriangle className="h-5 w-5 text-white mt-0.5" />
          ) : (
            <Clock className="h-5 w-5 text-white mt-0.5" />
          )}
          <div className="space-y-2">
            <AlertDescription className="text-white">
              {isDayOf ? (
                <>
                  <span className="font-semibold">Your trial ends today.</span>{" "}
                  Choose a plan to keep your campaigns running.
                </>
              ) : isLastDay ? (
                <>
                  <span className="font-semibold">Your trial ends tomorrow.</span>{" "}
                  Add a plan to keep your campaigns running.
                </>
              ) : (
                <>
                  <span className="font-semibold">Your trial ends in {daysRemaining} days.</span>{" "}
                  <Button
                    variant="link"
                    size="sm"
                    className="h-auto p-0 ml-2 text-white underline hover:text-white/80"
                    onClick={onUpgradeClick}
                  >
                    Choose a plan
                  </Button>
                </>
              )}
            </AlertDescription>
          </div>
        </div>
        {!isDayOf && (
          <button
            onClick={() => setDismissed(true)}
            className="text-white/70 hover:text-white mt-0.5"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      {(isDayOf || isLastDay) && (
        <div className="mt-3 ml-8">
          <Button onClick={onUpgradeClick} variant="secondary" className="w-full">
            Choose a Plan
          </Button>
        </div>
      )}
    </Alert>
  );
}
