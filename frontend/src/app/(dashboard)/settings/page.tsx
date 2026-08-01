"use client";

import { useCallback, useEffect, useState } from "react";
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
  getDailyUsage,
  getSettings,
  type DailyUsageResponse,
  type Settings,
} from "@/lib/api/dashboard";
import { LinkedInConnectionTab } from "@/components/settings/linkedin-connection-tab";
import RateLimitForm from "@/components/settings/rate-limit-form";
import LlmSettingsForm from "@/components/settings/llm-settings-form";
import ActiveHoursForm from "@/components/settings/active-hours-form";

function SettingsLoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-4 w-80" />
        </div>
        <Skeleton className="h-8 w-24" />
      </div>

      <Skeleton className="h-10 w-full max-w-2xl" />
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
      <Skeleton className="h-96 w-full" />
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [dailyUsage, setDailyUsage] = useState<DailyUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [settingsResponse, dailyUsageResponse] = await Promise.all([
        getSettings(),
        getDailyUsage(),
      ]);

      if (!settingsResponse.data) {
        setError("Failed to load settings");
        return;
      }

      setSettings(settingsResponse.data);
      setDailyUsage(dailyUsageResponse.data ?? null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const handleSettingsUpdate = () => {
    void loadSettings();
  };

  if (loading) {
    return <SettingsLoadingSkeleton />;
  }

  if (error || !settings) {
    return (
      <Alert variant="destructive">
        <Icons.AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Failed to load settings: {error || "Unknown error"}
          <Button variant="outline" className="ml-4" onClick={loadSettings}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const usageTone = {
    normal: "text-green-500",
    caution: "text-yellow-500",
    warning: "text-orange-500",
    exceeded: "text-red-500",
  }[dailyUsage?.rate_limit_status || "normal"];

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Breadcrumb
          items={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Settings', href: '/settings', isActive: true }
          ]}
        />

        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
            <p className="text-muted-foreground">
              Manage your LinkedIn connection, profile defaults, sending limits,
              and LLM behavior in one place.
            </p>
          </div>

          <Button variant="outline" onClick={loadSettings}>
            <Icons.RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>LinkedIn profile</CardDescription>
              <CardTitle className="flex items-center gap-2">
                <Icons.User className="h-4 w-4 text-blue-500" />
                {settings.linkedinProfile?.username
                  ? `@${settings.linkedinProfile.username}`
                  : "Not connected yet"}
              </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Campaign: {settings.linkedinProfile?.campaign || "None yet"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Daily sending profile</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <Icons.Shield className="h-4 w-4 text-blue-500" />
              {(settings.rateLimits?.dailyConnectionLimit ?? 0)} connect /{" "}
              {(settings.rateLimits?.dailyFollowUpLimit ?? 0)} follow-up
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Velocity {(settings.rateLimits?.velocity ?? 0)}/hour
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>LLM configuration</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <Icons.Sparkles className="h-4 w-4 text-blue-500" />
              {settings.llm.apiKey ? (settings.llm.provider || "Custom") : "Lengrowth AI"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="truncate text-sm text-muted-foreground">
              {settings.llm.apiKey
                ? `Model: ${settings.llm.model || "Not configured"}`
                : "Platform default — no setup needed"}
            </p>
            <div className="flex flex-wrap gap-2">
              {settings.llm.writingStyle && (
                <Badge variant="outline">Style</Badge>
              )}
              {settings.llm.sayRules && (
                <Badge variant="outline">Prefer</Badge>
              )}
              {settings.llm.avoidRules && (
                <Badge variant="outline">Avoid</Badge>
              )}
              {!settings.llm.writingStyle &&
                !settings.llm.sayRules &&
                !settings.llm.avoidRules && (
                  <Badge variant="outline">Defaults only</Badge>
                )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="linkedin" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 gap-2 rounded-xl bg-muted p-1 sm:grid-cols-5">
          <TabsTrigger value="linkedin" className="flex items-center gap-2 py-2">
            <Icons.Link className="h-4 w-4 shrink-0" />
            LinkedIn Connection
          </TabsTrigger>
          <TabsTrigger value="rate-limits" className="flex items-center gap-2 py-2">
            <Icons.Shield className="h-4 w-4 shrink-0" />
            Rate Limits
          </TabsTrigger>
          <TabsTrigger value="llm" className="flex items-center gap-2 py-2">
            <Icons.Sparkles className="h-4 w-4 shrink-0" />
            LLM / AI Settings
          </TabsTrigger>
          <TabsTrigger value="active-hours" className="flex items-center gap-2 py-2">
            <Icons.Clock className="h-4 w-4 shrink-0" />
            Active Hours
          </TabsTrigger>
          <TabsTrigger value="billing" className="flex items-center gap-2 py-2">
            <Icons.CreditCard className="h-4 w-4 shrink-0" />
            Billing
          </TabsTrigger>
        </TabsList>

        <TabsContent value="linkedin" className="space-y-6">
          <LinkedInConnectionTab onSetupComplete={handleSettingsUpdate} />
        </TabsContent>

        <TabsContent value="rate-limits" className="space-y-6">
          {dailyUsage && (
            <div className="grid gap-4 lg:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardDescription>Connections sent today</CardDescription>
                  <CardTitle>{dailyUsage.daily_connections_sent}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Base daily limit: {dailyUsage.daily_limit}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardDescription>Effective limit</CardDescription>
                  <CardTitle>{dailyUsage.effective_limit}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Remaining across profiles: {dailyUsage.remaining}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardDescription>Rate limit status</CardDescription>
                  <CardTitle className={usageTone}>
                    {dailyUsage.rate_limit_status}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {dailyUsage.warning_message ||
                      "Daily usage is within the current effective limit."}
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Rate limit settings</CardTitle>
              <CardDescription>
                Control daily volume and pacing to balance throughput with
                account safety.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RateLimitForm
                initialData={settings.rateLimits}
                onSuccess={handleSettingsUpdate}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="llm" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>LLM / AI settings</CardTitle>
              <CardDescription>
                Configure the model provider and fine-tune account-level
                messaging guardrails like what to emphasize, what to avoid, and
                how the AI should sound.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <LlmSettingsForm
                initialData={settings.llm}
                onSuccess={handleSettingsUpdate}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="active-hours" className="space-y-6">
          <ActiveHoursForm settings={settings} onUpdate={handleSettingsUpdate} />
        </TabsContent>

        <TabsContent value="billing" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Billing & Subscription</CardTitle>
              <CardDescription>
                View and manage your subscription plan, invoices, and payment method.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  For detailed billing information, invoices, and subscription management, visit the dedicated billing settings page.
                </p>
                <Button asChild>
                  <a href="/settings/billing">Go to Billing Settings</a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
