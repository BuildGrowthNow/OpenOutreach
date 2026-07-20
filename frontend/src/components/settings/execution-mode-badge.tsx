"use client";

import { Monitor, Cloud, Circle } from "lucide-react";
import { useDesktopDaemonStatus } from "@/lib/hooks/use-desktop-daemon-status";

interface ExecutionModeBadgeProps {
  executionMode: "desktop" | "cloud";
  profileId: string;
  showConnectionStatus?: boolean;
}

export function ExecutionModeBadge({
  executionMode,
  profileId,
  showConnectionStatus = true,
}: ExecutionModeBadgeProps) {
  const { getProfileStatus } = useDesktopDaemonStatus();
  const profileStatus = getProfileStatus(profileId);

  const isDesktop = executionMode === "desktop";
  const isConnected = profileStatus?.is_connected ?? false;
  const daemonStatus = profileStatus?.daemon_status ?? "unknown";

  return (
    <div className="flex items-center gap-2">
      {/* Execution Mode Badge */}
      {isDesktop ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/15 px-2.5 py-0.5 text-xs font-medium text-blue-300 border border-blue-500/30">
          <Monitor className="h-3 w-3" />
          Desktop
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-green-500/15 px-2.5 py-0.5 text-xs font-medium text-green-300 border border-green-500/30">
          <Cloud className="h-3 w-3" />
          Cloud
        </span>
      )}

      {/* Connection Status (only for desktop) */}
      {isDesktop && showConnectionStatus && (
        <span className="inline-flex items-center gap-1.5 text-xs">
          {isConnected ? (
            <>
              <Circle className="h-2 w-2 fill-emerald-500 text-emerald-500 animate-pulse" />
              <span className="text-emerald-300 font-medium">Active</span>
            </>
          ) : daemonStatus === "never_connected" ? (
            <>
              <Circle className="h-2 w-2 fill-zinc-500 text-zinc-500" />
              <span className="text-zinc-400">Pending</span>
            </>
          ) : (
            <>
              <Circle className="h-2 w-2 fill-zinc-500 text-zinc-500" />
              <span className="text-zinc-400">Offline</span>
            </>
          )}
        </span>
      )}
    </div>
  );
}

interface LastSeenStatusProps {
  profileId: string;
  executionMode: "desktop" | "cloud";
}

export function LastSeenStatus({ profileId, executionMode }: LastSeenStatusProps) {
  const { getProfileStatus } = useDesktopDaemonStatus();
  const profileStatus = getProfileStatus(profileId);

  if (executionMode !== "desktop" || !profileStatus) {
    return null;
  }

  const { last_seen, is_connected } = profileStatus;

  if (!last_seen) {
    return (
      <div className="text-xs text-zinc-400">
        Waiting for desktop app to connect...
      </div>
    );
  }

  const lastSeenDate = new Date(last_seen);
  const now = new Date();
  const minutesAgo = Math.floor((now.getTime() - lastSeenDate.getTime()) / 60000);

  let timeAgo = "";
  if (minutesAgo < 1) {
    timeAgo = "Just now";
  } else if (minutesAgo < 60) {
    timeAgo = `${minutesAgo} ${minutesAgo === 1 ? "minute" : "minutes"} ago`;
  } else {
    const hoursAgo = Math.floor(minutesAgo / 60);
    timeAgo = `${hoursAgo} ${hoursAgo === 1 ? "hour" : "hours"} ago`;
  }

  return (
    <div className="text-xs text-zinc-400">
      {is_connected ? "Active" : "Last seen"}: {timeAgo}
    </div>
  );
}
