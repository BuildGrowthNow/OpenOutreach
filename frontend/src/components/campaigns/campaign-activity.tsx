"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Icons } from "@/lib/types/components";
import {
  getCampaignActivity,
  type ActivityEntry,
  type NextTask,
} from "@/lib/api/dashboard";

const TYPE_LABELS: Record<string, string> = {
  connect: "Connection Request",
  check_pending: "Check Pending",
  follow_up: "Follow Up",
  send_manual_message: "Manual Message",
  campaign_paused: "Campaign Paused",
  campaign_started: "Campaign Started",
  lead_discovered: "Lead Discovered",
  lead_qualified: "Lead Qualified",
  lead_disqualified: "Lead Disqualified",
};

function formatActivityDescription(entry: ActivityEntry): string {
  const baseLabel = TYPE_LABELS[entry.type] || entry.type;

  // Use details if available
  if (entry.details) {
    const { lead_name, reason, message_preview, headline } = entry.details;

    switch (entry.type) {
      case "connect":
        return lead_name ? `Sent connection request to ${lead_name}` : baseLabel;

      case "follow_up":
        if (lead_name && message_preview) {
          return `Sent message to ${lead_name}: "${message_preview.substring(0, 50)}..."`;
        }
        return lead_name ? `Sent follow-up to ${lead_name}` : baseLabel;

      case "lead_discovered":
        if (lead_name && headline) {
          return `Discovered ${lead_name} (${headline})`;
        }
        return lead_name ? `Discovered ${lead_name}` : baseLabel;

      case "lead_qualified":
        if (lead_name && reason) {
          return `Qualified ${lead_name}: ${reason}`;
        }
        return lead_name ? `Qualified ${lead_name}` : baseLabel;

      case "lead_disqualified":
        if (lead_name && reason) {
          return `Disqualified ${lead_name}: ${reason}`;
        }
        return lead_name ? `Disqualified ${lead_name}` : baseLabel;

      default:
        return lead_name ? `${baseLabel}: ${lead_name}` : baseLabel;
    }
  }

  return baseLabel;
}

const STATUS_STYLES: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string }> = {
  completed: { variant: "default", label: "Completed" },
  running: { variant: "secondary", label: "Running" },
  failed: { variant: "destructive", label: "Failed" },
  pending: { variant: "outline", label: "Pending" },
};

function formatEta(seconds: number): string {
  if (seconds < 60) return "less than a minute";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function ActivityItem({ entry }: { entry: ActivityEntry }) {
  const style = STATUS_STYLES[entry.status] || STATUS_STYLES.pending;
  const description = formatActivityDescription(entry);

  return (
    <div className="flex items-center justify-between gap-3 py-2.5 px-3 rounded-md hover:bg-zinc-900/50 transition-colors">
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={`h-2 w-2 rounded-full shrink-0 ${
            entry.status === "completed"
              ? "bg-emerald-500"
              : entry.status === "running"
                ? "bg-blue-500 animate-pulse"
                : entry.status === "failed"
                  ? "bg-red-500"
                  : "bg-zinc-500"
          }`}
        />
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-100 truncate">{description}</p>
          {entry.error ? (
            <p className="text-xs text-red-400 truncate">{entry.error}</p>
          ) : (
            <p className="text-xs text-zinc-500">{formatTimestamp(entry.timestamp)}</p>
          )}
        </div>
      </div>
      <Badge variant={style.variant} className="shrink-0 text-xs">
        {style.label}
      </Badge>
    </div>
  );
}

function NextTaskBanner({ task }: { task: NextTask }) {
  const [eta, setEta] = useState(task.etaSeconds);

  useEffect(() => {
    setEta(task.etaSeconds);
    const interval = setInterval(() => {
      setEta((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [task.etaSeconds]);

  const label = TYPE_LABELS[task.taskType] || task.taskType;

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-blue-950/40 border border-blue-900/50">
      <Icons.Clock className="h-3.5 w-3.5 text-blue-400 shrink-0" />
      <span className="text-xs text-blue-200">
        Next: <span className="font-medium">{label}</span> in{" "}
        <span className="font-mono">{formatEta(eta)}</span>
      </span>
    </div>
  );
}

interface CampaignActivityProps {
  campaignId: number | string;
  compact?: boolean;
}

export function CampaignActivity({ campaignId, compact = false }: CampaignActivityProps) {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [nextTask, setNextTask] = useState<NextTask | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const limit = compact ? 10 : 20;

  const initialLoadDone = useRef(false);

  const fetchActivity = useCallback(
    async (pageNum: number, append = false) => {
      if (!initialLoadDone.current && pageNum === 1) setLoading(true);
      if (pageNum > 1) setLoadingMore(true);

      try {
        const resp = await getCampaignActivity(campaignId, pageNum, limit);
        if (resp.data) {
          const newEntries = resp.data.data;
          setEntries((prev) => (append ? [...prev, ...newEntries] : newEntries));
          setNextTask(resp.data.nextTask);
          setPendingCount(resp.data.pendingCount);
          setHasMore(resp.data.pagination.hasMore);
          setPage(pageNum);
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
        initialLoadDone.current = true;
      }
    },
    [campaignId, limit],
  );

  useEffect(() => {
    fetchActivity(1);
    const interval = setInterval(() => fetchActivity(1), 10000);
    return () => clearInterval(interval);
  }, [fetchActivity]);

  if (loading) {
    return (
      <Card className="border-zinc-800/80 bg-zinc-950/50">
        <CardHeader className="pb-3">
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-zinc-800/80 bg-zinc-950/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold text-zinc-100 flex items-center gap-2">
            <Icons.Activity className="h-4 w-4 text-zinc-400" />
            Activity
            {pendingCount > 0 && (
              <Badge variant="secondary" className="text-xs font-normal">
                {pendingCount} scheduled
              </Badge>
            )}
          </CardTitle>
          {compact && (
            <Link href={`/campaigns/${campaignId}/logs`}>
              <Button variant="ghost" size="sm" className="text-xs text-zinc-400 hover:text-zinc-100">
                View all
                <Icons.ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {nextTask && <NextTaskBanner task={nextTask} />}

        <div
          className={`mt-3 divide-y divide-zinc-800/50 ${
            compact ? "max-h-[420px] overflow-y-auto" : ""
          }`}
        >
          {entries.length > 0 ? (
            entries.map((entry) => <ActivityItem key={entry.id} entry={entry} />)
          ) : (
            <div className="text-center py-8">
              <Icons.Clock className="mx-auto h-8 w-8 text-zinc-700" />
              <p className="mt-2 text-sm text-zinc-500">No activity yet</p>
              {nextTask && (
                <p className="mt-1 text-xs text-zinc-600">
                  First task scheduled — waiting to execute
                </p>
              )}
            </div>
          )}
        </div>

        {!compact && hasMore && (
          <div className="mt-4 text-center">
            <Button
              variant="outline"
              size="sm"
              disabled={loadingMore}
              onClick={() => fetchActivity(page + 1, true)}
              className="border-zinc-800 text-zinc-300"
            >
              {loadingMore ? (
                <>
                  <Icons.RefreshCw className="mr-2 h-3 w-3 animate-spin" />
                  Loading...
                </>
              ) : (
                "Load more"
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
