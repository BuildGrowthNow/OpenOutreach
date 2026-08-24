"use client";

import { ReactNode, ButtonHTMLAttributes } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Lock } from "lucide-react";
import { useRouter } from "next/navigation";
import { usePlanLimit, LimitResource } from "@/lib/hooks/use-plan-limit";

interface PlanLimitButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  resource: LimitResource;
  children: ReactNode;
  variant?: "default" | "outline" | "secondary" | "ghost" | "link" | "destructive";
}

export function PlanLimitButton({
  resource,
  children,
  onClick,
  disabled,
  variant,
  ...props
}: PlanLimitButtonProps) {
  const router = useRouter();
  const { atLimit, used, limit, subscriptionActive } = usePlanLimit(resource);

  const isBlocked = atLimit || !subscriptionActive;

  if (!isBlocked) {
    return (
      <Button variant={variant} onClick={onClick} disabled={disabled} {...props}>
        {children}
      </Button>
    );
  }

  const tooltipText = !subscriptionActive
    ? "An active subscription is required. Click to choose a plan."
    : `You've used ${used}/${limit} ${resource === "campaigns" ? "campaigns" : resource === "whatsapp_accounts" ? "WhatsApp accounts" : "LinkedIn accounts"}. Upgrade to add more.`;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            disabled={false}
            className="opacity-60 cursor-pointer"
            onClick={() => router.push("/settings/plan")}
            {...props}
          >
            <Lock className="mr-2 h-4 w-4" />
            {children}
            <Badge variant="secondary" className="ml-2 text-xs">
              Upgrade
            </Badge>
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
