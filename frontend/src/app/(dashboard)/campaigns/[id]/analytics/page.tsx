"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Icons } from "@/lib/types/components";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
  Legend,
} from "recharts";
import { getCampaignAnalytics } from "@/lib/api/dashboard";

const PIPELINE_COLORS: Record<string, string> = {
  qualified: "#3b82f6",
  ready_to_connect: "#6366f1",
  pending: "#a855f7",
  connected: "#06b6d4",
  completed: "#10b981",
  failed: "#ef4444",
  no_email: "#9ca3af",
};

const PIPELINE_LABELS: Record<string, string> = {
  qualified: "Qualified",
  ready_to_connect: "Ready to Connect",
  pending: "Pending",
  connected: "Connected",
  completed: "Converted",
  failed: "Failed",
  no_email: "No Email",
};

interface Stats {
  connections_sent: number;
  connections_accepted: number;
  connection_accept_rate: number;
  messages_sent: number;
  messages_replied: number;
  response_rate: number;
  conversions: number;
  conversion_rate: number;
  errors: number;
}

interface ChannelStats {
  messages_sent: number;
  messages_replied: number;
  response_rate: number;
}

interface AnalyticsData {
  stats: Stats;
  pipeline?: Record<string, number>;
  channels?: {
    linkedin?: ChannelStats;
    whatsapp?: ChannelStats;
  };
}

function KpiCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card>
      <CardContent className="pt-6 text-center">
        <div className="text-3xl font-bold">{value}</div>
        <div className="text-sm text-muted-foreground mt-1">{label}</div>
        {sub && <div className="text-xs text-muted-foreground mt-0.5">{sub}</div>}
      </CardContent>
    </Card>
  );
}

function RateBadge({ value, label, sublabel }: { value: number; label: string; sublabel?: string }) {
  const color =
    value >= 30
      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
      : value >= 15
      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
      : "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <span className="text-sm">{label}</span>
        {sublabel && <div className="text-xs text-muted-foreground">{sublabel}</div>}
      </div>
      <Badge variant="outline" className={color}>
        {value.toFixed(1)}%
      </Badge>
    </div>
  );
}

