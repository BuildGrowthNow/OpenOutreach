"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Icons } from "@/lib/types/components";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  getCampaign,
  getCampaignAnalytics,
  getCampaignLeads,
  updateCampaign,
  deleteCampaign,
  clearCampaignErrors,
  getDailyUsage,
  getCampaignStatus,
} from "@/lib/api/dashboard";
import {
  Campaign,
  Lead,
} from "@/lib/types/components";
import { CampaignStats as CampaignStatsComponent } from "@/components/campaigns/campaign-stats";
import { CampaignList as CampaignListComponent } from "@/components/campaigns/campaign-list";
import { CampaignActivity } from "@/components/campaigns/campaign-activity";
import { DailyProgress } from "@/components/campaigns/daily-progress";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  zincDialogContentClassName,
  zincDialogFooterClassName,
  zincDialogHeaderClassName,
  zincInputClassName,
} from "@/lib/modal-styles";

interface CampaignAnalyticsResponse {
  stats: {
    connections_sent: number;
    connections_accepted: number;
    messages_sent: number;
    messages_replied: number;
    conversions: number;
    connection_accept_rate: number;
    response_rate: number;
    conversion_rate: number;
    errors: number;
    rate_limit_warnings: number;
  };
  pipeline?: Record<string, number>;
}



