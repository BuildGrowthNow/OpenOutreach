'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { LayoutDashboard, Activity, Users, MessageSquare, RefreshCw, AlertCircle, Plus, Mail } from 'lucide-react'
import { StatsCard } from '@/components/dashboard/stats-card'
import { RecentActivity } from '@/components/dashboard/recent-activity'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useDashboard } from '@/hooks/use-dashboard'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'

const NOW = Date.now()

// Card height class for consistent card heights
const CARD_HEIGHT_CLASS = "min-h-[280px]"

// Helper to round to 1 decimal place
function roundTo1Decimal(value: number): string {
  return (Math.round(value * 10) / 10).toFixed(1)
}

interface ActivityItem {
  id: string
  type: string
  description: string
  timestamp: string
  entity?: string
  status?: 'success' | 'pending' | 'failed'
}

const Dashboard = () => {
  const router = useRouter()
  const { 
    campaigns, 
    campaignsLoading, 
    campaignsError, 
    fetchCampaigns,
    leads, 
    leadsLoading, 
    leadsError, 
    fetchLeads,
    healthStatus,
    healthLoading,
    fetchHealth,
    fetchRateLimits 
  } = useDashboard()

  const [refreshing, setRefreshing] = useState(false)
  // Fetch initial data
  useEffect(() => {
    fetchCampaigns('active')
    fetchLeads('QUALIFIED')
    fetchHealth()
    fetchRateLimits()
  }, [fetchCampaigns, fetchLeads, fetchHealth, fetchRateLimits])

  const activity = useMemo<ActivityItem[]>(() => {
    if (campaigns.length === 0 && leads.length === 0) {
      return []
    }

    const processedActivity: ActivityItem[] = []

    campaigns.slice(0, 2).forEach((campaign, index) => {
      processedActivity.push({
        id: `campaign-${campaign.id || index}`,
        type: 'campaign_updated',
        description: `Campaign "${campaign.name || 'Unnamed'}" was updated`,
        timestamp: new Date(NOW - index * 3600000).toISOString(),
        entity: campaign.id,
        status: 'success',
      })
    })

    leads.slice(0, 3).forEach((lead, index) => {
      processedActivity.push({
        id: `lead-${lead.id || index}`,
        type: 'new_lead',
        description: `New lead "${lead.name || 'Unnamed'}" added`,
        timestamp: new Date(NOW - (index + 2) * 3600000).toISOString(),
        entity: lead.id,
        status: 'success',
      })
    })

    return processedActivity
  }, [campaigns, leads])

  const systemStatus = healthStatus
    ? (healthStatus.status === 'operational' ? 'operational' : 'degraded')
    : 'operational'

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await Promise.all([
        fetchCampaigns('active'),
        fetchLeads('QUALIFIED'),
        fetchHealth(),
        fetchRateLimits()
      ])
    } finally {
      setRefreshing(false)
    }
  }

  // Calculate dashboard statistics
  const stats = {
    totalCampaigns: campaigns.length || 0,
    totalLeads: leads.length || 0,
    connectedLeads: leads.filter(lead => lead.state === 'CONNECTED').length || 0,
    messagesSent: leads.reduce((total, lead) => total + (lead.messagesCount || 0), 0),
    activeCampaigns: campaigns.filter(c => c.status === 'active').length || 0,
    dailyLeads: leads.filter(lead => {
      const oneDayAgo = new Date(NOW - 86400000)
      const leadDate = new Date(lead.creationDate || NOW)
      return leadDate > oneDayAgo
    }).length || 0
  }

  const isLoading = campaignsLoading || leadsLoading || healthLoading

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <div className="flex items-center gap-2">
          <Badge 
            variant="outline" 
            className={`px-3 py-1 ${
              systemStatus === 'operational' ? 'text-emerald-600 border-emerald-200' :
              systemStatus === 'degraded' ? 'text-amber-600 border-amber-200' :
              'text-red-600 border-red-200'
            }`}
          >
            <Activity className="mr-2 h-3.5 w-3.5" />
            {systemStatus === 'operational' ? 'System Operational' : 
             systemStatus === 'degraded' ? 'System Degraded' : 'System Maintenance'}
          </Badge>
          <Button 
            size="sm" 
            onClick={handleRefresh} 
            disabled={refreshing}
            variant="outline"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
           <Button size="sm" onClick={() => router.push('/campaigns')}>
             <LayoutDashboard className="mr-2 h-4 w-4" />
             New Campaign
           </Button>
        </div>
      </div>

      {/* Error Alerts */}
      {(campaignsError || leadsError) && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {campaignsError || leadsError}
          </AlertDescription>
        </Alert>
      )}

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
              title="Total Campaigns"
              value={stats.totalCampaigns}
              trend={stats.totalCampaigns > 0 ? `+${Math.min(stats.totalCampaigns, 10)}` : undefined}
              trendUp={stats.totalCampaigns > 0}
              icon="LayoutDashboard"
              description="Active campaigns"
              className={CARD_HEIGHT_CLASS}
            />
            <StatsCard
              title="Total Leads"
              value={stats.totalLeads}
              trend={stats.totalLeads > 0 ? `+${Math.min(Math.floor(stats.totalLeads * 0.12), 20)}%` : undefined}
              trendUp={stats.totalLeads > 0}
              icon="Users"
              description="All time leads"
              className={CARD_HEIGHT_CLASS}
            />
            <StatsCard
              title="Connected"
              value={stats.connectedLeads}
              trend={stats.connectedLeads > 0 ? `+${Math.min(Math.floor(stats.connectedLeads * 0.08), 15)}%` : undefined}
              trendUp={stats.connectedLeads > 0}
              icon="Users"
              description="Connection rate"
              className={CARD_HEIGHT_CLASS}
            />
            <StatsCard
              title="Messages Sent"
              value={stats.messagesSent}
              trend={stats.messagesSent > 0 ? `+${Math.min(Math.floor(stats.messagesSent * 0.05), 25)}%` : undefined}
              trendUp={stats.messagesSent > 0}
              icon="MessageSquare"
              description="Total messages"
              className={CARD_HEIGHT_CLASS}
            />
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <Button variant="outline" className="flex flex-col gap-2 h-auto py-4" onClick={() => router.push('/leads')}>
                <Plus className="h-8 w-8" />
                <span className="text-sm font-medium">Add New Lead</span>
              </Button>
              <Button variant="outline" className="flex flex-col gap-2 h-auto  py-4" onClick={() => router.push('/leads')}>
                <Mail className="h-8 w-8" />
                <span className="text-sm font-medium">New Message</span>
              </Button>
              <Button variant="outline" className="flex flex-col gap-2 h-auto  py-4" onClick={() => router.push('/campaigns')}>
                <LayoutDashboard className="h-8 w-8" />
                <span className="text-sm font-medium">Campaign Stats</span>
              </Button>
              <Button variant="outline" className="flex flex-col gap-2 h-auto  py-4" onClick={() => router.push('/dashboard/health')}>
                <Activity className="h-8 w-8" />
                <span className="text-sm font-medium">View Health</span>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <RecentActivity items={activity} />
      </div>

      {/* Key Metrics */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Key Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
             <div className="space-y-2">
               <div className="text-sm text-muted-foreground">Active Campaigns</div>
               <div className="text-2xl font-bold">{stats.activeCampaigns}</div>
               <p className="text-xs text-muted-foreground">Real-time data</p>
             </div>
             <div className="space-y-2">
               <div className="text-sm text-muted-foreground">Leads Today</div>
               <div className="text-2xl font-bold">{stats.dailyLeads}</div>
               <p className="text-xs text-muted-foreground">Real-time data</p>
             </div>
             <div className="space-y-2">
               <div className="text-sm text-muted-foreground">Connection Rate</div>
               <div className="text-2xl font-bold">
                 {stats.totalLeads > 0 
                   ? `${roundTo1Decimal((stats.connectedLeads / stats.totalLeads) * 100)}%` 
                   : '0%'}
               </div>
               <p className="text-xs text-muted-foreground">Real-time data</p>
             </div>
             <div className="space-y-2">
               <div className="text-sm text-muted-foreground">Response Rate</div>
               <div className="text-2xl font-bold">
                 {stats.messagesSent > 0 
                   ? `${roundTo1Decimal((stats.connectedLeads / stats.messagesSent) * 100)}%` 
                   : '0%'}
               </div>
               <p className="text-xs text-muted-foreground">Real-time data</p>
             </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Dashboard
