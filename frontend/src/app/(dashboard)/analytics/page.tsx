"use client";

import { useCallback, useEffect, useState } from "react";
import { Breadcrumb } from "@/components/layout/breadcrumb";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProgressCard } from "@/components/ui/progress-card";
import {
  getAnalyticsOverview,
  getCampaigns,
  type AnalyticsOverviewResponse,
} from "@/lib/api/dashboard";
import { Icons } from "@/lib/types/components";
import { Campaign } from "@/lib/types/components";

const EMPTY_OVERVIEW: AnalyticsOverviewResponse = {
  period: "30d",
  stats: {
    connectionsSent: 0,
    connectionsAccepted: 0,
    connectionAcceptRate: 0,
    messagesSent: 0,
    messagesReplied: 0,
    responseRate: 0,
    conversions: 0,
    conversionRate: 0,
  },
  totals: {
    leads: 0,
    qualified: 0,
    readyToConnect: 0,
    connected: 0,
    pending: 0,
    failed: 0,
    noEmail: 0,
    connectionAcceptRate: 0,
    responseRate: 0,
    conversionRate: 0,
  },
  pipeline: {
    qualified: 0,
    ready_to_connect: 0,
    pending: 0,
    connected: 0,
    completed: 0,
    failed: 0,
    no_email: 0,
  },
  campaigns: [],
};

function roundTo1Decimal(value: number): number {
  return Math.round(value * 10) / 10;
}

