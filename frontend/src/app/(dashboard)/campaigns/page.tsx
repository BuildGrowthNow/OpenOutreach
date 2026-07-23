"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Icons } from "@/lib/types/components";
import {
  getCampaigns,
  updateCampaign,
  deleteCampaign,
} from "@/lib/api/dashboard";
import { Campaign } from "@/lib/types/components";
import { CampaignCard } from "@/components/dashboard/campaign-card";
import { CreateCampaignWizard } from "@/components/campaigns/create-campaign-wizard";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { Breadcrumb } from "@/components/layout/breadcrumb";
import { BulkActionsToolbar, BulkAction } from "@/components/ui/bulk-actions-toolbar";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import { PlanLimitButton } from "@/components/billing/plan-limit-button";
import { useUpgradeToast } from "@/lib/hooks/use-upgrade-toast";

export default function CampaignsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const handleUpgradeError = useUpgradeToast();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null);
  const [selectedCampaignIds, setSelectedCampaignIds] = useState<Set<string>>(new Set());

  const fetchCampaigns = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getCampaigns();
      if (response.data) {
        setCampaigns(response.data.data || []);
      } else {
        setError(
          response.error || response.message || "Failed to fetch campaigns",
        );
      }
    } catch (err) {
      setError("An error occurred while fetching campaigns");
      console.error("Error fetching campaigns:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await fetchCampaigns();
    })();
  }, [fetchCampaigns]);

  const filteredCampaigns = useMemo(() => {
    let filtered = [...campaigns];

    // Filter by tab
    if (selectedTab !== "all") {
      filtered = filtered.filter((campaign) => campaign.status === selectedTab);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(
        (campaign) =>
          campaign.name.toLowerCase().includes(query) ||
          campaign.description?.toLowerCase().includes(query),
      );
    }

    return filtered;
  }, [campaigns, selectedTab, searchQuery]);


  const handleUpdateCampaign = async (id: string, data: Partial<Campaign>) => {
    try {
      setError(null);
      const response = await updateCampaign(id, data);
      if (response.data) {
        // Update the local campaigns list immediately
        setCampaigns((prev) =>
          prev.map((c) => (c.id === id ? response.data! : c))
        );
        setEditingCampaign(null);
        // Also refresh to ensure consistency
        fetchCampaigns();
      } else {
        setError(
          response.error || response.message || "Failed to update campaign",
        );
      }
    } catch (error) {
      setError("An error occurred while updating the campaign");
      console.error("Error updating campaign:", error);
    }
  };

  const handleDeleteCampaign = async (campaign: Campaign) => {
    try {
      setError(null);
      await deleteCampaign(campaign.id);
      // Deletion successful (204 No Content) - refresh list
      fetchCampaigns();
    } catch (error) {
      console.error("Error deleting campaign:", error);
      setError("An error occurred while deleting the campaign");
    }
  };

  const handleCampaignClick = (campaign: Campaign) => {
    router.push(`/campaigns/${campaign.id}`);
  };

  const handleEditCampaign = (campaign: Campaign) => {
    setEditingCampaign(campaign);
  };

  const handleDeleteClick = (campaign: Campaign) => {
    handleDeleteCampaign(campaign);
  };

  const handleStartCampaign = async (campaign: Campaign) => {
    try {
      setError(null);
      const response = await updateCampaign(campaign.id, { status: "active" });
      if (response.data) {
        fetchCampaigns();
      } else {
        setError(
          response.error || response.message || "Failed to start campaign",
        );
      }
    } catch (err) {
      if (!handleUpgradeError(err)) {
        setError("An error occurred while starting the campaign");
        console.error("Error starting campaign:", err);
      }
    }
  };

  const handlePauseCampaign = async (campaign: Campaign) => {
    try {
      setError(null);
      const response = await updateCampaign(campaign.id, { status: "paused" });
      if (response.data) {
        fetchCampaigns();
      } else {
        setError(
          response.error || response.message || "Failed to pause campaign",
        );
      }
    } catch (err) {
      setError("An error occurred while pausing the campaign");
      console.error("Error pausing campaign:", err);
    }
  };

  const handleBulkDelete = async (ids: string[]) => {
    if (!window.confirm(`Delete ${ids.length} campaign(s)? This cannot be undone.`)) {
      return;
    }

    setBulkLoading(true);
    let successCount = 0;
    const errors: string[] = [];

    try {
      for (const id of ids) {
        try {
          await deleteCampaign(id);
          successCount++;
        } catch (err) {
          errors.push(`Failed to delete campaign ${id}`);
        }
      }

      if (successCount > 0) {
        toast({
          title: "Campaigns deleted",
          description: `Successfully deleted ${successCount} campaign${successCount !== 1 ? 's' : ''}.`,
        });
        fetchCampaigns();
        setSelectedCampaignIds(new Set());
      }

      if (errors.length > 0) {
        setError(`${errors.length} deletion(s) failed. Please try again.`);
      }
    } catch (err) {
      setError("An error occurred while deleting campaigns");
      console.error("Error deleting campaigns:", err);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkPause = async (ids: string[]) => {
    setBulkLoading(true);
    let successCount = 0;

    try {
      for (const id of ids) {
        try {
          const response = await updateCampaign(id, { status: "paused" });
          if (response.data) {
            successCount++;
          }
        } catch (err) {
          console.error(`Failed to pause campaign ${id}:`, err);
        }
      }

      if (successCount > 0) {
        toast({
          title: "Campaigns paused",
          description: `Successfully paused ${successCount} campaign${successCount !== 1 ? 's' : ''}.`,
        });
        fetchCampaigns();
        setSelectedCampaignIds(new Set());
      }
    } catch (err) {
      setError("An error occurred while pausing campaigns");
      console.error("Error pausing campaigns:", err);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkStart = async (ids: string[]) => {
    setBulkLoading(true);
    let successCount = 0;

    try {
      for (const id of ids) {
        try {
          const response = await updateCampaign(id, { status: "active" });
          if (response.data) {
            successCount++;
          }
        } catch (err) {
          console.error(`Failed to start campaign ${id}:`, err);
        }
      }

      if (successCount > 0) {
        toast({
          title: "Campaigns started",
          description: `Successfully started ${successCount} campaign${successCount !== 1 ? 's' : ''}.`,
        });
        fetchCampaigns();
        setSelectedCampaignIds(new Set());
      }
    } catch (err) {
      setError("An error occurred while starting campaigns");
      console.error("Error starting campaigns:", err);
    } finally {
      setBulkLoading(false);
    }
  };

  const bulkActions: BulkAction[] = [
    {
      id: "start",
      label: "Start Selected",
      icon: <Icons.Play className="h-4 w-4" />,
      onClick: handleBulkStart,
      disabled: (ids) => {
        const selectedCampaigns = campaigns.filter((c) => ids.includes(c.id));
        return selectedCampaigns.every((c) => c.status === "active");
      },
    },
    {
      id: "pause",
      label: "Pause Selected",
      icon: <Icons.Pause className="h-4 w-4" />,
      onClick: handleBulkPause,
      disabled: (ids) => {
        const selectedCampaigns = campaigns.filter((c) => ids.includes(c.id));
        return selectedCampaigns.every((c) => c.status === "paused");
      },
    },
    {
      id: "delete",
      label: "Delete Selected",
      icon: <Icons.Trash2 className="h-4 w-4" />,
      variant: "destructive",
      onClick: handleBulkDelete,
    },
  ];

  const getStats = () => {
    const activeCount = campaigns.filter((c) => c.status === "active").length;
    const pausedCount = campaigns.filter((c) => c.status === "paused").length;
    const draftCount = campaigns.filter((c) => c.status === "draft").length;

    return {
      total: campaigns.length,
      active: activeCount,
      paused: pausedCount,
      draft: draftCount,
    };
  };

  const stats = getStats();

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
          <Skeleton className="h-10 w-32" />
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-8 w-full mb-2" />
                <Skeleton className="h-4 w-3/4" />
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i} className="h-48">
              <CardContent className="p-6">
                <Skeleton className="h-6 w-3/4 mb-4" />
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-5/6 mb-2" />
                <Skeleton className="h-4 w-4/6" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Breadcrumb
          items={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Campaigns', href: '/campaigns', isActive: true }
          ]}
        />

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Campaigns</h1>
            <p className="text-muted-foreground">
              Manage your outreach campaigns and track performance
            </p>
          </div>
          <PlanLimitButton resource="campaigns" onClick={() => setShowCreateForm(true)}>
            <Icons.Plus className="mr-2 h-4 w-4" />
            New Campaign
          </PlanLimitButton>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {selectedCampaignIds.size > 0 && (
        <BulkActionsToolbar
          selectedIds={selectedCampaignIds}
          totalItems={filteredCampaigns.length}
          onSelectAll={(selected) => {
            if (selected) {
              setSelectedCampaignIds(new Set(filteredCampaigns.map((c) => c.id)));
            } else {
              setSelectedCampaignIds(new Set());
            }
          }}
          onSelectNone={() => setSelectedCampaignIds(new Set())}
          actions={bulkActions}
          isLoading={bulkLoading}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Campaigns" value={stats.total} />
        <StatCard title="Active" value={stats.active} status="active" />
        <StatCard title="Paused" value={stats.paused} status="paused" />
        <StatCard title="Draft" value={stats.draft} status="draft" />
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search campaigns..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-sm"
          />
        </div>
        <div className="flex gap-2">
          <Tabs
            value={selectedTab}
            onValueChange={setSelectedTab}
            className="w-full sm:w-auto"
          >
            <TabsList>
              <TabsTrigger value="all">All ({campaigns.length})</TabsTrigger>
              <TabsTrigger value="active">Active ({stats.active})</TabsTrigger>
              <TabsTrigger value="paused">Paused ({stats.paused})</TabsTrigger>
              <TabsTrigger value="draft">Draft ({stats.draft})</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </div>

      {filteredCampaigns.length === 0 && !loading ? (
        <EmptyState
          title="No campaigns found"
          description={
            searchQuery
              ? "Try changing your search terms"
              : "Create your first campaign to get started"
          }
          action={
            <PlanLimitButton resource="campaigns" onClick={() => setShowCreateForm(true)}>
              <Icons.Plus className="mr-2 h-4 w-4" />
              Create Campaign
            </PlanLimitButton>
          }
        />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredCampaigns.map((campaign) => (
              <div key={campaign.id} className="relative">
                <CampaignCard
                  campaign={campaign}
                  onClick={() => handleCampaignClick(campaign)}
                  onEdit={handleEditCampaign}
                  onDelete={handleDeleteClick}
                  onStart={handleStartCampaign}
                  onPause={handlePauseCampaign}
                />
                <div
                  className="absolute top-3 left-3 cursor-pointer z-10"
                  onClick={(e) => {
                    e.stopPropagation();
                    const newSelected = new Set(selectedCampaignIds);
                    if (newSelected.has(campaign.id)) {
                      newSelected.delete(campaign.id);
                    } else {
                      newSelected.add(campaign.id);
                    }
                    setSelectedCampaignIds(newSelected);
                  }}
                >
                  <div
                    className={cn(
                      "w-5 h-5 border-2 border-gray-300 rounded transition-all",
                      selectedCampaignIds.has(campaign.id)
                        ? "bg-blue-600 border-blue-600"
                        : "hover:border-gray-400",
                    )}
                  >
                    {selectedCampaignIds.has(campaign.id) && (
                      <Icons.Check className="h-4 w-4 text-white" />
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <Dialog open={showCreateForm} onOpenChange={setShowCreateForm}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <CreateCampaignWizard
            onSuccess={(campaignId) => {
              setShowCreateForm(false);
              localStorage.setItem('first_campaign_banner_dismissed', '1');
              router.push(`/campaigns/${campaignId}`);
            }}
            onCancel={() => setShowCreateForm(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: number;
  status?: "active" | "paused" | "draft";
}

function StatCard({ title, value, status }: StatCardProps) {
  const getStatusColor = () => {
    switch (status) {
      case "active":
        return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";
      case "paused":
        return "bg-amber-500/10 text-amber-600 dark:text-amber-400";
      case "draft":
        return "bg-slate-500/10 text-slate-600 dark:text-slate-400";
      default:
        return "bg-blue-500/10 text-blue-600 dark:text-blue-400";
    }
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="text-3xl font-bold">{value}</div>
          {status && (
            <Badge
              variant="outline"
              className={cn("text-xs", getStatusColor())}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
