"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Icons } from "@/lib/types/components";
import { getLeadSequenceTimeline, type SequenceTimelineEntry } from "@/lib/api/campaigns";

interface LeadSequenceTimelineProps {
  campaignId: string;
  leadId: string;
}

function stepIcon(entry: SequenceTimelineEntry) {
  if (entry.type === "end") return <Icons.CheckCircle className="h-4 w-4" />;
  if (entry.type === "wait") return <Icons.Clock className="h-4 w-4" />;
  if (entry.type === "condition") return <Icons.Workflow className="h-4 w-4" />;
  if (entry.channel === "email") return <Icons.Mail className="h-4 w-4" />;
  if (entry.channel === "whatsapp") return <Icons.Phone className="h-4 w-4" />;
  return <Icons.Network className="h-4 w-4" />;
}

function statusColor(status: SequenceTimelineEntry["status"]) {
  if (status === "completed") return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  if (status === "active") return "text-blue-400 bg-blue-500/10 border-blue-500/30";
  return "text-zinc-500 bg-zinc-800 border-zinc-700";
}

export function LeadSequenceTimeline({ campaignId, leadId }: LeadSequenceTimelineProps) {
  const [timeline, setTimeline] = useState<SequenceTimelineEntry[]>([]);
  const [active, setActive] = useState(false);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getLeadSequenceTimeline(campaignId, leadId)
      .then((res) => {
        if (cancelled) return;
        if (res.error || !res.data) {
          setError(res.error ?? "Failed to load sequence timeline");
          return;
        }
        setTimeline(res.data.timeline);
        setActive(res.data.sequenceActive);
        setDone(res.data.sequenceDone);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load sequence timeline");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [campaignId, leadId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
        <Icons.RefreshCw className="h-3.5 w-3.5 animate-spin" />
        Loading sequence...
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-3 pt-3 border-t">
        <p className="text-xs text-destructive">Could not load sequence timeline: {error}</p>
      </div>
    );
  }

  if (!active || timeline.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t space-y-1">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Sequence Progress
        </span>
        {done && (
          <Badge variant="outline" className="text-xs text-emerald-700 border-emerald-300 bg-emerald-50">
            Done
          </Badge>
        )}
      </div>
      <div className="flex items-start gap-0">
        {timeline.map((entry, i) => (
          <div key={entry.stepId} className="flex flex-col items-center flex-1 min-w-0">
            <div className="flex items-center w-full">
              {i > 0 && (
                <div
                  className={`h-0.5 flex-1 ${
                    entry.status === "completed" || entry.status === "active"
                      ? "bg-emerald-400"
                      : "bg-border"
                  }`}
                />
              )}
              <div
                className={`flex-shrink-0 w-7 h-7 rounded-full border flex items-center justify-center ${statusColor(entry.status)}`}
              >
                {stepIcon(entry)}
              </div>
              {i < timeline.length - 1 && (
                <div
                  className={`h-0.5 flex-1 ${
                    entry.status === "completed" ? "bg-emerald-400" : "bg-border"
                  }`}
                />
              )}
            </div>
            <span className="text-[10px] text-muted-foreground mt-1 text-center truncate w-full px-0.5">
              {entry.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
