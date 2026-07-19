"use client";

import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { AlertCircle } from "lucide-react";

interface UsageIndicatorProps {
  label: string;
  used: number;
  limit: number | null;
}

export function UsageIndicator({ label, used, limit }: UsageIndicatorProps) {
  if (limit === null) {
    return (
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{label}</span>
        <Badge variant="secondary">Unlimited</Badge>
      </div>
    );
  }

  const percentage = (used / limit) * 100;
  const isAtLimit = percentage >= 100;
  const isNearLimit = percentage >= 80;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-sm">
          {used}/{limit}
        </span>
      </div>
      <div className="flex gap-2 items-center">
        <Progress
          value={Math.min(percentage, 100)}
          className={`flex-1 ${
            isAtLimit ? "bg-red-100" : isNearLimit ? "bg-yellow-100" : ""
          }`}
        />
        {isAtLimit && (
          <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
        )}
        {isNearLimit && !isAtLimit && (
          <AlertCircle className="h-4 w-4 text-yellow-600 flex-shrink-0" />
        )}
      </div>
      {isAtLimit && (
        <p className="text-xs text-red-600">You've reached your plan limit</p>
      )}
      {isNearLimit && !isAtLimit && (
        <p className="text-xs text-yellow-600">
          {limit - used} {limit - used === 1 ? "slot" : "slots"} remaining
        </p>
      )}
    </div>
  );
}