export default function CampaignAnalyticsPage() {
  const params = useParams();
  const router = useRouter();
  const campaignId = params.id as string;

  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState("30d");

  const fetchAnalytics = useCallback(async (p: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await getCampaignAnalytics(campaignId, p);
      if (response.data) {
        setAnalytics(response.data);
      } else {
        setError(response.error || response.message || "Failed to load analytics");
      }
    } catch {
      setError("Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    void fetchAnalytics(period);
  }, [fetchAnalytics, period]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-56" />
          <div className="flex gap-2">
            <Skeleton className="h-9 w-32" />
            <Skeleton className="h-9 w-28" />
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error || "No analytics data available."}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => router.push(`/campaigns/${campaignId}`)}>
          Back to Campaign
        </Button>
      </div>
    );
  }

  const s = analytics.stats;

  const funnelData = [
    { name: "Sent", value: s.connections_sent, fill: "#6366f1" },
    { name: "Accepted", value: s.connections_accepted, fill: "#06b6d4" },
    { name: "Messaged", value: s.messages_sent, fill: "#3b82f6" },
    { name: "Replied", value: s.messages_replied, fill: "#a855f7" },
    { name: "Converted", value: s.conversions, fill: "#10b981" },
  ];

  const pipelineData = analytics.pipeline
    ? Object.entries(analytics.pipeline)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({
          name: PIPELINE_LABELS[k] || k,
          value: v,
          fill: PIPELINE_COLORS[k] || "#71717a",
        }))
    : [];

  const totalPipeline = pipelineData.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Campaign Analytics</h1>
          <p className="text-muted-foreground">Performance metrics for this campaign</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={period} onValueChange={(v) => { if (v) setPeriod(v); }}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
              <SelectItem value="all">All time</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void fetchAnalytics(period)}
            disabled={loading}
          >
            <Icons.RefreshCw className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/campaigns/${campaignId}`)}
          >
            <Icons.ChevronLeft className="mr-1 h-4 w-4" />
            Back
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Connections Sent" value={s.connections_sent} />
        <KpiCard
          label="Connections Accepted"
          value={s.connections_accepted}
          sub={`${s.connection_accept_rate.toFixed(1)}% accept rate`}
        />
        <KpiCard
          label="Messages Sent"
          value={s.messages_sent}
          sub={`${s.messages_replied} conversations replied · ${s.response_rate.toFixed(1)}% reply rate`}
        />
        <KpiCard
          label="Converted"
          value={s.conversions}
          sub={`${s.conversion_rate.toFixed(1)}% of accepted connections`}
        />
      </div>

      {/* Channel breakdown - only when WA data exists */}
      {analytics.channels?.whatsapp && analytics.channels.whatsapp.messages_sent > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Channel Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg border p-3 space-y-1">
                <div className="flex items-center gap-1.5 text-sm font-medium text-blue-500">
                  <Icons.Users className="h-3.5 w-3.5" /> LinkedIn
                </div>
                <p className="text-xl font-bold">{analytics.channels.linkedin?.messages_sent ?? 0}</p>
                <p className="text-xs text-muted-foreground">
                  {analytics.channels.linkedin?.messages_replied ?? 0} replied · {(analytics.channels.linkedin?.response_rate ?? 0).toFixed(1)}%
                </p>
              </div>
              <div className="rounded-lg border p-3 space-y-1">
                <div className="flex items-center gap-1.5 text-sm font-medium text-emerald-500">
                  <Icons.MessageCircle className="h-3.5 w-3.5" /> WhatsApp
                </div>
                <p className="text-xl font-bold">{analytics.channels.whatsapp.messages_sent}</p>
                <p className="text-xs text-muted-foreground">
                  {analytics.channels.whatsapp.messages_replied} replied · {analytics.channels.whatsapp.response_rate.toFixed(1)}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Outreach funnel */}
        <Card>
          <CardHeader>
            <CardTitle>Outreach Funnel</CardTitle>
            <CardDescription>Leads at each stage of the flow</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={funnelData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
                  labelStyle={{ color: "hsl(var(--foreground))" }}
                  itemStyle={{ color: "hsl(var(--foreground))" }}
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {funnelData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Rates summary */}
        <Card>
          <CardHeader>
            <CardTitle>Conversion Rates</CardTitle>
            <CardDescription>Key performance percentages</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 pt-2">
            <RateBadge value={s.connection_accept_rate} label="Connection Accept Rate" sublabel="of requests sent" />
            <div className="h-px bg-border" />
            <RateBadge value={s.response_rate} label="Reply Rate" sublabel="conversations with a reply" />
            <div className="h-px bg-border" />
            <RateBadge value={s.conversion_rate} label="Conversion Rate" sublabel="of accepted connections" />
            {s.errors > 0 && (
              <>
                <div className="h-px bg-border" />
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm">Task Errors</span>
                  <Badge variant="destructive">{s.errors}</Badge>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Pipeline breakdown */}
      {pipelineData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Lead Pipeline</CardTitle>
            <CardDescription>
              {totalPipeline} total leads by deal state
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col lg:flex-row items-center gap-8">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={pipelineData}
                    cx="50%"
                    cy="50%"
                    innerRadius={65}
                    outerRadius={105}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {pipelineData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v) => [v, "leads"]}
                    contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
                    itemStyle={{ color: "hsl(var(--foreground))" }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
              <div className="w-full lg:w-auto min-w-[200px] space-y-2">
                {pipelineData.map(({ name, value, fill }) => (
                  <div key={name} className="flex items-center justify-between gap-6">
                    <div className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: fill }} />
                      <span className="text-sm">{name}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-medium tabular-nums">{value}</span>
                      <span className="text-xs text-muted-foreground ml-1.5">
                        {totalPipeline > 0 ? `${Math.round((value / totalPipeline) * 100)}%` : ""}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