export default function AnalyticsOverviewPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [overview, setOverview] =
    useState<AnalyticsOverviewResponse>(EMPTY_OVERVIEW);
  const [selectedCampaign, setSelectedCampaign] = useState<string>("all");
  const [timeRange, setTimeRange] = useState<string>("30d");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCampaignOptions = useCallback(async () => {
    const response = await getCampaigns();
    if (response.data?.data) {
      setCampaigns(response.data.data);
      return;
    }

    throw new Error(
      response.error || response.message || "Failed to load campaigns",
    );
  }, []);

  const loadOverview = useCallback(
    async (campaignId: string, period: string) => {
      const response = await getAnalyticsOverview(campaignId, period);
      if (response.data) {
        setOverview(response.data);
        return;
      }

      throw new Error(
        response.error ||
          response.message ||
          "Failed to load analytics overview",
      );
    },
    [],
  );

  const refreshAll = useCallback(async () => {
    try {
      setError(null);
      setRefreshing(true);
      await Promise.all([
        loadCampaignOptions(),
        loadOverview(selectedCampaign, timeRange),
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred",
      );
    } finally {
      setRefreshing(false);
    }
  }, [loadCampaignOptions, loadOverview, selectedCampaign, timeRange]);

  useEffect(() => {
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        await Promise.all([
          loadCampaignOptions(),
          loadOverview(selectedCampaign, timeRange),
        ]);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "An unexpected error occurred",
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [loadCampaignOptions, loadOverview, selectedCampaign, timeRange]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Breadcrumb
          items={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Analytics", href: "/analytics", isActive: true },
          ]}
        />
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
          <div className="flex gap-4">
            <Skeleton className="h-10 w-44" />
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-10 w-28" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  const stats = overview.stats;
  const totals = overview.totals;
  const pipeline = overview.pipeline;
  const visibleCampaigns = overview.campaigns;

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Analytics", href: "/analytics", isActive: true },
        ]}
      />

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>Failed to load analytics: {error}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Analytics Overview
          </h1>
          <p className="text-muted-foreground">
            Live performance metrics across your campaigns
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Select
            value={selectedCampaign}
            onValueChange={(value) => {
              if (value) setSelectedCampaign(value);
            }}
          >
            <SelectTrigger className="w-full sm:w-45">
              <SelectValue placeholder="Select Campaign" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Campaigns</SelectItem>
              {campaigns.map((campaign) => (
                <SelectItem key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={timeRange}
            onValueChange={(value) => {
              if (value) setTimeRange(value);
            }}
          >
            <SelectTrigger className="w-full sm:w-32">
              <SelectValue placeholder="Time Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>

          <Button variant="outline" onClick={refreshAll} disabled={refreshing}>
            <Icons.RefreshCw
              className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <ProgressCard
          title="Connection Accept Rate"
          value={`${roundTo1Decimal(stats.connectionAcceptRate)}%`}
          subtitle={`${stats.connectionsAccepted} / ${stats.connectionsSent} accepted`}
          progress={Math.min(stats.connectionAcceptRate, 100)}
          progressColor="emerald"
          icon={<Icons.TrendingUp className="h-4 w-4" />}
        />

        <ProgressCard
          title="Response Rate"
          value={`${roundTo1Decimal(stats.responseRate)}%`}
          subtitle={`${stats.messagesReplied} / ${stats.messagesSent} replied`}
          progress={Math.min(stats.responseRate, 100)}
          progressColor="blue"
          icon={<Icons.MessageCircle className="h-4 w-4" />}
        />

        <ProgressCard
          title="Conversion Rate"
          value={`${roundTo1Decimal(stats.conversionRate)}%`}
          subtitle={`${stats.conversions} conversions from ${totals.qualified} qualified`}
          progress={Math.min(stats.conversionRate, 100)}
          progressColor="purple"
          icon={<Icons.Target className="h-4 w-4" />}
        />

        <ProgressCard
          title="Active Leads"
          value={totals.leads}
          subtitle={`${totals.qualified} qualified • ${totals.readyToConnect} ready`}
          progress={totals.leads > 0 ? (totals.readyToConnect / totals.leads) * 100 : 0}
          progressColor="amber"
          icon={<Icons.Users className="h-4 w-4" />}
        />
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">
            <Icons.BarChartBig className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="campaigns">
            <Icons.Users className="h-4 w-4 mr-2" />
            By Campaign
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Campaign Performance</CardTitle>
                <CardDescription>
                  Live metrics for the selected scope
                </CardDescription>
              </CardHeader>
              <CardContent>
                {visibleCampaigns.length > 0 ? (
                  <div className="space-y-3">
                    {visibleCampaigns.map((campaign) => (
                      <div
                        key={campaign.id}
                        className="flex items-center justify-between p-4 border border-border rounded-lg hover:border-primary/50 hover:bg-accent/30 hover:shadow-sm transition-all duration-200 cursor-pointer group"
                      >
                        <div className="flex-1">
                          <h4 className="font-semibold group-hover:text-primary transition-colors">{campaign.name}</h4>
                          <p className="text-sm text-muted-foreground line-clamp-1">
                            {campaign.description || "No description"}
                          </p>
                        </div>
                        <div className="text-right ml-4 flex-shrink-0">
                          <div className="text-lg font-bold text-primary">
                            {campaign.stats?.totalLeads || 0}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {campaign.stats?.connectionAcceptRate || 0}% accept rate
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Icons.InboxIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No campaigns match the current filter.</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Lead Pipeline</CardTitle>
                <CardDescription>
                  Current lead distribution across stages
                </CardDescription>
              </CardHeader>
              <CardContent>
                {totals.leads > 0 ||
                pipeline.completed > 0 ||
                pipeline.failed > 0 ||
                pipeline.no_email > 0 ? (
                  <div className="space-y-3">
                    {[
                      {
                        stage: "Qualified",
                        count: pipeline.qualified,
                        color: "bg-blue-500",
                        icon: Icons.CheckCircle,
                      },
                      {
                        stage: "Ready to Connect",
                        count: pipeline.ready_to_connect,
                        color: "bg-amber-500",
                        icon: Icons.Zap,
                      },
                      {
                        stage: "Pending",
                        count: pipeline.pending,
                        color: "bg-orange-500",
                        icon: Icons.Clock,
                      },
                      {
                        stage: "Connected",
                        count: pipeline.connected,
                        color: "bg-emerald-500",
                        icon: Icons.Link,
                      },
                      {
                        stage: "Completed",
                        count: pipeline.completed,
                        color: "bg-purple-500",
                        icon: Icons.Check,
                      },
                      {
                        stage: "Failed",
                        count: pipeline.failed,
                        color: "bg-rose-500",
                        icon: Icons.AlertCircle,
                      },
                      {
                        stage: "No Email",
                        count: pipeline.no_email,
                        color: "bg-slate-500",
                        icon: Icons.Mail,
                      },
                    ]
                      .filter((item) => item.count > 0)
                      .map((item) => {
                        const Icon = item.icon;
                        return (
                          <div
                            key={item.stage}
                            className="flex items-center space-x-3 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                          >
                            <Icon className={`h-4 w-4 flex-shrink-0 ${item.color.replace('bg-', 'text-')}`} />
                            <div className="flex-1 min-w-0">
                              <div className="flex justify-between items-center mb-1.5">
                                <span className="text-sm font-medium">{item.stage}</span>
                                <span className="text-sm font-bold">{item.count}</span>
                              </div>
                              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${item.color} transition-all duration-300`}
                                  style={{
                                    width: `${totals.leads > 0 ? (item.count / Math.max(totals.leads, item.count)) * 100 : 100}%`,
                                  }}
                                />
                              </div>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-muted-foreground">
                      No pipeline data available yet.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="campaigns" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Comparison</CardTitle>
              <CardDescription>
                Real metrics for the selected time range
              </CardDescription>
            </CardHeader>
            <CardContent>
              {visibleCampaigns.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left py-3 px-4 font-semibold">Campaign</th>
                        <th className="text-left py-3 px-4 font-semibold">Leads</th>
                        <th className="text-left py-3 px-4 font-semibold">Accept Rate</th>
                        <th className="text-left py-3 px-4 font-semibold">Response Rate</th>
                        <th className="text-left py-3 px-4 font-semibold">Conversion Rate</th>
                        <th className="text-left py-3 px-4 font-semibold">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleCampaigns.map((campaign) => (
                        <tr
                          key={campaign.id}
                          className="border-b hover:bg-muted/50 transition-colors hover:cursor-pointer"
                        >
                          <td className="py-3 px-4">
                            <div className="font-medium">{campaign.name}</div>
                            <div className="text-xs text-muted-foreground truncate max-w-xs">
                              {campaign.description || "No description"}
                            </div>
                          </td>
                          <td className="py-3 px-4 font-bold">{campaign.stats?.totalLeads || 0}</td>
                          <td className="py-3 px-4">
                            <div className="flex items-center space-x-1">
                              <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-emerald-500"
                                  style={{
                                    width: `${Math.min(campaign.stats?.connectionAcceptRate || 0, 100)}%`,
                                  }}
                                />
                              </div>
                              <span className="text-xs font-medium">
                                {campaign.stats?.connectionAcceptRate || 0}%
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex items-center space-x-1">
                              <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-blue-500"
                                  style={{
                                    width: `${Math.min(campaign.stats?.responseRate || 0, 100)}%`,
                                  }}
                                />
                              </div>
                              <span className="text-xs font-medium">
                                {campaign.stats?.responseRate || 0}%
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex items-center space-x-1">
                              <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-purple-500"
                                  style={{
                                    width: `${Math.min(campaign.stats?.conversionRate || 0, 100)}%`,
                                  }}
                                />
                              </div>
                              <span className="text-xs font-medium">
                                {campaign.stats?.conversionRate || 0}%
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                campaign.status === "active"
                                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                  : campaign.status === "paused"
                                    ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                                    : "bg-slate-100 text-slate-800 dark:bg-slate-950 dark:text-slate-300"
                              }`}
                            >
                              {campaign.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <Icons.InboxIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No campaign data available for this filter.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
