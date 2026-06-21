'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { getCampaign, getCampaignAnalytics, getCampaignLeads, updateCampaign, deleteCampaign } from '@/lib/api/dashboard'
import { Campaign, Lead } from '@/lib/types/components'
import { CampaignForm } from '@/components/campaigns/campaign-form'
import { CampaignStats as CampaignStatsComponent } from '@/components/campaigns/campaign-stats'
import { CampaignList as CampaignListComponent } from '@/components/campaigns/campaign-list'
import { cn } from '@/lib/utils'

interface CampaignAnalyticsResponse {
  stats: {
    connections_sent: number
    connections_accepted: number
    messages_sent: number
    messages_replied: number
    conversions: number
    connection_accept_rate: number
    response_rate: number
    conversion_rate: number
    errors: number
    rate_limit_warnings: number
  }
}

export default function CampaignDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const campaignId = params.id as string

  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [analytics, setAnalytics] = useState<CampaignAnalyticsResponse | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const fetchCampaignData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch campaign details
      const campaignResponse = await getCampaign(campaignId)
      if (campaignResponse.data) {
        setCampaign(campaignResponse.data!)
      } else {
        setError(campaignResponse.error || campaignResponse.message || 'Failed to fetch campaign')
      }

      // Fetch campaign analytics
      const analyticsResponse = await getCampaignAnalytics(campaignId)
      if (analyticsResponse.data) {
        setAnalytics(analyticsResponse.data)
      }

      // Fetch campaign leads
      const leadsResponse = await getCampaignLeads(campaignId)
      if (leadsResponse.data) {
        setLeads(leadsResponse.data.data || [])
      }
    } catch (err) {
      setError('An error occurred while fetching campaign data')
      console.error('Error fetching campaign data:', err)
    } finally {
      setLoading(false)
    }
  }, [campaignId])

  useEffect(() => {
    void (async () => {
      await fetchCampaignData()
    })()
  }, [fetchCampaignData])

  const handleUpdateCampaign = async (data: Partial<Campaign>) => {
    try {
      if (!campaign) return
      
      setError(null)
      const response = await updateCampaign(campaign.id, data)
      if (response.data) {
        setEditing(false)
        fetchCampaignData() // Refresh data
      } else {
        setError(response.error || response.message || 'Failed to update campaign')
      }
    } catch (error) {
      setError('An error occurred while updating the campaign')
      console.error('Error updating campaign:', error)
    }
  }

  const handleDeleteCampaign = async () => {
    if (!campaign) return

    try {
      setDeleting(true)
      const response = await deleteCampaign(campaign.id)
      if (response.data) {
        router.push('/campaigns')
      } else {
        setError(response.error || response.message || 'Failed to delete campaign')
      }
    } catch (error) {
      console.error('Error deleting campaign:', error)
      setError('An error occurred while deleting the campaign')
    } finally {
      setDeleting(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
      case 'paused':
        return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
      case 'draft':
        return 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20'
      default:
        return 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20'
    }
  }

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
    )
  }

  if (!campaign) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive">
          <AlertTitle>Campaign Not Found</AlertTitle>
          <AlertDescription>
            The campaign you&apos;re looking for doesn&apos;t exist or you don&apos;t have permission to view it.
          </AlertDescription>
        </Alert>
        <Button onClick={() => router.push('/campaigns')}>
          <Icons.ChevronRight className="mr-2 h-4 w-4" />
          Back to Campaigns
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{campaign.name}</h1>
            <Badge variant="outline" className={cn('text-xs', getStatusColor(campaign.status))}>
              {campaign.status.charAt(0).toUpperCase() + campaign.status.slice(1)}
            </Badge>
          </div>
          <p className="text-muted-foreground">{campaign.description || 'No description'}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditing(true)}>
            <Icons.Edit className="mr-2 h-4 w-4" />
            Edit
          </Button>
          <Button variant="destructive" onClick={handleDeleteCampaign} disabled={deleting}>
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
                  <CardDescription>Performance metrics for this campaign</CardDescription>
                </CardHeader>
                <CardContent>
                  {analytics ? (
                    <CampaignStatsComponent stats={analytics.stats} />
                  ) : (
                    <div className="space-y-4">
                      <Skeleton className="h-32 w-full" />
                      <Skeleton className="h-24 w-full" />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Recent Activity */}
              <Card>
                <CardHeader>
                  <CardTitle>Recent Activity</CardTitle>
                  <CardDescription>Latest actions and updates</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {leads.length > 0 ? (
                      <div className="space-y-2">
                        {leads.slice(0, 5).map((lead) => (
                          <div
                            key={(lead as { id?: string }).id}
                            className="flex items-center justify-between p-3 rounded-lg border"
                          >
                            <div className="flex items-center gap-3">
                              <div className="h-2 w-2 rounded-full bg-emerald-500" />
                              <div>
                                <p className="font-medium">{(lead as { name?: string }).name || 'Unnamed Lead'}</p>
                                <p className="text-sm text-muted-foreground">
                                  {(lead as { company?: string }).company || 'No company'}
                                </p>
                              </div>
                            </div>
                            <Badge variant="outline">{(lead as { state?: string }).state}</Badge>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-8">
                        <p className="text-muted-foreground">No recent activity</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              {/* Campaign Details */}
              <Card>
                <CardHeader>
                  <CardTitle>Campaign Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Status</span>
                      <Badge variant="outline" className={cn(getStatusColor(campaign.status))}>
                        {campaign.status}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Daily Velocity</span>
                      <span className="font-medium">{campaign.velocity} connects/day</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Cooldown</span>
                      <span className="font-medium">{campaign.cooldownMinutes} minutes</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Freemium</span>
                      <span className="font-medium">{campaign.isFreemium ? 'Yes' : 'No'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Created</span>
                      <span className="font-medium">
                        {new Date(campaign.createdAt).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Last Updated</span>
                      <span className="font-medium">
                        {new Date(campaign.updatedAt).toLocaleDateString()}
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
                  <Button variant="outline" className="w-full justify-start" onClick={() => router.push(`/campaigns/${campaignId}/leads`)}>
                    <Icons.Users className="mr-2 h-4 w-4" />
                    View All Leads
                  </Button>
                  <Button variant="outline" className="w-full justify-start" onClick={() => router.push(`/campaigns/${campaignId}/analytics`)}>
                    <Icons.BarChart3 className="mr-2 h-4 w-4" />
                    View Analytics
                  </Button>
                  <Button variant="outline" className="w-full justify-start" onClick={() => router.push(`/campaigns/${campaignId}/state-machine`)}>
                    <Icons.ListTodo className="mr-2 h-4 w-4" />
                    State Machine
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Leads Tab */}
        <TabsContent value="leads" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Leads</CardTitle>
              <CardDescription>All leads associated with this campaign</CardDescription>
            </CardHeader>
            <CardContent>
              {leads.length > 0 ? (
                <CampaignListComponent leads={leads} campaignId={campaignId} />
              ) : (
                <div className="text-center py-12">
                  <Icons.Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No Leads Yet</h3>
                  <p className="text-sm text-muted-foreground mb-6">
                    Start adding leads to this campaign to see them here.
                  </p>
                  <Button onClick={() => router.push('/leads')}>
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
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Performance Metrics</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold">{analytics.stats?.connections_sent || 0}</div>
                      <div className="text-sm text-muted-foreground">Connections Sent</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">{analytics.stats?.connections_accepted || 0}</div>
                      <div className="text-sm text-muted-foreground">Connections Accepted</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">{analytics.stats?.messages_sent || 0}</div>
                      <div className="text-sm text-muted-foreground">Messages Sent</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">{analytics.stats?.conversions || 0}</div>
                      <div className="text-sm text-muted-foreground">Conversions</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Additional analytics content would go here */}
              <div className="text-center py-12">
                <p className="text-muted-foreground">Advanced analytics charts and visualizations will be implemented in Phase 6</p>
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-muted-foreground">No analytics data available yet</p>
            </div>
          )}
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Settings</CardTitle>
              <CardDescription>Configure campaign parameters and behavior</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2">Velocity Settings</h4>
                    <p className="text-sm text-muted-foreground">
                      Daily: {campaign.velocity} connections<br />
                      Cooldown: {campaign.cooldownMinutes} minutes
                    </p>
                  </div>
                  <div>
                    <h4 className="font-medium mb-2">Campaign Type</h4>
                    <p className="text-sm text-muted-foreground">
                      {campaign.isFreemium ? 'Freemium Model' : 'Standard Model'}
                    </p>
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2">Links</h4>
                    <p className="text-sm text-muted-foreground">
                      {campaign.bookingLink ? (
                        <a href={campaign.bookingLink} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                          Booking Link
                        </a>
                      ) : (
                        'No booking link'
                      )}
                      <br />
                      {campaign.productDocs ? (
                        <a href={campaign.productDocs} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                          Product Docs
                        </a>
                      ) : (
                        'No product docs'
                      )}
                    </p>
                  </div>
                  <div>
                    <h4 className="font-medium mb-2">Objective</h4>
                    <p className="text-sm text-muted-foreground">
                      {campaign.campaignObjective || 'No objective set'}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {editing && (
        <CampaignForm
          open={editing}
          onOpenChange={setEditing}
          campaign={campaign}
          onSubmit={handleUpdateCampaign}
          isEditing
        />
      )}
    </div>
  )
}
