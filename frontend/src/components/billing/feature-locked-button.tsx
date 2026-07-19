"use client";

import { ReactNode, ButtonHTMLAttributes } from "react";
import { Button } from "@/components/ui/button";
import { useFeatureAccess } from "@/lib/hooks/use-feature-access";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Lock } from "lucide-react";
import { useRouter } from "next/navigation";

interface FeatureLockedButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  featureName: string;
  children: ReactNode;
}

export function FeatureLockedButton({
  featureName,
  children,
  onClick,
  disabled,
  ...props
}: FeatureLockedButtonProps) {
  const router = useRouter();
  const { hasAccess, requiredPlan } = useFeatureAccess(featureName);

  if (hasAccess) {
    return (
      <Button onClick={onClick} disabled={disabled} {...props}>
        {children}
      </Button>
    );
  }

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    router.push("/settings/plan");
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            onClick={handleClick}
            disabled={true}
            variant="outline"
            className="relative opacity-50"
            {...props}
          >
            <Lock className="mr-2 h-4 w-4" />
            {children}
            {requiredPlan && (
              <Badge variant="secondary" className="ml-2">
                {requiredPlan.charAt(0).toUpperCase() + requiredPlan.slice(1)}
              </Badge>
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>
            This feature is available on {requiredPlan || "a higher"} plan.{" "}
            <span className="font-semibold">Click to upgrade</span>
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
