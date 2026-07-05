"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Icons } from "@/lib/types/components";
import { getSettings, type Settings } from "@/lib/api/dashboard";
import { LinkedInConnectionTab } from "@/components/settings/linkedin-connection-tab";
import { useToast } from "@/components/ui/use-toast";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      const response = await getSettings();
      if (response.data) {
        setSettings(response.data);
      } else {
        setError("Failed to load settings");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await loadSettings();
    })();
  }, [loadSettings]);

  const handleSettingsUpdate = () => {
    loadSettings();
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="grid gap-6">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <Icons.AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Failed to load settings: {error}
          <Button variant="outline" className="ml-4" onClick={loadSettings}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Configure system settings, rate limits, and your profile
        </p>
      </div>
      <Button variant="outline" onClick={loadSettings}>
        <Icons.RefreshCw className="h-4 w-4 mr-2" />
        Refresh
      </Button>

      <LinkedInConnectionTab onSetupComplete={handleSettingsUpdate} />
    </div>
  );
}
