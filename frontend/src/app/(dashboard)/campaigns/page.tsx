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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Breadcrumb } from "@/components/layout/breadcrumb";
import { PlanLimitButton } from "@/components/billing/plan-limit-button";
import { useUpgradeToast } from "@/lib/hooks/use-upgrade-toast";

export default function CampaignsPage() {
  const router = useRouter();
  const handleUpgradeError = useUpgradeToast();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [campaignToDelete, setCampaignToDelete] = useState<Campaign | null>(null);

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

    if (selectedTab !== "all") {
      filtered = filtered.filter((campaign) => campaign.status === selectedTab);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter((campaign) =>
        campaign.name.toLowerCase().includes(query),
      );
    }

    return filtered;
  }, [campaigns, selectedTab, searchQuery]);

  const handleDeleteCampaign = (campaign: Campaign) => {
    setCampaignToDelete(campaign);
  };

  const confirmDeleteCampaign = async () => {
    if (!campaignToDelete) return;
    const target = campaignToDelete;
    setCampaignToDelete(null);
    setError(null);
    const result = await deleteCampaign(target.id);
    if (result.error) {
      setError(result.error);
      return;
    }
    fetchCampaigns();
  };

  const handleStartCampaign = async (campaign: Campaign) => {
    try {
      setError(null);
      const response = await updateCampaign(campaign.id, { status: "active" });
      if (response.data) {
        fetchCampaigns();
      } else {
        setError(response.error || response.message || "Failed to start campaign");
      }
    } catch (err) {
      if (!handleUpgradeError(err)) {
        setError("An error occurred while starting the campaign");
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
        setError(response.error || response.message || "Failed to pause campaign");
      }
    } catch (err) {
      setError("An error occurred while pausing the campaign");
    }
  };

  const handleEditCampaign = (campaign: Campaign) => {
    router.push(`/campaigns/${campaign.id}?tab=settings`);
  };

  const stats = useMemo(() => ({
    total: campaigns.length,
    active: campaigns.filter((c) => c.status === "active").length,
    paused: campaigns.filter((c) => c.status === "paused").length,
    draft: campaigns.filter((c) => c.status === "draft").length,
  }), [campaigns]);

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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="h-52">
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

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search campaigns..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-sm"
          />
        </div>
        <Tabs
          value={selectedTab}
          onValueChange={setSelectedTab}
          className="w-full sm:w-auto"
        >
          <TabsList>
            <TabsTrigger value="all">All ({stats.total})</TabsTrigger>
            <TabsTrigger value="active">Active ({stats.active})</TabsTrigger>
            <TabsTrigger value="paused">Paused ({stats.paused})</TabsTrigger>
            <TabsTrigger value="draft">Draft ({stats.draft})</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {filteredCampaigns.length === 0 ? (
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCampaigns.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              onClick={() => router.push(`/campaigns/${campaign.id}`)}
              onEdit={handleEditCampaign}
              onDelete={handleDeleteCampaign}
              onStart={handleStartCampaign}
              onPause={handlePauseCampaign}
            />
          ))}
        </div>
      )}

      <Dialog open={!!campaignToDelete} onOpenChange={(open) => { if (!open) setCampaignToDelete(null); }}>
        <DialogContent className="sm:max-w-[420px]">
          <DialogHeader>
            <DialogTitle>Delete Campaign</DialogTitle>
            <DialogDescription>
              This will permanently delete &quot;{campaignToDelete?.name}&quot; along with all its leads, deals, and conversation history. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCampaignToDelete(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDeleteCampaign}>
              Delete Campaign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
