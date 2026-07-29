"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Icons } from "@/lib/types/components";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Breadcrumb } from "@/components/layout/breadcrumb";
import {
  getBillingStatus,
  getPlans,
  isLifetimeDealActive,
  createCheckoutSession,
  changePlan,
  Plan,
  BillingStatus,
} from "@/lib/api/billing";
import { PlanCard } from "@/components/billing/plan-card";
import { PlanComparison } from "@/components/billing/plan-comparison";

function PlanPageLoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-10 w-full max-w-xs" />
      <div className="grid gap-6 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-96 w-full" />
        ))}
      </div>
    </div>
  );
}

export default function PlanPage() {
  const router = useRouter();
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [lifetimeDealActive, setLifetimeDealActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAnnual, setIsAnnual] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [statusRes, plansRes, dealRes] = await Promise.all([
        getBillingStatus(),
        getPlans(),
        isLifetimeDealActive(),
      ]);

      if (statusRes.data) setBillingStatus(statusRes.data);
      if (plansRes.data) setPlans(plansRes.data.filter((p) => p.name !== "cloud_addon"));
      if (dealRes.data) setLifetimeDealActive(dealRes.data.active);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load plans"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleSelectPlan = async (planName: string, billingPeriod: string) => {
    try {
      setIsProcessing(true);
      setError(null);
      setSelectedPlan(planName);

      if (
        billingStatus?.plan === planName &&
        billingStatus.billing_period === billingPeriod
      ) {
        setError("You are already on this plan");
        setSelectedPlan(null);
        return;
      }

      if (billingStatus?.stripe_subscription_id) {
        await changePlan(planName, billingPeriod);
        setError(null);
        router.push("/settings/billing?success=true");
      } else {
        const checkoutRes = await createCheckoutSession(planName, billingPeriod);
        if (checkoutRes.data?.url) {
          window.location.href = checkoutRes.data.url;
        } else {
          setError("Failed to create checkout session");
        }
      }
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to process plan selection";
      setError(message);
    } finally {
      setIsProcessing(false);
      setSelectedPlan(null);
    }
  };

  if (loading) {
    return <PlanPageLoadingSkeleton />;
  }

  const currentPlan = billingStatus?.plan || "starter";

  // Separate lifetime from regular plans; exclude cloud_addon from display
  const regularPlans = plans.filter((p) => p.name !== "lifetime" && p.name !== "cloud_addon");
  const lifetimePlan = plans.find((p) => p.name === "lifetime");

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Breadcrumb
          items={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Settings", href: "/settings" },
            { label: "Plan", href: "/settings/plan", isActive: true },
          ]}
        />

        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">Choose Your Plan</h1>
          <p className="text-muted-foreground">
            Upgrade or downgrade your plan anytime. Changes take effect immediately for upgrades.
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Billing Frequency</CardTitle>
              <CardDescription>Save 17% when billed annually</CardDescription>
            </div>
            <Tabs
              defaultValue="monthly"
              onValueChange={(v) => setIsAnnual(v === "annual")}
              className="w-auto"
            >
              <TabsList>
                <TabsTrigger value="monthly">Monthly</TabsTrigger>
                <TabsTrigger value="annual">Annual</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-6 lg:grid-cols-4">
        {regularPlans.map((plan) => (
          <PlanCard
            key={plan.name}
            plan={plan}
            isCurrentPlan={currentPlan === plan.name}
            isAnnual={isAnnual}
            isLifetimeDealActive={lifetimeDealActive}
            onSelectPlan={handleSelectPlan}
            isLoading={isProcessing && selectedPlan === plan.name}
          />
        ))}
      </div>

      {/* Lifetime deal — standalone banner */}
      {lifetimeDealActive && lifetimePlan && (
        <Card className={`border-amber-500/50 bg-amber-500/5 ${currentPlan === "lifetime" ? "border-2 border-amber-500" : ""}`}>
          <CardContent className="flex flex-col sm:flex-row items-start sm:items-center gap-6 pt-6">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Icons.Zap className="h-5 w-5 text-amber-500" />
                <span className="font-bold text-lg">Lifetime Pro — $149 once</span>
                {currentPlan === "lifetime" && (
                  <span className="text-xs bg-amber-500 text-white px-2 py-0.5 rounded-full font-semibold">Current Plan</span>
                )}
              </div>
              <p className="text-sm text-muted-foreground mb-3">
                Pay once, use forever. All Pro features included — no monthly fees, ever. Limited spots remaining.
              </p>
              <ul className="flex flex-wrap gap-x-6 gap-y-1">
                {lifetimePlan.features.map((f) => (
                  <li key={f} className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
            <Button
              onClick={() => handleSelectPlan("lifetime", "lifetime")}
              disabled={currentPlan === "lifetime" || isProcessing}
              className="bg-amber-500 hover:bg-amber-400 text-white font-semibold shrink-0"
            >
              {currentPlan === "lifetime" ? "Current Plan" : isProcessing && selectedPlan === "lifetime" ? "Loading..." : "Claim Lifetime Deal"}
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Plan Comparison</CardTitle>
          <CardDescription>
            See all features across plans
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PlanComparison plans={plans} currentPlan={currentPlan} />
        </CardContent>
      </Card>

      <Card className="bg-muted/50">
        <CardHeader>
          <CardTitle className="text-lg">What happens when I change plans?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="font-semibold mb-2">Upgrading</h4>
            <p className="text-sm text-muted-foreground">
              You'll be charged the prorated difference immediately. Your new limits take effect right away.
            </p>
          </div>
          <div>
            <h4 className="font-semibold mb-2">Downgrading</h4>
            <p className="text-sm text-muted-foreground">
              Your plan will change at the end of your current billing period. If you have more LinkedIn accounts or campaigns than your new plan allows, you'll be asked to select which to keep.
            </p>
          </div>
          <div>
            <h4 className="font-semibold mb-2">Annual Plans</h4>
            <p className="text-sm text-muted-foreground">
              Save 17% when you commit to annual billing. You can still cancel anytime.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