export default function CampaignDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const campaignId = params.id as string;

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const campaignStatusRef = useRef<string | undefined>(undefined);
  const [analytics, setAnalytics] = useState<CampaignAnalyticsResponse | null>(
    null,
  );
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [deleting, setDeleting] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);

  const [dailyUsage, setDailyUsage] = useState<{
    dailyConnectionsSent: number;
    dailyMessagesSent: number;
    dailyLimit: number;
    effectiveLimit: number;
    remaining: number;
    rateLimitStatus: "normal" | "caution" | "warning" | "exceeded";
    warningMessage?: string;
    warningLevel?: "low" | "medium" | "high";
  }>({
    dailyConnectionsSent: 0,
    dailyMessagesSent: 0,
    dailyLimit: 20,
    effectiveLimit: 20,
    remaining: 20,
    rateLimitStatus: "normal",
    warningLevel: "low",
  });

  const [actionLoading, setActionLoading] = useState(false);

  const fetchCampaignData = useCallback(
    async (silent = false) => {
      try {
        if (!silent) setLoading(true);
        setError(null);

        // Fetch campaign details
        const campaignResponse = await getCampaign(campaignId);
        if (campaignResponse.data) {
          setCampaign(campaignResponse.data!);
        } else {
          setError(
            campaignResponse.error ||
              campaignResponse.message ||
              "Failed to fetch campaign",
          );
        }

        // Fetch campaign analytics
        const analyticsResponse = await getCampaignAnalytics(campaignId);
        if (analyticsResponse.data) {
          setAnalytics(analyticsResponse.data);
        }

        // Fetch campaign leads
        const leadsResponse = await getCampaignLeads(campaignId);
        if (leadsResponse.data) {
          setLeads(leadsResponse.data.data || []);
        }

        // Fetch daily usage
        const dailyUsageResponse = await getDailyUsage();
        if (dailyUsageResponse.data) {
          setDailyUsage({
            dailyConnectionsSent:
              dailyUsageResponse.data.daily_connections_sent || 0,
            dailyMessagesSent:
              dailyUsageResponse.data.daily_messages_sent || 0,
            dailyLimit: dailyUsageResponse.data.daily_limit || 20,
            effectiveLimit: dailyUsageResponse.data.effective_limit || 20,
            remaining: dailyUsageResponse.data.remaining || 20,
            rateLimitStatus:
              dailyUsageResponse.data.rate_limit_status || "normal",
            warningMessage: dailyUsageResponse.data.warning_message,
            warningLevel: dailyUsageResponse.data.warning_level,
          });
        }
      } catch (err) {
        setError("An error occurred while fetching campaign data");
        console.error("Error fetching campaign data:", err);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [campaignId],
  );

  const refetchDailyUsage = useCallback(async () => {
    try {
      const dailyUsageResponse = await getDailyUsage();
      if (dailyUsageResponse.data) {
        setDailyUsage({
          dailyConnectionsSent:
            dailyUsageResponse.data.daily_connections_sent || 0,
          dailyMessagesSent:
            dailyUsageResponse.data.daily_messages_sent || 0,
          dailyLimit: dailyUsageResponse.data.daily_limit || 20,
          effectiveLimit: dailyUsageResponse.data.effective_limit || 20,
          remaining: dailyUsageResponse.data.remaining || 20,
          rateLimitStatus:
            dailyUsageResponse.data.rate_limit_status || "normal",
          warningMessage: dailyUsageResponse.data.warning_message,
          warningLevel: dailyUsageResponse.data.warning_level,
        });
      }
    } catch (err) {
      console.error("Error fetching daily usage:", err);
    }
  }, []);

  // Only show as active if there are actual simulation entries
  useEffect(() => {
    void (async () => {
      await fetchCampaignData(false);
    })();
  }, [fetchCampaignData]);

  // Keep ref in sync so the polling callback stays stable
  useEffect(() => {
    campaignStatusRef.current = campaign?.status;
  }, [campaign?.status]);

  // Targeted polling: fetch only status every 10 seconds
  // Full data is fetched only on initial load or manual refresh
  const fetchCampaignStatus = useCallback(async () => {
    try {
      const response = await getCampaignStatus(campaignId);
      if (
        response.data &&
        typeof response.data === "object" &&
        "status" in response.data
      ) {
        const statusData = response.data as { status: string };
        if (statusData.status !== campaignStatusRef.current) {
          setCampaign((prev) =>
            prev ? { ...prev, status: statusData.status } : null,
          );
        }
      }
    } catch (err) {
      console.error("Error fetching campaign status during polling:", err);
    }
  }, [campaignId]);

  // Poll for status updates every 10 seconds (lightweight - single small API call)
  useEffect(() => {
    if (!campaignId) return;
    const interval = setInterval(() => {
      void fetchCampaignStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, [campaignId, fetchCampaignStatus]);

  // Poll leads every 30 seconds so new discoveries appear without a page reload
  const fetchLeadsSilent = useCallback(async () => {
    try {
      const leadsResponse = await getCampaignLeads(campaignId);
      if (leadsResponse.data) {
        setLeads(leadsResponse.data.data || []);
      }
    } catch {
      // silent — don't surface polling errors to the user
    }
  }, [campaignId]);

  useEffect(() => {
    if (!campaignId) return;
    const interval = setInterval(() => {
      void fetchLeadsSilent();
    }, 30000);
    return () => clearInterval(interval);
  }, [campaignId, fetchLeadsSilent]);


  const handleClearErrors = async () => {
    if (!campaign) return;
    await clearCampaignErrors(campaign.id);
    fetchCampaignData(true);
  };

  const handleDeleteCampaign = async () => {
    if (!campaign) return;
    setShowDeleteModal(false);
    setDeleting(true);
    const result = await deleteCampaign(campaign.id);
    if (result.error) {
      setError(result.error);
      setDeleting(false);
      return;
    }
    router.push("/campaigns");
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20";
      case "paused":
        return "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20";
      case "draft":
        return "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20";
      case "completed":
        return "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20";
      default:
        return "bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20";
    }
  };

  const handleMarkCompleted = async () => {
    if (!campaign) return;
    try {
      setError(null);
      const response = await updateCampaign(campaign.id, {
        status: "completed",
      });
      if (response.data) {
        setCampaign(response.data);
        setShowCompletionModal(false);
        fetchCampaignData();
      } else {
        setError(
          response.error || response.message || "Failed to complete campaign",
        );
      }
    } catch (err) {
      setError("An error occurred while completing the campaign");
      console.error("Error completing campaign:", err);
    }
  };

  const handlePauseCampaign = async () => {
    if (!campaign) return;
    try {
      setActionLoading(true);
      setError(null);
      const response = await updateCampaign(campaign.id, {
        isPaused: true,
        status: "paused",
      });
      if (response.data) {
        setCampaign(response.data);
        fetchCampaignData(true);
      } else {
        setError(response.error || "Failed to pause campaign");
      }
    } catch (err) {
      setError("An error occurred while pausing the campaign");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResumeCampaign = async () => {
    if (!campaign) return;
    try {
      setActionLoading(true);
      setError(null);
      const response = await updateCampaign(campaign.id, {
        isPaused: false,
        status: "active",
      });
      if (response.data) {
        setCampaign(response.data);
        fetchCampaignData(true);
      } else {
        setError(response.error || "Failed to resume campaign");
      }
    } catch (err) {
      setError("An error occurred while resuming the campaign");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-10 w-24" />
            <Skeleton className="h-10 w-24" />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
          <div className="space-y-6">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive">
          <AlertTitle>Campaign Not Found</AlertTitle>
          <AlertDescription>
            The campaign you're looking for doesn't exist or you don't have
            permission to view it.
          </AlertDescription>
        </Alert>
        <Button onClick={() => router.push("/campaigns")}>
          <Icons.ChevronRight className="mr-2 h-4 w-4" />
          Back to Campaigns
        </Button>
      </div>
    );
  }

  const stats = analytics?.stats || {
    connections_sent: 0,
    connections_accepted: 0,
    messages_sent: 0,
    messages_replied: 0,
    conversions: 0,
    connection_accept_rate: 0,
    response_rate: 0,
    conversion_rate: 0,
    errors: 0,
    rate_limit_warnings: 0,
  };

  const hasCompletedConnections = stats.connections_sent > 0;
  const now = Date.now();
  const daysSinceStart = campaign.createdAt
    ? Math.ceil(
        (now - new Date(campaign.createdAt).getTime()) / (1000 * 60 * 60 * 24),
      )
    : 1;
  const avgDailyConnections =
    stats.connections_sent / Math.max(daysSinceStart, 1);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">
              {campaign.name}
            </h1>
            <Badge
              variant="outline"
              className={cn("text-xs", getStatusColor(campaign.status))}
            >
              {campaign.status.charAt(0).toUpperCase() +
                campaign.status.slice(1)}
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {(() => {
              const pitch = campaign.productPitch || (campaign as unknown as Record<string, string>).product_pitch || ''
              if (!pitch) return <span className="italic">No description</span>
              return pitch.length > 90 ? pitch.slice(0, 90) + '…' : pitch
            })()}
          </p>
        </div>
        <div className="flex gap-2">
          {campaign.status === "active" ? (
            <Button
              variant="outline"
              className="border-amber-500/20 text-amber-600 hover:bg-amber-500/10 dark:text-amber-400"
              onClick={handlePauseCampaign}
              disabled={actionLoading}
            >
              <Icons.Pause className="mr-2 h-4 w-4" />
              Pause
            </Button>
          ) : campaign.status === "paused" ? (
            <Button
              variant="outline"
              className="border-emerald-500/20 text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400"
              onClick={handleResumeCampaign}
              disabled={actionLoading}
            >
              <Icons.Play className="mr-2 h-4 w-4" />
              Resume
            </Button>
          ) : campaign.status === "draft" ? (
            <Button
              variant="outline"
              className="border-emerald-500/20 text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400"
              onClick={handleResumeCampaign}
              disabled={actionLoading}
            >
              <Icons.Play className="mr-2 h-4 w-4" />
              Start
            </Button>
          ) : null}
          <Button
            variant="destructive"
            onClick={() => setShowDeleteModal(true)}
            disabled={deleting}
          >
            {deleting ? (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Deleting...
              </>
            ) : (
              <>
                <Icons.Trash2 className="mr-2 h-4 w-4" />
                Delete
              </>
            )}
          </Button>
          <Dialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
            <DialogContent className={`${zincDialogContentClassName} sm:max-w-[420px]`}>
              <DialogHeader className={zincDialogHeaderClassName}>
                <DialogTitle>Delete Campaign</DialogTitle>
                <DialogDescription>
                  This will permanently delete &quot;{campaign?.name}&quot; along with all its leads, deals, and conversation history. This cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter className={zincDialogFooterClassName}>
                <Button
                  variant="outline"
                  className="border-zinc-800 bg-zinc-900 text-zinc-100 hover:bg-zinc-800"
                  onClick={() => setShowDeleteModal(false)}
                >
                  Cancel
                </Button>
                <Button variant="destructive" onClick={handleDeleteCampaign}>
                  Delete Campaign
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Tabs Navigation */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-4 w-full md:w-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="leads">Leads</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column */}
            <div className="lg:col-span-2 space-y-6">
              {/* Campaign Stats */}
              <Card>
                <CardHeader>
                  <CardTitle>Campaign Statistics</CardTitle>
                  <CardDescription>
                    Performance metrics for this campaign
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {analytics ? (
                    <CampaignStatsComponent stats={analytics.stats} onClearErrors={handleClearErrors} />
                  ) : (
                    <div className="space-y-4">
                      <Skeleton className="h-32 w-full" />
                      <Skeleton className="h-24 w-full" />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Campaign Activity */}
              <CampaignActivity campaignId={campaignId} compact />
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              {/* Daily Progress */}
              <Card>
                <CardHeader>
                  <CardTitle>Daily Progress</CardTitle>
                  <CardDescription>Today's account-wide velocity</CardDescription>
                </CardHeader>
                <CardContent>
                  <DailyProgress
                    dailyConnectionsSent={dailyUsage.dailyConnectionsSent}
                    dailyMessagesSent={dailyUsage.dailyMessagesSent}
                    dailyLimit={dailyUsage.dailyLimit}
                    effectiveLimit={dailyUsage.effectiveLimit}
                  />
                  {/* Show warning banner if limit is exceeded or approaching */}
                  {dailyUsage.rateLimitStatus === "exceeded" && (
                    <div className="mt-4 rounded-md bg-destructive/10 border border-destructive/20 p-3">
                      <div className="flex items-start gap-3">
                        <Icons.AlertTriangle className="h-5 w-5 text-destructive mt-0.5" />
                        <div>
                          <h5 className="font-medium text-destructive">
                            Daily Connection Limit Exceeded
                          </h5>
                          <p className="text-sm text-destructive/80 mt-1">
                            {dailyUsage.warningMessage ||
                              "You have reached your daily connection limit. No more connections can be sent today."}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  {dailyUsage.rateLimitStatus === "warning" && (
                    <div className="mt-4 rounded-md bg-amber-500/10 border border-amber-500/20 p-3">
                      <div className="flex items-start gap-3">
                        <Icons.AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5" />
                        <div>
                          <h5 className="font-medium text-amber-600 dark:text-amber-400">
                            Approaching Rate Limit
                          </h5>
                          <p className="text-sm text-amber-600/80 dark:text-amber-400/80 mt-1">
                            {dailyUsage.warningMessage ||
                              "You are approaching your daily connection limit."}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Campaign Details */}
              <Card>
                <CardHeader>
                  <CardTitle>Campaign Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">
                        Status
                      </span>
                      <Badge
                        variant="outline"
                        className={cn(getStatusColor(campaign.status))}
                      >
                        {campaign.status}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">
                        Created
                      </span>
                      <span className="font-medium">
                        {(() => {
                          const raw = (campaign as unknown as Record<string, string>).created_at || campaign.createdAt;
                          const d = raw ? new Date(raw) : null;
                          return d && !isNaN(d.getTime()) ? d.toLocaleDateString() : "—";
                        })()}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <Card>
                <CardHeader>
                  <CardTitle>Quick Actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() =>
                      router.push(`/campaigns/${campaignId}/leads`)
                    }
                  >
                    <Icons.Users className="mr-2 h-4 w-4" />
                    View All Leads
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() =>
                      router.push(`/campaigns/${campaignId}/analytics`)
                    }
                  >
                    <Icons.BarChart3 className="mr-2 h-4 w-4" />
                    View Analytics
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() =>
                      router.push(`/messages?campaign=${campaignId}`)
                    }
                  >
                    <Icons.MessageSquare className="mr-2 h-4 w-4" />
                    View Campaign Messages
                  </Button>
                  {/* State Machine temporarily hidden - incomplete feature */}
                  {process.env.NEXT_PUBLIC_ENABLE_STATE_MACHINE === 'true' && (
                    <Button
                      variant="outline"
                      className="w-full justify-start"
                      onClick={() =>
                        router.push(`/campaigns/${campaignId}/state-machine`)
                      }
                    >
                      <Icons.ListTodo className="mr-2 h-4 w-4" />
                      State Machine
                    </Button>
                  )}
                  {campaign.status !== "completed" && (
                    <>
                      <Button
                        variant="default"
                        className="w-full justify-start bg-emerald-600 hover:bg-emerald-700"
                        onClick={() => setShowCompletionModal(true)}
                      >
                        <Icons.Check className="mr-2 h-4 w-4" />
                        Archive Campaign
                      </Button>
                      <Dialog
                        open={showCompletionModal}
                        onOpenChange={setShowCompletionModal}
                      >
                        <DialogContent
                          className={`${zincDialogContentClassName} sm:max-w-[720px]`}
                        >
                          <DialogHeader className={zincDialogHeaderClassName}>
                            <DialogTitle>Archive Campaign</DialogTitle>
                            <DialogDescription>
                              This stops all automation and marks the campaign as completed. The campaign and its leads remain visible — nothing is deleted.
                            </DialogDescription>
                          </DialogHeader>
                          <div className="space-y-4 py-4">
                            <div className="grid grid-cols-2 gap-4">
                              <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                                <div className="text-sm text-zinc-400">
                                  Total Connections Sent
                                </div>
                                <div className="text-2xl font-bold text-zinc-100">
                                  {stats.connections_sent}
                                </div>
                              </div>
                              <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                                <div className="text-sm text-zinc-400">
                                  Connection Accept Rate
                                </div>
                                <div className="text-2xl font-bold text-zinc-100">
                                  {stats.connection_accept_rate >= 0
                                    ? stats.connection_accept_rate.toFixed(1)
                                    : "0.0"}
                                  %
                                </div>
                              </div>
                              <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                                <div className="text-sm text-zinc-400">
                                  Messages Sent
                                </div>
                                <div className="text-2xl font-bold text-zinc-100">
                                  {stats.messages_sent}
                                </div>
                              </div>
                              <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                                <div className="text-sm text-zinc-400">
                                  Conversions
                                </div>
                                <div className="text-2xl font-bold text-zinc-100">
                                  {stats.conversions}
                                </div>
                              </div>
                            </div>
                            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                              <div className="flex items-center justify-between">
                                <span className="text-sm font-medium">
                                  Overall ROI Summary
                                </span>
                                <span className="font-bold">
                                  {stats.connection_accept_rate > 0
                                    ? `${stats.conversions} conversions from ${stats.connections_sent} connections`
                                    : "No connection data yet"}
                                </span>
                              </div>
                            </div>
                          </div>
                          <DialogFooter className={zincDialogFooterClassName}>
                            <Button
                              variant="outline"
                              className="border-zinc-800 bg-zinc-900 text-zinc-100 hover:bg-zinc-800"
                              onClick={() => setShowCompletionModal(false)}
                            >
                              Cancel
                            </Button>
                            <Button
                              variant="destructive"
                              onClick={handleMarkCompleted}
                            >
                              Archive Campaign
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Leads Tab */}
        <TabsContent value="leads" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-2 sm:space-y-0">
              <div>
                <CardTitle>Campaign Leads</CardTitle>
                <CardDescription>
                  All leads associated with this campaign
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {leads.length > 0 ? (
                <CampaignListComponent leads={leads} campaignId={campaignId} onLeadsUpdated={fetchLeadsSilent} />
              ) : (
                <div className="text-center py-12">
                  <Icons.Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No Leads Yet</h3>
                  <p className="text-sm text-muted-foreground mb-6">
                    Start adding leads to this campaign to see them here.
                  </p>
                  <Button onClick={() => router.push("/leads")}>
                    <Icons.UserPlus className="mr-2 h-4 w-4" />
                    Add Leads
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>


        {/* Analytics Tab */}
        <TabsContent value="analytics" className="space-y-6">
          {analytics ? (
            <CampaignAnalyticsCharts analytics={analytics} />
          ) : (
            <div className="text-center py-12">
              <p className="text-muted-foreground">
                No analytics data available yet
              </p>
            </div>
          )}
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-6">
          <CampaignSettingsForm
            campaign={campaign}
            saving={settingsSaving}
            onSave={async (data) => {
              setSettingsSaving(true);
              setError(null);
              try {
                const response = await updateCampaign(campaign.id, data);
                if (response.data) {
                  setCampaign(response.data);
                } else {
                  setError(response.error || "Failed to save settings");
                }
              } catch {
                setError("An error occurred while saving settings");
              } finally {
                setSettingsSaving(false);
              }
            }}
          />
        </TabsContent>
      </Tabs>

    </div>
  );
}


const PIPELINE_COLORS: Record<string, string> = {
  discovered: "#71717a",
  qualified: "#3b82f6",
  ready_to_connect: "#6366f1",
  pending: "#a855f7",
  connected: "#06b6d4",
  completed: "#10b981",
  failed: "#ef4444",
  no_email: "#9ca3af",
};

const PIPELINE_LABELS: Record<string, string> = {
  discovered: "Discovered",
  qualified: "Qualified",
  ready_to_connect: "Ready",
  pending: "Pending",
  connected: "Connected",
  completed: "Done",
  failed: "Failed",
  no_email: "No Email",
};

function CampaignAnalyticsCharts({ analytics }: { analytics: CampaignAnalyticsResponse }) {
  const s = analytics.stats;

  const funnelData = [
    { name: "Sent", value: s.connections_sent },
    { name: "Accepted", value: s.connections_accepted },
    { name: "Messaged", value: s.messages_sent },
    { name: "Replied", value: s.messages_replied },
    { name: "Done", value: s.conversions },
  ];

  const ratesData = [
    { name: "Accept Rate", value: parseFloat(s.connection_accept_rate.toFixed(1)) },
    { name: "Response Rate", value: parseFloat(s.response_rate.toFixed(1)) },
    { name: "Conversion Rate", value: parseFloat(s.conversion_rate.toFixed(1)) },
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

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Connections Sent", value: s.connections_sent },
          { label: "Connections Accepted", value: s.connections_accepted },
          { label: "Messages Sent", value: s.messages_sent },
          { label: "Replies", value: s.messages_replied },
        ].map(({ label, value }) => (
          <Card key={label}>
            <CardContent className="pt-6 text-center">
              <div className="text-3xl font-bold">{value}</div>
              <div className="text-sm text-muted-foreground mt-1">{label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Funnel bar chart */}
        <Card>
          <CardHeader>
            <CardTitle>Outreach Funnel</CardTitle>
            <CardDescription>Leads at each stage of the outreach flow</CardDescription>
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
                  {funnelData.map((_, i) => (
                    <Cell key={i} fill={["#6366f1", "#06b6d4", "#3b82f6", "#a855f7", "#10b981"][i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Conversion rates bar chart */}
        <Card>
          <CardHeader>
            <CardTitle>Conversion Rates</CardTitle>
            <CardDescription>Key performance percentages</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={ratesData} layout="vertical" margin={{ top: 4, right: 24, left: 10, bottom: 0 }}>
                <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                <Tooltip
                  formatter={(v) => [`${v}%`, ""]}
                  contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
                  labelStyle={{ color: "hsl(var(--foreground))" }}
                  itemStyle={{ color: "hsl(var(--foreground))" }}
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  <Cell fill="#6366f1" />
                  <Cell fill="#3b82f6" />
                  <Cell fill="#10b981" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Pipeline breakdown */}
      {pipelineData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Lead Pipeline Breakdown</CardTitle>
            <CardDescription>Current distribution of leads by deal state</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col lg:flex-row items-center gap-6">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={pipelineData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {pipelineData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
                    itemStyle={{ color: "hsl(var(--foreground))" }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
              <div className="w-full lg:w-auto space-y-2 min-w-[180px]">
                {pipelineData.map(({ name, value, fill }) => (
                  <div key={name} className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: fill }} />
                      <span className="text-sm">{name}</span>
                    </div>
                    <span className="text-sm font-medium tabular-nums">{value}</span>
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

function CampaignSettingsForm({
  campaign,
  saving,
  onSave,
}: {
  campaign: Campaign;
  saving: boolean;
  onSave: (data: Partial<Campaign>) => Promise<void>;
}) {
  // API returns snake_case, TS interface declares camelCase — read both
  const c = campaign as unknown as Record<string, unknown>;
  const getStr = (camel: string, snake: string) => String(c[camel] || c[snake] || "");
  const getArr = (camel: string, snake: string) => (c[camel] || c[snake] || []) as string[];

  const [name, setName] = useState(campaign.name || "");
  const [productPitch, setProductPitch] = useState(getStr("productPitch", "product_pitch"));
  const [campaignObjective, setCampaignObjective] = useState(getStr("campaignObjective", "campaign_objective"));
  const [bookingLink, setBookingLink] = useState(getStr("bookingLink", "booking_link"));
  const [icpTitles, setIcpTitles] = useState<string[]>(getArr("icpTitles", "icp_titles"));
  const [icpInput, setIcpInput] = useState("");
  const [targetCompanySize, setTargetCompanySize] = useState(getStr("targetCompanySize", "target_company_size"));
  const [followUpStrategy, setFollowUpStrategy] = useState(getStr("followUpStrategy", "follow_up_strategy"));

  useEffect(() => {
    const c2 = campaign as unknown as Record<string, unknown>;
    const s = (camel: string, snake: string) => String(c2[camel] || c2[snake] || "");
    const a = (camel: string, snake: string) => (c2[camel] || c2[snake] || []) as string[];
    setName(campaign.name || "");
    setProductPitch(s("productPitch", "product_pitch"));
    setCampaignObjective(s("campaignObjective", "campaign_objective"));
    setBookingLink(s("bookingLink", "booking_link"));
    setIcpTitles(a("icpTitles", "icp_titles"));
    setTargetCompanySize(s("targetCompanySize", "target_company_size"));
    setFollowUpStrategy(s("followUpStrategy", "follow_up_strategy"));
  }, [campaign]);

  const handleAddTitle = () => {
    const title = icpInput.trim();
    if (title && !icpTitles.includes(title)) {
      setIcpTitles([...icpTitles, title]);
      setIcpInput("");
    }
  };

  const handleSave = async () => {
    // API expects snake_case field names
    await onSave({
      name: name.trim(),
      product_pitch: productPitch.trim(),
      campaign_objective: campaignObjective.trim(),
      booking_link: bookingLink.trim(),
      icp_titles: icpTitles,
      target_company_size: targetCompanySize.trim() || undefined,
      follow_up_strategy: followUpStrategy.trim() || undefined,
    } as unknown as Partial<Campaign>);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Campaign Info</CardTitle>
          <CardDescription>Core campaign details and messaging</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="settings-name">Campaign Name</Label>
            <Input
              id="settings-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Campaign name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="settings-pitch">Product Pitch</Label>
            <Textarea
              id="settings-pitch"
              value={productPitch}
              onChange={(e) => setProductPitch(e.target.value)}
              placeholder="What problem do you solve?"
              rows={4}
              className="resize-none"
            />
            <p className="text-xs text-muted-foreground">
              The AI uses this to personalize outreach messages
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="settings-objective">Campaign Goal</Label>
            <Textarea
              id="settings-objective"
              value={campaignObjective}
              onChange={(e) => setCampaignObjective(e.target.value)}
              placeholder="What are you trying to achieve?"
              rows={3}
              className="resize-none"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="settings-booking">Booking Link</Label>
            <Input
              id="settings-booking"
              value={bookingLink}
              onChange={(e) => setBookingLink(e.target.value)}
              placeholder="https://calendly.com/you/30min"
              type="url"
            />
            <p className="text-xs text-muted-foreground">
              The AI shares this when a lead shows interest
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="settings-strategy">Follow-Up Strategy <span className="text-muted-foreground font-normal">(optional)</span></Label>
            <Textarea
              id="settings-strategy"
              value={followUpStrategy}
              onChange={(e) => setFollowUpStrategy(e.target.value)}
              placeholder="Additional instructions for how the AI should handle follow-up conversations..."
              rows={3}
              className="resize-none"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Targeting</CardTitle>
          <CardDescription>Who should the AI search for on LinkedIn</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Target Job Titles</Label>
            <div className="flex gap-2">
              <Input
                value={icpInput}
                onChange={(e) => setIcpInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddTitle();
                  }
                }}
                placeholder="Add a job title and press Enter"
                className="flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddTitle}
                disabled={!icpInput.trim()}
              >
                Add
              </Button>
            </div>
            {icpTitles.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {icpTitles.map((title) => (
                  <Badge key={title} variant="secondary" className="text-sm py-1 px-3 gap-1.5">
                    {title}
                    <button
                      type="button"
                      onClick={() => setIcpTitles(icpTitles.filter((t) => t !== title))}
                      className="hover:text-destructive transition-colors"
                    >
                      <Icons.X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              The AI generates LinkedIn search queries based on these titles
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="settings-company-size">
              Target Company Size <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Input
              id="settings-company-size"
              value={targetCompanySize}
              onChange={(e) => setTargetCompanySize(e.target.value)}
              placeholder="e.g., small to medium companies, 10-500 employees, no enterprise"
            />
            <p className="text-xs text-muted-foreground">
              Leads who clearly work at companies outside this range (e.g. Google, Spotify) will be disqualified
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <>
              <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Save Settings"
          )}
        </Button>
      </div>
    </div>
  );
}
