'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Icons } from '@/lib/types/components'
import { getCampaigns, createCampaign, updateCampaign, deleteCampaign } from '@/lib/api/dashboard'
import { Campaign } from '@/lib/types/components'
import { CampaignCard } from '@/components/dashboard/campaign-card'
import { CampaignForm } from '@/components/campaigns/campaign-form'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export default function CampaignsPage() {
  const router = useRouter()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTab, setSelectedTab] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null)

  const fetchCampaigns = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getCampaigns()
      if (response.data) {
        setCampaigns(response.data.data || [])
      } else {
        setError(response.error || response.message || 'Failed to fetch campaigns')
      }
    } catch (err) {
      setError('An error occurred while fetching campaigns')
      console.error('Error fetching campaigns:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      await fetchCampaigns()
    })()
  }, [fetchCampaigns])

  const filteredCampaigns = useMemo(() => {
    let filtered = [...campaigns]

    // Filter by tab
    if (selectedTab !== 'all') {
      filtered = filtered.filter(campaign => campaign.status === selectedTab)
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim()
      filtered = filtered.filter(
        campaign =>
          campaign.name.toLowerCase().includes(query) ||
          campaign.description?.toLowerCase().includes(query)
      )
    }

    return filtered
  }, [campaigns, selectedTab, searchQuery])

  const handleCreateCampaign = async (data: Partial<Campaign>) => {
    try {
      setError(null)
      const response = await createCampaign(data)
      if (response.data) {
        setShowCreateForm(false)
        fetchCampaigns() // Refresh list
      } else {
        setError(response.error || response.message || 'Failed to create campaign')
      }
    } catch (error) {
      setError('An error occurred while creating the campaign')
      console.error('Error creating campaign:', error)
    }
  }

  const handleUpdateCampaign = async (id: string, data: Partial<Campaign>) => {
    try {
      setError(null)
      const response = await updateCampaign(id, data)
      if (response.data) {
        setEditingCampaign(null)
        fetchCampaigns() // Refresh list
      } else {
        setError(response.error || response.message || 'Failed to update campaign')
      }
    } catch (error) {
      setError('An error occurred while updating the campaign')
      console.error('Error updating campaign:', error)
    }
  }

  const handleDeleteCampaign = async (campaign: Campaign) => {
    try {
      setError(null)
      const response = await deleteCampaign(campaign.id)
      if (response.data) {
        fetchCampaigns() // Refresh list
      } else {
        setError(response.error || response.message || 'Failed to delete campaign')
      }
    } catch (error) {
      console.error('Error deleting campaign:', error)
      setError('An error occurred while deleting the campaign')
    }
  }

  const handleCampaignClick = (campaign: Campaign) => {
    router.push(`/campaigns/${campaign.id}`)
  }

  const handleEditCampaign = (campaign: Campaign) => {
    setEditingCampaign(campaign)
  }

  const handleDeleteClick = (campaign: Campaign) => {
    handleDeleteCampaign(campaign)
  }

  const getStats = () => {
    const activeCount = campaigns.filter(c => c.status === 'active').length
    const pausedCount = campaigns.filter(c => c.status === 'paused').length
    const draftCount = campaigns.filter(c => c.status === 'draft').length

    return {
      total: campaigns.length,
      active: activeCount,
      paused: pausedCount,
      draft: draftCount,
    }
  }

  const stats = getStats()

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
          {[1, 2, 3, 4].map(i => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-8 w-full mb-2" />
                <Skeleton className="h-4 w-3/4" />
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
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
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Campaigns</h1>
          <p className="text-muted-foreground">
            Manage your outreach campaigns and track performance
          </p>
        </div>
        <Button onClick={() => setShowCreateForm(true)}>
          <Icons.Plus className="mr-2 h-4 w-4" />
          New Campaign
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
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
            onChange={e => setSearchQuery(e.target.value)}
            className="max-w-sm"
          />
        </div>
        <div className="flex gap-2">
          <Tabs value={selectedTab} onValueChange={setSelectedTab} className="w-full sm:w-auto">
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
          description={searchQuery ? 'Try changing your search terms' : 'Create your first campaign to get started'}
          action={
            <Button onClick={() => setShowCreateForm(true)}>
              <Icons.Plus className="mr-2 h-4 w-4" />
              Create Campaign
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCampaigns.map(campaign => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              onClick={() => handleCampaignClick(campaign)}
              onEdit={handleEditCampaign}
              onDelete={handleDeleteClick}
            />
          ))}
        </div>
      )}

      {showCreateForm && (
        <CampaignForm
          open={showCreateForm}
          onOpenChange={setShowCreateForm}
          onSubmit={handleCreateCampaign}
        />
      )}

      {editingCampaign && (
        <CampaignForm
          open={!!editingCampaign}
          onOpenChange={open => !open && setEditingCampaign(null)}
          campaign={editingCampaign}
          onSubmit={data => handleUpdateCampaign(editingCampaign.id, data)}
          isEditing
        />
      )}
    </div>
  )
}

interface StatCardProps {
  title: string
  value: number
  status?: 'active' | 'paused' | 'draft'
}

function StatCard({ title, value, status }: StatCardProps) {
  const getStatusColor = () => {
    switch (status) {
      case 'active':
        return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
      case 'paused':
        return 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
      case 'draft':
        return 'bg-slate-500/10 text-slate-600 dark:text-slate-400'
      default:
        return 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="text-3xl font-bold">{value}</div>
          {status && (
            <Badge variant="outline" className={cn('text-xs', getStatusColor())}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  )
}