"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/authStoreV2";

export interface ProfileDaemonStatus {
  id: string;
  email: string;
  execution_mode: "desktop" | "cloud";
  is_connected: boolean;
  last_seen: string | null;
  daemon_status: "connected" | "disconnected" | "never_connected";
}

export interface DaemonStatusResponse {
  profiles: ProfileDaemonStatus[];
}

/**
 * Hook to monitor desktop daemon connection status
 * Polls /api/desktop-daemon/status every 30 seconds
 */
export function useDesktopDaemonStatus() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [status, setStatus] = useState<DaemonStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      if (!accessToken) {
        setError("Not authenticated");
        return;
      }

      const response = await fetch("/api/desktop-daemon/status", {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch daemon status: ${response.statusText}`);
      }

      const data: DaemonStatusResponse = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!accessToken) return;

    fetchStatus();

    const interval = setInterval(fetchStatus, 30000);

    return () => clearInterval(interval);
  }, [accessToken]);

  const getProfileStatus = (profileId: string): ProfileDaemonStatus | null => {
    if (!status) return null;
    return status.profiles.find((p) => p.id === profileId) || null;
  };

  const isProfileConnected = (profileId: string): boolean => {
    const profile = getProfileStatus(profileId);
    return profile?.is_connected ?? false;
  };

  const refresh = () => {
    setLoading(true);
    fetchStatus();
  };

  return {
    status,
    loading,
    error,
    getProfileStatus,
    isProfileConnected,
    refresh,
  };
}
