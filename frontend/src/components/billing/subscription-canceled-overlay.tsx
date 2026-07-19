"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { format, addDays } from "date-fns";
import { AlertTriangle } from "lucide-react";

interface SubscriptionCanceledOverlayProps {
  subscriptionStatus: string;
  currentPeriodEnd: string | null;
  onReactivate: () => void;
  children: React.ReactNode;
}

export function SubscriptionCanceledOverlay({
  subscriptionStatus,
  currentPeriodEnd,
  onReactivate,
  children,
}: SubscriptionCanceledOverlayProps) {
  const showOverlay = subscriptionStatus === "canceled" && currentPeriodEnd && new Date(currentPeriodEnd) <= new Date();
  const gracePeriodEnd = currentPeriodEnd ? addDays(new Date(currentPeriodEnd), 30) : null;
  const daysRemaining = gracePeriodEnd
    ? Math.ceil((gracePeriodEnd.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24))
    : 0;
  const isExpired = daysRemaining <= 0;

  if (!showOverlay) {
    return <>{children}</>;
  }

  return (
    <div className="relative h-screen w-full bg-background">
      {/* Read-only background content with notice */}
      <div className="absolute inset-0 blur-sm opacity-50 pointer-events-none overflow-hidden">
        {children}
      </div>

      {/* Overlay */}
      <div className="absolute inset-0 bg-black/40 flex items-center justify-center z-50">
        <Card className="w-full max-w-md mx-4 p-8 bg-background border-2 border-orange-200">
          <div className="space-y-6 text-center">
            <div className="flex justify-center">
              <AlertTriangle className="h-16 w-16 text-orange-600" />
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl font-bold">Subscription Canceled</h2>
              <p className="text-muted-foreground">
                Your subscription has been canceled. You can still access your data for a limited time.
              </p>
            </div>

            {!isExpired && gracePeriodEnd && (
              <div className="bg-orange-50 border border-orange-200 rounded-md p-4 text-sm text-orange-900">
                <p className="font-semibold mb-1">Grace Period</p>
                <p>Data will be permanently deleted on {format(gracePeriodEnd, "MMM d, yyyy")}</p>
                <p className="text-xs mt-2">({daysRemaining} days remaining)</p>
              </div>
            )}

            <div className="space-y-3">
              <Button
                onClick={onReactivate}
                size="lg"
                className="w-full bg-blue-600 hover:bg-blue-700"
              >
                Reactivate Subscription
              </Button>
              <p className="text-xs text-muted-foreground">
                All your campaigns and data will be restored.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
