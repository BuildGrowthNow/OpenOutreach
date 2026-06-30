'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Icons } from '@/lib/types/components'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { getCampaign, getCampaignAnalytics, getCampaignLeads, updateCampaign, deleteCampaign, getDailyUsage, uploadCampaignLeads, getCampaignStatus, getGhostModeSimulations, startGhostMode, stopGhostMode, createCampaignTemplate, addLeadToCampaign } from '@/lib/api/dashboard'
import { Campaign, Lead, CampaignTemplateCreateData } from '@/lib/types/components'
import { CampaignForm } from '@/components/campaigns/campaign-form'
import { CampaignStats as CampaignStatsComponent } from '@/components/campaigns/campaign-stats'
import { CampaignList as CampaignListComponent } from '@/components/campaigns/campaign-list'
import { DailyProgress } from '@/components/campaigns/daily-progress'
import { cn } from '@/lib/utils'
import { LinksManager } from '@/components/campaign/LinksManager'

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

interface GhostSimulationLog {
  id: number
  action_type: string
  target_name?: string
  target_url?: string
  result_data?: Record<string, unknown>
  rating?: number
  score?: number
  started_at?: string
  completed_at?: string
  simulated_action?: {
    type?: string
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
  const [showCompletionModal, setShowCompletionModal] = useState(false)
  
  const [dailyUsage, setDailyUsage] = useState<{
    dailyConnectionsSent: number
    dailyLimit: number
    effectiveLimit: number
    remaining: number
    rateLimitStatus: 'normal' | 'caution' | 'warning' | 'exceeded'
    warningMessage?: string
    warningLevel?: 'low' | 'medium' | 'high'
  }>({
    dailyConnectionsSent: 0,
    dailyLimit: 20,
    effectiveLimit: 20,
    remaining: 20,
    rateLimitStatus: 'normal',
    warningLevel: 'low',
  })
  const [ghostModeSimulations, setGhostModeSimulations] = useState<GhostSimulationLog[]>([])
  const [ghostModeLoading, setGhostModeLoading] = useState(false)
  const [ghostModeMode, setGhostModeMode] = useState<'simulation' | 'validation' | 'dry_run'>('simulation')
  const [ghostModeActive, setGhostModeActive] = useState<boolean>(false)

  // Lead upload and play/pause states
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<{ success: boolean; message: string } | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  
  // Save as Template states
  const [showSaveTemplateModal, setShowSaveTemplateModal] = useState(false)
  const [newTemplateName, setNewTemplateName] = useState('')
  const [newTemplateDescription, setNewTemplateDescription] = useState('')
  const [newTemplateIsPublic, setNewTemplateIsPublic] = useState(false)
  const [saveTemplateLoading, setSaveTemplateLoading] = useState(false)

  // Handle save as template
  const handleSaveAsTemplate = async () => {
    if (!campaign) return
    
    try {
      setSaveTemplateLoading(true)
      const templateData: CampaignTemplateCreateData = {
        name: newTemplateName.trim() || `${campaign.name} (Template)`,
        description: newTemplateDescription.trim() || campaign.description,
        campaign_objective: campaign.campaignObjective,
        ghost_mode_enabled: campaign.ghostModeEnabled,
        velocity: campaign.velocity,
        cooldown_minutes: campaign.cooldownMinutes,
        is_public: newTemplateIsPublic,
      }
      
      const response = await createCampaignTemplate(templateData)
      if (response.data) {
        setShowSaveTemplateModal(false)
        setNewTemplateName('')
        setNewTemplateDescription('')
        setNewTemplateIsPublic(false)
        // Optionally navigate to templates page
        router.push('/campaigns/templates')
      } else {
        setError(response.error || response.message || 'Failed to save template')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred while saving template')
    } finally {
      setSaveTemplateLoading(false)
    }
  }

  // Targeted polling state - only fetch status every 10 seconds
  const [campaignStatus, setCampaignStatus] = useState<string | null>(null)

  const fetchCampaignData = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true)
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

      // Fetch daily usage
      const dailyUsageResponse = await getDailyUsage()
      if (dailyUsageResponse.data) {
        setDailyUsage({
          dailyConnectionsSent: dailyUsageResponse.data.daily_connections_sent || 0,
          dailyLimit: dailyUsageResponse.data.daily_limit || 20,
          effectiveLimit: dailyUsageResponse.data.effective_limit || 20,
          remaining: dailyUsageResponse.data.remaining || 20,
          rateLimitStatus: dailyUsageResponse.data.rate_limit_status || 'normal',
          warningMessage: dailyUsageResponse.data.warning_message,
          warningLevel: dailyUsageResponse.data.warning_level,
        })
      }
    } catch (err) {
      setError('An error occurred while fetching campaign data')
      console.error('Error fetching campaign data:', err)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [campaignId])

