"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Icons } from "@/lib/types/components";
import { getDaemonStatus, type DaemonStatusResponse } from "@/lib/api/dashboard";
import { Monitor, Wifi, WifiOff, Clock, AlertCircle, CheckCircle2, Download } from "lucide-react";

export function DaemonStatusCard() {
  const [status, setStatus] = useState<DaemonStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getDaemonStatus();
      if (response.data) {
        setStatus(response.data);
      } else {
        setError(response.error || "Failed to load daemon status");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load daemon status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    // Refresh every 30 seconds
    const interval = setInterval(loadStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (profileStatus: string) => {
    switch (profileStatus) {
      case "online":
        return "bg-emerald-500";
      case "stale":
        return "bg-amber-500";
      case "offline":
      default:
        return "bg-zinc-500";
    }
  };

  const getStatusLabel = (profileStatus: string) => {
    switch (profileStatus) {
      case "online":
        return "Online";
      case "stale":
        return "Stale";
      case "offline":
      default:
        return "Offline";
    }
  };

  const getStatusIcon = (profileStatus: string) => {
    switch (profileStatus) {
      case "online":
        return <Wifi className="h-4 w-4 text-emerald-500" />;
      case "stale":
        return <Clock className="h-4 w-4 text-amber-500" />;
      case "offline":
      default:
        return <WifiOff className="h-4 w-4 text-zinc-500" />;
    }
  };

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return "Never";
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffSec = Math.floor(diffMs / 1000);
      const diffMin = Math.floor(diffSec / 60);
      const diffHr = Math.floor(diffMin / 60);

      if (diffSec < 60) return `${diffSec}s ago`;
      if (diffMin < 60) return `${diffMin}m ago`;
      if (diffHr < 24) return `${diffHr}h ago`;
      return date.toLocaleDateString();
    } catch {
      return "Unknown";
    }
  };

  if (loading) {
    return (
      <Card className="border-zinc-800/80 bg-zinc-950/40 shadow-none">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Monitor className="h-5 w-5 text-zinc-400" />
            <CardTitle>Desktop Daemon Status</CardTitle>
          </div>
          <CardDescription>
            Checking daemon connection...
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Icons.RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-zinc-800/80 bg-zinc-950/40 shadow-none">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Monitor className="h-5 w-5 text-zinc-400" />
            <CardTitle>Desktop Daemon Status</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <Alert className="border-red-500/50 bg-red-500/10">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <AlertDescription className="text-red-400">
              {error}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!status || !status.has_daemon || status.profiles.length === 0) {
    return (
      <Card className="border-zinc-800/80 bg-zinc-950/40 shadow-none">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Monitor className="h-5 w-5 text-zinc-400" />
            <CardTitle>Desktop Daemon</CardTitle>
          </div>
          <CardDescription>
            Run automation from your computer using your residential IP
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert className="border-zinc-700 bg-zinc-900/50">
            <Download className="h-4 w-4 text-blue-400" />
            <AlertDescription className="text-zinc-300">
              No desktop daemon detected. Download the desktop app to run automation from your own computer and avoid proxy costs.
            </AlertDescription>
          </Alert>
          <Button variant="outline" asChild>
            <a href="https://github.com/your-org/openoutreach/releases" target="_blank" rel="noopener noreferrer">
              <Download className="mr-2 h-4 w-4" />
              Download Desktop App
            </a>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-zinc-800/80 bg-zinc-950/40 shadow-none">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Monitor className="h-5 w-5 text-zinc-400" />
            <CardTitle>Desktop Daemon Status</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={loadStatus}
            className="h-8 w-8 p-0"
          >
            <Icons.RefreshCw className="h-4 w-4" />
          </Button>
        </div>
        <CardDescription>
          Desktop automation running on your local machine
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {status.profiles.map((profile) => (
            <div
              key={profile.profile_id}
              className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 space-y-3">
                  <div className="flex items-center gap-3">
                    {getStatusIcon(profile.status)}
                    <div>
                      <div className="font-medium text-zinc-100">
                        {profile.username || "Profile"}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-zinc-400">
                        <span
                          className={`h-2 w-2 rounded-full ${getStatusColor(profile.status)}`}
                        />
                        <span>{getStatusLabel(profile.status)}</span>
                        {profile.last_seen && (
                          <>
                            <span className="text-zinc-600">•</span>
                            <span>Last seen {formatTimestamp(profile.last_seen)}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {profile.daemon_active && (
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="flex items-center gap-2 text-zinc-400">
                        <span>Version:</span>
                        <span className="text-zinc-300">{profile.version || "Unknown"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-zinc-400">
                        <span>Platform:</span>
                        <span className="text-zinc-300">{profile.platform || "Unknown"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-zinc-400">
                        <span>Browser:</span>
                        <span className="text-zinc-300">{profile.browser || "Unknown"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-zinc-400">
                        <span>LinkedIn:</span>
                        {profile.is_logged_in ? (
                          <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            Logged In
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="border-zinc-500/30 bg-zinc-500/10 text-zinc-400">
                            Not Logged In
                          </Badge>
                        )}
                      </div>
                    </div>
                  )}

                  {profile.requires_verification && (
                    <Alert className="border-amber-500/50 bg-amber-500/10">
                      <AlertCircle className="h-4 w-4 text-amber-500" />
                      <AlertDescription className="text-amber-400">
                        LinkedIn requires verification. Please log in to the web platform to complete the {profile.verification_type || "challenge"}.
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
