"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Breadcrumb } from "@/components/layout/breadcrumb";
import { Icons } from "@/lib/types/components";
import {
  getBillingStatus,
  getInvoices,
  getPlans,
  getUsage,
  isLifetimeDealActive,
  createPortalSession,
  updateCloudAddon,
  Invoice,
  Plan,
  BillingStatus,
} from "@/lib/api/billing";
import { BillingStatusCard } from "@/components/billing/billing-status";
import { TrialBanner } from "@/components/billing/trial-banner";
import { UsageIndicator } from "@/components/billing/usage-indicator";
import { useBilling } from "@/lib/contexts/billing-context";
import { Input } from "@/components/ui/input";
import { Minus, Plus } from "lucide-react";
import { format } from "date-fns";

function BillingLoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-96 w-full" />
    </div>
  );
}

export default function BillingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [usage, setUsage] = useState<{ linkedin_accounts_used: number; campaigns_used: number }>({ linkedin_accounts_used: 0, campaigns_used: 0 });
  const [lifetimeDealActive, setLifetimeDealActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isPortalLoading, setIsPortalLoading] = useState(false);
  const [seatQuantity, setSeatQuantity] = useState(0);
  const [isSeatLoading, setIsSeatLoading] = useState(false);
  const [seatError, setSeatError] = useState<string | null>(null);
  const { refetch: refetchBilling } = useBilling();
  const isBillingOwner = billingStatus?.is_billing_owner !== false;

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [statusRes, plansRes, invoicesRes, dealRes, usageRes] = await Promise.all([
        getBillingStatus(),
        getPlans(),
        getInvoices(),
        isLifetimeDealActive(),
        getUsage(),
      ]);

      if (statusRes.data) setBillingStatus(statusRes.data);
      if (statusRes.data) setSeatQuantity(statusRes.data.cloud_profiles ?? 0);
      if (plansRes.data) setPlans(plansRes.data);
      if (invoicesRes.data) setInvoices(invoicesRes.data);
      if (dealRes.data) setLifetimeDealActive(dealRes.data.active);
      if (usageRes.data) setUsage(usageRes.data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load billing information"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();

    const success = searchParams.get("success");
    const canceled = searchParams.get("canceled");

    if (success === "true") {
      setSuccessMessage("Subscription updated successfully!");
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
    if (canceled === "true") {
      setError("Checkout was canceled.");
    }
  }, [loadData, searchParams]);

  const handleManageSubscription = async () => {
    try {
      setIsPortalLoading(true);
      const res = await createPortalSession();
      if (res.data?.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      setError("Failed to open billing portal");
    } finally {
      setIsPortalLoading(false);
    }
  };

  const handleUpgradeClick = () => {
    router.push("/settings/plan");
  };

  const handleUpdateSeats = async () => {
    if (!billingStatus) return;
    if (seatQuantity === billingStatus.cloud_profiles) return;
    if (seatQuantity < billingStatus.cloud_profiles) {
      const confirmed = window.confirm(
        "Removing cloud seats pauses any LinkedIn accounts above the new limit. Continue?"
      );
      if (!confirmed) return;
    }
    try {
      setIsSeatLoading(true);
      setSeatError(null);
      const response = await updateCloudAddon(seatQuantity);
      if (response.error) {
        throw new Error(response.error);
      }
      await loadData();
      await refetchBilling();
      setSuccessMessage("Cloud seats updated.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      setSeatError(
        err instanceof Error ? err.message : "Failed to update cloud seats"
      );
    } finally {
      setIsSeatLoading(false);
    }
  };

  if (loading) {
    return <BillingLoadingSkeleton />;
  }

  const currentPlan = plans.find((p) => p.name === billingStatus?.plan);

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Breadcrumb
          items={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Settings", href: "/settings" },
            { label: "Billing", href: "/settings/billing", isActive: true },
          ]}
        />

        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight">Billing</h1>
            <p className="text-muted-foreground">
              Manage your subscription, view invoices, and update your payment method.
            </p>
          </div>

          <Button variant="outline" onClick={loadData} disabled={loading}>
            <Icons.RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {successMessage && (
        <Alert className="bg-green-50 border-green-200">
          <Icons.CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            {successMessage}
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {billingStatus?.subscription_status === "trialing" && (
        <TrialBanner
          trialEndsAt={billingStatus.trial_ends_at}
          subscriptionStatus={billingStatus.subscription_status}
          onUpgradeClick={handleUpgradeClick}
        />
      )}

      {billingStatus && currentPlan && (
        <BillingStatusCard status={billingStatus} planDisplayName={currentPlan.display_name} />
      )}

      {billingStatus && !isBillingOwner && (
        <Alert>
          <Icons.Info className="h-4 w-4" />
          <AlertDescription>
            Your workspace owner ({billingStatus.billing_owner_email || "the owner"}) manages billing.
            You inherit the workspace plan and seat pool.
          </AlertDescription>
        </Alert>
      )}

      {isBillingOwner && (
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Manage your subscription and payment method</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 sm:flex-row">
            <Button onClick={handleUpgradeClick} variant="default" className="flex-1">
              Change Plan
            </Button>
            <Button
              onClick={handleManageSubscription}
              variant="outline"
              className="flex-1"
              disabled={isPortalLoading}
            >
              {isPortalLoading ? "Opening..." : "Manage Subscription"}
            </Button>
          </CardContent>
        </Card>
      )}

      {billingStatus && (
        <Card>
          <CardHeader>
            <CardTitle>Plan Limits</CardTitle>
            <CardDescription>Your current usage</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <UsageIndicator
              label="LinkedIn Accounts"
              used={usage.linkedin_accounts_used}
              limit={billingStatus.linkedin_account_limit}
            />
            <UsageIndicator
              label="Campaigns"
              used={usage.campaigns_used}
              limit={billingStatus.campaign_limit}
            />
          </CardContent>
        </Card>
      )}

      {isBillingOwner && billingStatus?.plan === "cloud" && billingStatus.cloud_seats_enabled && (
        <Card>
          <CardHeader>
            <CardTitle>Cloud seats</CardTitle>
            <CardDescription>
              Your Cloud plan includes 1 LinkedIn account and 1 managed proxy.
              Add extra cloud seats to run more accounts on managed infrastructure.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="text-sm text-muted-foreground">
                {billingStatus.cloud_seat_limit} cloud seat
                {billingStatus.cloud_seat_limit === 1 ? "" : "s"} total
                {" · "}
                {billingStatus.cloud_profiles} extra
              </div>
              <div className="ml-auto flex items-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setSeatQuantity((value) => Math.max(0, value - 1))}
                  disabled={isSeatLoading || seatQuantity <= 0}
                  aria-label="Remove a cloud seat"
                >
                  <Minus className="h-4 w-4" />
                </Button>
                <Input
                  type="number"
                  min={0}
                  value={seatQuantity}
                  onChange={(event) =>
                    setSeatQuantity(Math.max(0, Number(event.target.value) || 0))
                  }
                  className="w-20 text-center"
                  aria-label="Extra cloud seats"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setSeatQuantity((value) => value + 1)}
                  disabled={isSeatLoading}
                  aria-label="Add a cloud seat"
                >
                  <Plus className="h-4 w-4" />
                </Button>
                <Button
                  onClick={handleUpdateSeats}
                  disabled={
                    isSeatLoading || seatQuantity === billingStatus.cloud_profiles
                  }
                >
                  {isSeatLoading ? "Updating..." : "Update seats"}
                </Button>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Each extra seat is $299/mo and adds one LinkedIn account plus one
              managed proxy. Removing a seat pauses accounts above the new limit.
            </p>
            {seatError && (
              <Alert variant="destructive">
                <Icons.AlertCircle className="h-4 w-4" />
                <AlertDescription>{seatError}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {billingStatus?.team_workspaces_enabled && (
        <Card>
          <CardHeader>
            <CardTitle>Desktop seats</CardTitle>
            <CardDescription>
              Desktop seats are included in team plans. They run on the
              member&apos;s computer with the local IP, use no proxy, and do not
              consume a cloud seat.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Member logins are included during rollout. A login alone does not
              include a browser account, proxy, or email slot.
            </p>
          </CardContent>
        </Card>
      )}

      {isBillingOwner && (
        <Card>
          <CardHeader>
            <CardTitle>Invoices</CardTitle>
            <CardDescription>Your billing history</CardDescription>
          </CardHeader>
          <CardContent>
            {invoices.length === 0 ? (
              <p className="text-sm text-muted-foreground">No invoices yet</p>
            ) : (
              <div className="space-y-4">
                {invoices.map((invoice) => (
                  <div
                    key={invoice.id}
                    className="flex items-center justify-between border-b pb-4 last:border-0"
                  >
                    <div>
                      <p className="font-medium">
                        {invoice.number || `Invoice ${invoice.id.slice(0, 8)}`}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {format(new Date(invoice.created * 1000), "MMM d, yyyy")}
                      </p>
                    </div>
                    <div className="flex items-center gap-4">
                      <Badge
                        variant={invoice.paid ? "outline" : "secondary"}
                        className={invoice.paid ? "bg-green-50" : ""}
                      >
                        {invoice.status}
                      </Badge>
                      <div className="text-right">
                        <p className="font-medium">
                          ${(invoice.amount_paid / 100).toFixed(2)}
                        </p>
                        {invoice.pdf_url && (
                          <a
                            href={invoice.pdf_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline"
                          >
                            Download PDF
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