  const refetchDailyUsage = useCallback(async () => {
    try {
      const dailyUsageResponse = await getDailyUsage()
      if (dailyUsageResponse.data) {
        setDailyUsage({
          dailyConnectionsSent: dailyUsageResponse.data.daily_connections_sent || 0,
          dailyLimit: dailyUsageResponse.data.daily_limit || 20,
          effectiveLimit: dailyUsageResponse.data.effective_limit || 20,
          remaining: dailyUsageResponse.data.remaining || 20,
          rateLimitStatus: dailyUsageResponse.data.rate_limit_status || 'normal',
          warningMessage: dailyUsageResponse.data.warning_message,
          warningLevel: dailyUsageResponse.data.warning_level,
        })
      }
    } catch (err) {
      console.error('Error fetching daily usage:', err)
    }
  }, [])

  const fetchGhostModeSimulations = useCallback(async () => {
    if (!campaignId) return
    try {
      setGhostModeLoading(true)
      const response = await getGhostModeSimulations(campaignId)
      if (response.data && Array.isArray(response.data.simulations)) {
        const simulations = response.data.simulations as GhostSimulationLog[]
        setGhostModeSimulations(simulations)
        // Only show as active if there are actual simulation entries
        if (simulations.length > 0) {
          setGhostModeActive(true)
        }
      }
    } catch (err) {
      console.error('Error fetching ghost mode simulations:', err)
    } finally {
      setGhostModeLoading(false)
    }
  }, [campaignId])

  useEffect(() => {
    void (async () => {
      await fetchCampaignData(false)
    })()
  }, [fetchCampaignData])

  // Targeted polling: fetch only status every 10 seconds
  // Full data is fetched only on initial load or manual refresh
  const fetchCampaignStatus = useCallback(async () => {
    try {
      const response = await getCampaignStatus(campaignId)
      if (response.data && typeof response.data === 'object' && 'status' in response.data) {
        const statusData = response.data as { status: string }
        if (statusData.status !== campaign?.status) {
          setCampaign((prev) => (prev ? { ...prev, status: statusData.status } : null))
        }
      }
    } catch (err) {
      console.error('Error fetching campaign status during polling:', err)
    }
  }, [campaignId, campaign])

