"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";

interface AccountBlockedOverlayProps {
  userStatus: string;
  adminNotes?: string | null;
  children: React.ReactNode;
}

export function AccountBlockedOverlay({
  userStatus,
  adminNotes,
  children,
}: AccountBlockedOverlayProps) {
  const showOverlay = userStatus === "blocked";

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
              <h2 className="text-2xl font-bold">Account Blocked</h2>
              <p className="text-muted-foreground">
                Your account has been temporarily blocked. This may be due to a violation of our terms of service or suspicious activity.
              </p>
            </div>

            {adminNotes && (
              <div className="bg-red-50 border border-red-200 rounded-md p-4 text-sm text-red-900">
                <p className="font-semibold mb-2">Reason:</p>
                <p>{adminNotes}</p>
              </div>
            )}

            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                For assistance, please contact our support team at{" "}
                <a href="mailto:support@lengrowth.com" className="font-medium text-blue-600 hover:underline">
                  support@lengrowth.com
                </a>
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
