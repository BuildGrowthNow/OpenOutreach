"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BillingStatus } from "@/lib/api/billing";
import { format } from "date-fns";

interface BillingStatusCardProps {
  status: BillingStatus;
  planDisplayName: string;
}

export function BillingStatusCard({
  status,
  planDisplayName,
}: BillingStatusCardProps) {
  const getStatusBadge = (subscriptionStatus: string, trialEndsAt?: string | null) => {
    if (subscriptionStatus === "trialing") {
      const daysRemaining = trialEndsAt
        ? Math.ceil(
            (new Date(trialEndsAt).getTime() - new Date().getTime()) /
              (1000 * 60 * 60 * 24)
          )
        : 0;
      return (
        <Badge variant="outline" className="bg-blue-50">
          Trial ({daysRemaining} days left)
        </Badge>
      );
    } else if (subscriptionStatus === "active") {
      return (
        <Badge variant="outline" className="bg-green-50">
          Active
        </Badge>
      );
    } else if (subscriptionStatus === "past_due") {
      return (
        <Badge variant="destructive">
          Payment Failed
        </Badge>
      );
    } else if (subscriptionStatus === "canceled") {
      return (
        <Badge variant="outline" className="bg-gray-50">
          Canceled
        </Badge>
      );
    } else if (subscriptionStatus === "expired") {
      return (
        <Badge variant="destructive">
          Trial Expired
        </Badge>
      );
    }
    return <Badge variant="outline">Unknown</Badge>;
  };

  const nextRenewalDate = status.current_period_end
    ? format(new Date(status.current_period_end), "MMM d, yyyy")
    : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle>{planDisplayName}</CardTitle>
            <CardDescription>Your current subscription</CardDescription>
          </div>
          {getStatusBadge(status.subscription_status, status.trial_ends_at)}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-sm text-muted-foreground">Billing Period</p>
            <p className="font-medium">
              {status.billing_period
                ? status.billing_period.charAt(0).toUpperCase() +
                  status.billing_period.slice(1)
                : "N/A"}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Next Renewal</p>
            <p className="font-medium">
              {nextRenewalDate ? nextRenewalDate : "N/A"}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">LinkedIn Accounts</p>
            <p className="font-medium">{status.linkedin_account_limit}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Campaigns</p>
            <p className="font-medium">
              {status.campaign_limit === null ? "Unlimited" : status.campaign_limit}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