  // Poll for status updates every 10 seconds (lightweight - single small API call)
  useEffect(() => {
    if (!campaignId) return
    const interval = setInterval(() => {
      void fetchCampaignStatus()
    }, 10000)
    return () => clearInterval(interval)
  }, [campaignId, fetchCampaignStatus])


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
      case 'completed':
        return 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
      default:
        return 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20'
    }
  }

  const handleMarkCompleted = async () => {
    if (!campaign) return
    try {
      setError(null)
      const response = await updateCampaign(campaign.id, { status: 'completed' })
      if (response.data) {
        setCampaign(response.data)
        setShowCompletionModal(false)
        fetchCampaignData()
      } else {
        setError(response.error || response.message || 'Failed to complete campaign')
      }
    } catch (err) {
      setError('An error occurred while completing the campaign')
      console.error('Error completing campaign:', err)
    }
  }

  const handlePauseCampaign = async () => {
    if (!campaign) return
    try {
      setActionLoading(true)
      setError(null)
      const response = await updateCampaign(campaign.id, { isPaused: true, status: 'paused' })
      if (response.data) {
        setCampaign(response.data)
        fetchCampaignData(true)
      } else {
        setError(response.error || 'Failed to pause campaign')
      }
    } catch (err) {
      setError('An error occurred while pausing the campaign')
    } finally {
      setActionLoading(false)
    }
  }

  const handleResumeCampaign = async () => {
    if (!campaign) return
    try {
      setActionLoading(true)
      setError(null)
      const response = await updateCampaign(campaign.id, { isPaused: false, status: 'active' })
      if (response.data) {
        setCampaign(response.data)
        fetchCampaignData(true)
      } else {
        setError(response.error || 'Failed to resume campaign')
      }
    } catch (err) {
      setError('An error occurred while resuming the campaign')
    } finally {
      setActionLoading(false)
    }
  }

  const handleUploadCSV = async () => {
    if (!uploadFile) return
    try {
      setUploadLoading(true)
      setUploadStatus(null)
      const response = await uploadCampaignLeads(campaignId, uploadFile)
      if (response.data) {
        setUploadStatus({
          success: true,
          message: `Successfully imported ${response.data.imported} leads! (Skipped/Existing: ${response.data.skipped})`
        })
        setUploadFile(null)
        // Reset file input element if possible
        const fileInput = document.getElementById('csv-file') as HTMLInputElement
        if (fileInput) fileInput.value = ''
        fetchCampaignData(true) // Refresh leads list in background
      } else {
        setUploadStatus({
          success: false,
          message: response.error || 'Failed to import connections'
        })
      }
    } catch (err) {
      setUploadStatus({
        success: false,
        message: err instanceof Error ? err.message : 'An error occurred during import'
      })
    } finally {
      setUploadLoading(false)
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
            The campaign you're looking for doesn't exist or you don't have permission to view it.
          </AlertDescription>
        </Alert>
        <Button onClick={() => router.push('/campaigns')}>
          <Icons.ChevronRight className="mr-2 h-4 w-4" />
          Back to Campaigns
        </Button>
      </div>
    )
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
  }

   const hasCompletedConnections = stats.connections_sent > 0
   const now = Date.now()
   const daysSinceStart = campaign.createdAt ? Math.ceil((now - new Date(campaign.createdAt).getTime()) / (1000 * 60 * 60 * 24)) : 1
   const avgDailyConnections = stats.connections_sent / Math.max(daysSinceStart, 1)

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
          <p className="text-muted-foreground">{campaign.description || <span className="text-muted-foreground italic">No description</span>}</p>
        </div>
        <div className="flex gap-2">
          {campaign.status === 'active' ? (
            <Button variant="outline" className="border-amber-500/20 text-amber-600 hover:bg-amber-500/10 dark:text-amber-400" onClick={handlePauseCampaign} disabled={actionLoading}>
              <Icons.Pause className="mr-2 h-4 w-4" />
              Pause
            </Button>
          ) : campaign.status === 'paused' ? (
            <Button variant="outline" className="border-emerald-500/20 text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400" onClick={handleResumeCampaign} disabled={actionLoading}>
              <Icons.Play className="mr-2 h-4 w-4" />
              Resume
            </Button>
          ) : campaign.status === 'draft' ? (
            <Button variant="outline" className="border-emerald-500/20 text-emerald-600 hover:bg-emerald-500/10 dark:text-emerald-400" onClick={handleResumeCampaign} disabled={actionLoading}>
              <Icons.Play className="mr-2 h-4 w-4" />
              Start
            </Button>
          ) : null}
          <Button variant="outline" onClick={handleSaveAsTemplate}>
            <Icons.Save className="mr-2 h-4 w-4" />
            Save as Template
          </Button>
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
        <TabsList className="grid grid-cols-6 w-full md:w-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="leads">Leads</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="links">Links</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="ghost-mode">Safe Test Mode</TabsTrigger>
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
                                 <p className="font-medium">{(lead as { name?: string }).name || <span className="text-muted-foreground italic">Unnamed Lead</span>}</p>
                                 <p className="text-sm text-muted-foreground">
                                   {(lead as { company?: string }).company || <span className="text-muted-foreground italic">Unnamed Lead</span>}
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
              {/* Daily Progress */}
              <Card>
                <CardHeader>
                  <CardTitle>Daily Progress</CardTitle>
                  <CardDescription>Today's velocity tracking</CardDescription>
                </CardHeader>
                <CardContent>
                  <DailyProgress 
                    dailyConnectionsSent={dailyUsage.dailyConnectionsSent} 
                    dailyLimit={dailyUsage.dailyLimit}
                    effectiveLimit={dailyUsage.effectiveLimit}
                  />
                  {/* Show warning banner if limit is exceeded or approaching */}
                  {dailyUsage.rateLimitStatus === 'exceeded' && (
                    <div className="mt-4 rounded-md bg-destructive/10 border border-destructive/20 p-3">
                      <div className="flex items-start gap-3">
                        <Icons.AlertTriangle className="h-5 w-5 text-destructive mt-0.5" />
                        <div>
                          <h5 className="font-medium text-destructive">Daily Connection Limit Exceeded</h5>
                          <p className="text-sm text-destructive/80 mt-1">
                            {dailyUsage.warningMessage || 'You have reached your daily connection limit. No more connections can be sent today.'}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  {dailyUsage.rateLimitStatus === 'warning' && (
                    <div className="mt-4 rounded-md bg-amber-500/10 border border-amber-500/20 p-3">
                      <div className="flex items-start gap-3">
                        <Icons.AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5" />
                        <div>
                          <h5 className="font-medium text-amber-600 dark:text-amber-400">Approaching Rate Limit</h5>
                          <p className="text-sm text-amber-600/80 dark:text-amber-400/80 mt-1">
                            {dailyUsage.warningMessage || 'You are approaching your daily connection limit.'}
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
                      <span className="text-sm text-muted-foreground">Status</span>
                      <Badge variant="outline" className={cn(getStatusColor(campaign.status))}>
                        {campaign.status}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Daily Connection Limit</span>
                      <span className="font-medium">{campaign.velocity} connections/day</span>
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
                  {campaign.status !== 'completed' && (
                    <Dialog open={showCompletionModal} onOpenChange={setShowCompletionModal}>
                      <DialogTrigger asChild>
                        <Button variant="default" className="w-full justify-start bg-emerald-600 hover:bg-emerald-700">
                          <Icons.Check className="mr-2 h-4 w-4" />
                          Mark as Completed
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Complete Campaign</DialogTitle>
                          <DialogDescription>
                            Are you sure you want to mark this campaign as completed? This action cannot be undone.
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <div className="text-sm text-muted-foreground">Total Connections Sent</div>
                              <div className="text-2xl font-bold">{stats.connections_sent}</div>
                            </div>
                            <div className="space-y-2">
                              <div className="text-sm text-muted-foreground">Connection Accept Rate</div>
                              <div className="text-2xl font-bold">{stats.connection_accept_rate >= 0 ? stats.connection_accept_rate.toFixed(1) : '0.0'}%</div>
                            </div>
                            <div className="space-y-2">
                              <div className="text-sm text-muted-foreground">Messages Sent</div>
                              <div className="text-2xl font-bold">{stats.messages_sent}</div>
                            </div>
                            <div className="space-y-2">
                              <div className="text-sm text-muted-foreground">Conversions</div>
                              <div className="text-2xl font-bold">{stats.conversions}</div>
                            </div>
                          </div>
                          <div className="border-t pt-4">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-medium">Overall ROI Summary</span>
                              <span className="font-bold">
                                {stats.connection_accept_rate > 0 
                                  ? `${stats.conversions} conversions from ${stats.connections_sent} connections`
                                  : 'No connection data yet'}
                              </span>
                            </div>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setShowCompletionModal(false)}>
                            Cancel
                          </Button>
                          <Button variant="destructive" onClick={handleMarkCompleted}>
                            Yes, Complete Campaign
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
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
                <CardDescription>All leads associated with this campaign</CardDescription>
              </div>
              <Dialog open={showUploadModal} onOpenChange={setShowUploadModal}>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Icons.Download className="mr-2 h-4 w-4 rotate-180" />
                    Import Connections (CSV)
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Import Connections (CSV)</DialogTitle>
                    <DialogDescription>
                      Upload a CSV file containing LinkedIn profiles or connection URLs to add as campaign leads.
                      The CSV should have one profile URL or public identifier per line (or a header row starting with firstName/lastName).
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="flex flex-col gap-2">
                      <label htmlFor="csv-file" className="text-sm font-medium">Select CSV File</label>
                      <Input 
                        id="csv-file"
                        type="file" 
                        accept=".csv"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null;
                          if (file && !file.name.toLowerCase().endsWith('.csv')) {
                            setUploadStatus({ success: false, message: 'Please select a valid CSV file (.csv)' });
                            setUploadFile(null);
                          } else {
                            setUploadFile(file);
                            setUploadStatus(null);
                          }
                        }}
                      />
                      {uploadStatus && !uploadStatus.success && (
                        <Alert variant="destructive">
                          <AlertDescription>{uploadStatus.message}</AlertDescription>
                        </Alert>
                      )}
                    </div>
                    {uploadStatus && (
                      <Alert variant={uploadStatus.success ? "default" : "destructive"}>
                        <AlertTitle>{uploadStatus.success ? "Success" : "Error"}</AlertTitle>
                        <AlertDescription>{uploadStatus.message}</AlertDescription>
                      </Alert>
                    )}
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => { setShowUploadModal(false); setUploadStatus(null); setUploadFile(null); }}>
                      Cancel
                    </Button>
                    <Button onClick={handleUploadCSV} disabled={!uploadFile || uploadLoading}>
                      {uploadLoading ? "Importing..." : "Import"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
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

        {/* Ghost Mode Tab */}
        <TabsContent value="ghost-mode" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Ghost Mode Simulation</CardTitle>
              <CardDescription>
                Simulate campaign behavior without actually connecting to LinkedIn
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Toggle for Ghost Mode */}
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="space-y-1">
                    <h4 className="font-medium">Ghost Mode Status</h4>
                    <p className="text-sm text-muted-foreground">
                      {ghostModeActive 
                        ? "Ghost mode is currently active" 
                        : "Ghost mode is currently inactive"}
                    </p>
                  </div>
                  <Button
                    variant={ghostModeActive ? "destructive" : "default"}
                    onClick={async () => {
                      if (ghostModeActive) {
                        await stopGhostMode(campaignId)
                        setGhostModeActive(false)
                        fetchGhostModeSimulations()
                      } else {
                        await startGhostMode(campaignId)
                        setGhostModeActive(true)
                        fetchGhostModeSimulations()
                      }
                    }}
                    disabled={ghostModeLoading}
                  >
                    {ghostModeActive 
                      ? (
                          <>
                            <Icons.X className="mr-2 h-4 w-4" />
                            Stop Simulation
                          </>
                        ) 
                      : (
                          <>
                            <Icons.Zap className="mr-2 h-4 w-4" />
                            Start Simulation
                          </>
                        )}
                  </Button>
                </div>

                {/* Simulations Data */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">Simulation Logs</h4>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => fetchGhostModeSimulations()}
                      disabled={ghostModeLoading}
                    >
                      <Icons.RefreshCw className={`mr-2 h-4 w-4 ${ghostModeLoading ? 'animate-spin' : ''}`} />
                      Refresh
                    </Button>
                  </div>
                  
                  {ghostModeLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-12 w-full" />
                      <Skeleton className="h-12 w-full" />
                      <Skeleton className="h-12 w-full" />
                    </div>
                  ) : ghostModeSimulations.length > 0 ? (
                    <div className="space-y-3">
                      {ghostModeSimulations.slice(0, 10).map((sim: GhostSimulationLog) => (
                        <div key={sim.id} className="p-4 border rounded-lg bg-muted/30 space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-xs">
                                {sim.action_type}
                              </Badge>
                              {sim.rating && (
                                <Badge className="text-xs" variant={
                                      sim.rating >= 4 ? "default" : 
                                      sim.rating >= 3 ? "secondary" : "destructive"
                                    }>
                                    Rating: {sim.rating}/5
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {new Date(sim.completed_at || '').toLocaleString()}
                            </span>
                          </div>
                          <div className="text-sm">
                            {sim.target_name && (
                              <div className="font-medium">{sim.target_name}</div>
                            )}
                            {sim.target_url && (
                              <a 
                                href={sim.target_url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="text-sm text-blue-500 hover:underline"
                              >
                                {sim.target_url}
                              </a>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {sim.simulated_action?.type && (
                              <div>Action: {sim.simulated_action.type}</div>
                            )}
                            {typeof sim.score === 'number' && (
                              <div>Score: {sim.score}</div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 border border-dashed rounded-lg">
                      <Icons.Activity className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                      <h3 className="text-lg font-semibold mb-2">No Simulation Data</h3>
                      <p className="text-sm text-muted-foreground mb-4">
                        Start a ghost mode simulation to see simulated activity logs here.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Links Tab */}
        <TabsContent value="links" className="space-y-6">
          <LinksManager campaignId={campaignId} />
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
                    <h4 className="font-medium mb-2">Connection Settings</h4>
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

      {/* Save as Template Modal */}
      <Dialog open={showSaveTemplateModal} onOpenChange={setShowSaveTemplateModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Campaign as Template</DialogTitle>
            <DialogDescription>
              Save this campaign configuration as a reusable template
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label htmlFor="template-name" className="text-sm font-medium">Template Name</label>
              <Input
                id="template-name"
                value={newTemplateName}
                onChange={e => setNewTemplateName(e.target.value)}
                placeholder="Enter template name"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="template-description" className="text-sm font-medium">Description</label>
              <Input
                id="template-description"
                value={newTemplateDescription}
                onChange={e => setNewTemplateDescription(e.target.value)}
                placeholder="Brief description of the template"
              />
            </div>
            <div className="flex items-center space-x-2 p-3 rounded-lg border">
              <Switch
                checked={newTemplateIsPublic}
                onCheckedChange={setNewTemplateIsPublic}
              />
              <div className="space-y-0.5">
                <label className="text-sm font-medium">Public Template</label>
                <p className="text-xs text-muted-foreground">
                  Make this template available to all team members
                </p>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveTemplateModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveAsTemplate} disabled={saveTemplateLoading}>
              {saveTemplateLoading ? 'Saving...' : 'Save Template'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
