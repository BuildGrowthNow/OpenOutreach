"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";

interface TrialExpiredOverlayProps {
  subscriptionStatus: string;
  onChoosePlan: () => void;
  children: React.ReactNode;
}

export function TrialExpiredOverlay({
  subscriptionStatus,
  onChoosePlan,
  children,
}: TrialExpiredOverlayProps) {
  const showOverlay = subscriptionStatus === "expired";

  if (!showOverlay) {
    return <>{children}</>;
  }

  return (
    <div className="relative h-screen w-full bg-background">
      {/* Blurred background content */}
      <div className="absolute inset-0 blur-sm opacity-50 pointer-events-none overflow-hidden">
        {children}
      </div>

      {/* Overlay */}
      <div className="absolute inset-0 bg-black/40 flex items-center justify-center z-50">
        <Card className="w-full max-w-md mx-4 p-8 bg-background border-2 border-red-200">
          <div className="space-y-6 text-center">
            <div className="flex justify-center">
              <AlertTriangle className="h-16 w-16 text-red-600" />
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl font-bold">Trial Ended</h2>
              <p className="text-muted-foreground">
                Your free trial has ended. To continue using Lengrowth and keep your campaigns running, please choose a plan.
              </p>
            </div>

            <div className="space-y-3">
              <Button
                onClick={onChoosePlan}
                size="lg"
                className="w-full bg-blue-600 hover:bg-blue-700"
              >
                Choose a Plan
              </Button>
              <p className="text-xs text-muted-foreground">
                All your data will be preserved when you subscribe.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
