'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { LayoutDashboard, Activity, RefreshCw, AlertCircle, Plus } from 'lucide-react'
import { StatsCard } from '@/components/dashboard/stats-card'
import { RecentActivity } from '@/components/dashboard/recent-activity'
import { CampaignPipeline } from '@/components/dashboard/campaign-pipeline'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useDashboard } from '@/hooks/use-dashboard'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { getAnalyticsOverview, AnalyticsOverviewResponse, RecentActivityEntry } from '@/lib/api/dashboard'

function toActivityItems(entries: RecentActivityEntry[]) {
  return entries.map((e) => {
    const nameClause = e.leadName ? `: ${e.leadName}` : ''
    const campaignClause = e.campaignName ? ` (${e.campaignName})` : ''

    let description = e.type.replace(/_/g, ' ')
    if (e.type === 'connect') description = `Connection sent${nameClause}${campaignClause}`
    else if (e.type === 'follow_up') description = `Follow-up sent${nameClause}${campaignClause}`
    else if (e.type === 'check_pending') description = `Pending check${nameClause}${campaignClause}`
    else if (e.type === 'lead_discovered') description = `Lead discovered${nameClause}${campaignClause}`
    else if (e.type === 'lead_qualified') description = `Lead qualified${nameClause}${campaignClause}`
    else if (e.type === 'lead_disqualified') description = `Lead disqualified${nameClause}${campaignClause}`
    else if (e.type === 'campaign_started') description = `Campaign started${campaignClause}`
    else if (e.type === 'campaign_paused') description = `Campaign paused${campaignClause}`

    const status: 'success' | 'pending' | 'failed' =
      e.status === 'failed' || !!e.error ? 'failed'
      : e.status === 'pending' ? 'pending'
      : 'success'

    const iconMap: Record<string, string> = {
      connect: 'connection_sent',
      follow_up: 'message_sent',
      check_pending: 'connection_accepted',
      lead_discovered: 'new_lead',
      lead_qualified: 'deal_completed',
      lead_disqualified: 'deal_failed',
    }

    return {
      id: e.id,
      type: iconMap[e.type] || e.type,
      description,
      timestamp: e.timestamp,
      status,
    }
  })
}

// Helper to round to 1 decimal place
function roundTo1(value: number): string {
  return (Math.round(value * 10) / 10).toFixed(1)
}

const Dashboard = () => {
  const router = useRouter()
  const {
    campaigns,
    campaignsLoading,
    campaignsError,
    fetchCampaigns,
    healthStatus,
    healthLoading,
    fetchHealth,
    recentActivity,
    recentActivityLoading,
    fetchRecentActivity,
  } = useDashboard()

  const [refreshing, setRefreshing] = useState(false)
  const [overview, setOverview] = useState<AnalyticsOverviewResponse | null>(null)
  const [overviewLoading, setOverviewLoading] = useState(true)

  useEffect(() => {
    fetchHealth()
    fetchCampaigns('active')
    fetchRecentActivity()
    getAnalyticsOverview(undefined, '30d').then((res) => {
      if (res.data) setOverview(res.data)
    }).finally(() => setOverviewLoading(false))
  }, [fetchHealth, fetchCampaigns, fetchRecentActivity])

  const systemStatus = healthStatus
    ? (healthStatus.status === 'operational' ? 'operational' : 'degraded')
    : 'operational'

  const handleRefresh = async () => {
    setRefreshing(true)
    setOverviewLoading(true)
    try {
      await Promise.all([
        fetchCampaigns('active'),
        fetchHealth(),
        fetchRecentActivity(),
        getAnalyticsOverview(undefined, '30d').then((res) => {
          if (res.data) setOverview(res.data)
        }),
      ])
    } finally {
      setRefreshing(false)
      setOverviewLoading(false)
    }
  }

  const totals = overview?.totals
  const stats = overview?.stats
  const pipeline = overview?.pipeline

  const totalLeads = totals?.leads ?? 0
  const connected = totals?.connected ?? 0
  const connectionsSent = stats?.connectionsSent ?? 0
  const connectionsAccepted = stats?.connectionsAccepted ?? 0
  const messagesSent = stats?.messagesSent ?? 0
  const messagesReplied = stats?.messagesReplied ?? 0

  const connectionRate = totalLeads > 0 ? `${roundTo1((connected / totalLeads) * 100)}%` : '—'
  const acceptRate = connectionsSent > 0 ? `${roundTo1((connectionsAccepted / connectionsSent) * 100)}%` : '—'
  const replyRate = messagesSent > 0 ? `${roundTo1((messagesReplied / messagesSent) * 100)}%` : '—'

  const isLoading = campaignsLoading || healthLoading || overviewLoading

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={`px-3 py-1 cursor-pointer ${
              systemStatus === 'operational' ? 'text-emerald-600 border-emerald-600' :
              'text-amber-600 border-amber-600'
            }`}
            onClick={() => router.push('/health')}
          >
            <Activity className="mr-2 h-3.5 w-3.5" />
            {systemStatus === 'operational' ? 'System Operational' : 'System Degraded'}
          </Badge>
          <Button size="sm" onClick={handleRefresh} disabled={refreshing} variant="outline">
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button size="sm" onClick={() => router.push('/campaigns')}>
            <Plus className="mr-2 h-4 w-4" />
            New Campaign
          </Button>
        </div>
      </div>

      {campaignsError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{campaignsError}</AlertDescription>
        </Alert>
      )}

      {/* Stat cards */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-2" />
                <Skeleton className="h-3 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatsCard
            title="Active Campaigns"
            value={campaigns.length}
            icon="LayoutDashboard"
            description="Running right now"
          />
          <StatsCard
            title="Total Leads"
            value={totalLeads}
            icon="Users"
            description="All campaigns, 30 days"
          />
          <StatsCard
            title="Connected"
            value={connected}
            icon="Users"
            description={`Connection rate ${connectionRate}`}
          />
          <StatsCard
            title="Messages Sent"
            value={messagesSent}
            icon="MessageSquare"
            description={`Reply rate ${replyRate}`}
          />
        </div>
      )}

      {/* Pipeline + Activity */}
      <div className="grid gap-6 md:grid-cols-2">
        {overviewLoading ? (
          <Card>
            <CardHeader><Skeleton className="h-5 w-32" /></CardHeader>
            <CardContent className="space-y-3">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
            </CardContent>
          </Card>
        ) : pipeline ? (
          <CampaignPipeline
            qualified={pipeline.qualified}
            readyToConnect={pipeline.ready_to_connect}
            pending={pipeline.pending}
            connected={pipeline.connected}
            completed={pipeline.completed}
            failed={pipeline.failed}
            noEmail={pipeline.no_email}
          />
        ) : null}

        <RecentActivity
          items={recentActivityLoading ? [] : toActivityItems(recentActivity)}
        />
      </div>

      {/* Key metrics row */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">30-Day Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">Connections Sent</div>
              <div className="text-2xl font-bold">{connectionsSent}</div>
            </div>
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">Accept Rate</div>
              <div className="text-2xl font-bold">{acceptRate}</div>
            </div>
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">Reply Rate</div>
              <div className="text-2xl font-bold">{replyRate}</div>
            </div>
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">Connection Rate</div>
              <div className="text-2xl font-bold">{connectionRate}</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Dashboard
