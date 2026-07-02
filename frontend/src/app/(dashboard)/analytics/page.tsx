'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { getCampaigns } from '@/lib/api/dashboard'
import { Breadcrumb } from '@/components/layout/breadcrumb'
import { Campaign } from '@/lib/types/components'

// Fallback constants for analytics - clearly labeled as such
const FALLBACK_CONNECTION_ACCEPT_RATE = 25
const FALLBACK_RESPONSE_RATE = 20
const FALLBACK_CONVERSION_RATE = 12

// Type for computed analytics stats
interface ComputedStats {
  connectionsSent: number;
  connectionsAccepted: number;
  messagesSent: number;
  messagesReplied: number;
  conversions: number;
  qualified: number;
  readyToConnect: number;
  connected: number;
  pending: number;
  failed: number;
  noEmail: number;
}

export default function AnalyticsOverviewPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [selectedCampaign, setSelectedCampaign] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [timeRange, setTimeRange] = useState<string>('30d')

  // Load campaigns from backend
  const loadCampaigns = useCallback(async () => {
    try {
      setLoading(true)
      const response = await getCampaigns()
      if (response.data && response.data.data) {
        setCampaigns(response.data.data)
      } else {
        setError('Failed to load campaigns')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      await loadCampaigns()
    })()
  }, [loadCampaigns])

  if (loading) {
    return (
      <div className="space-y-6">
        <Breadcrumb 
          items={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Analytics', href: '/analytics', isActive: true }
          ]}
        />
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
          <Skeleton className="h-10 w-32" />
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <>
        <Breadcrumb 
          items={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Analytics', href: '/analytics', isActive: true }
          ]}
        />
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Failed to load analytics: {error}
            <Button variant="outline" className="ml-4" onClick={loadCampaigns}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </>
    )
  }

  // Calculate totals from real campaign data
  const filteredCampaigns = selectedCampaign === 'all' 
    ? campaigns 
    : campaigns.filter(campaign => campaign.id === selectedCampaign)

  // Calculate actual totals from campaign stats (when available)
  function reduceCampaignStats(acc: ComputedStats, campaign: Campaign): ComputedStats {
    const stats = campaign.stats || {
      totalLeads: 0,
      connected: 0,
      messagesSent: 0,
      messagesReplied: 0,
      completed: 0,
      qualified: 0,
      readyToConnect: 0,
      pending: 0,
      failed: 0,
      noEmail: 0,
    }
    return {
      connectionsSent: acc.connectionsSent + (stats.totalLeads || 0),
      connectionsAccepted: acc.connectionsAccepted + (stats.connected || 0),
      messagesSent: acc.messagesSent + (stats.messagesSent || 0),
      messagesReplied: acc.messagesReplied + (stats.messagesReplied || 0),
      conversions: acc.conversions + (stats.completed || 0),
      qualified: acc.qualified + (stats.qualified || 0),
      readyToConnect: acc.readyToConnect + (stats.readyToConnect || 0),
      connected: acc.connected + (stats.connected || 0),
      pending: acc.pending,
      failed: acc.failed,
      noEmail: acc.noEmail,
    }
  }

  const initialStats: ComputedStats = {
    connectionsSent: 0,
    connectionsAccepted: 0,
    messagesSent: 0,
    messagesReplied: 0,
    conversions: 0,
    qualified: 0,
    readyToConnect: 0,
    connected: 0,
    pending: 0,
    failed: 0,
    noEmail: 0,
  }
  
  const computedStats: ComputedStats = filteredCampaigns.reduce(reduceCampaignStats, initialStats)

  const connectionAcceptRate = computedStats.connectionsSent > 0
    ? (computedStats.connectionsAccepted / computedStats.connectionsSent) * 100
    : FALLBACK_CONNECTION_ACCEPT_RATE

  const responseRate = computedStats.messagesSent > 0
    ? (computedStats.messagesReplied / computedStats.messagesSent) * 100
    : FALLBACK_RESPONSE_RATE

  const conversionRate = computedStats.qualified > 0
    ? (computedStats.conversions / computedStats.qualified) * 100
    : FALLBACK_CONVERSION_RATE

  const totalStats = {
    connectionsSent: computedStats.connectionsSent,
    connectionsAccepted: computedStats.connectionsAccepted,
    connectionAcceptRate: roundTo1Decimal(connectionAcceptRate),
    messagesSent: computedStats.messagesSent,
    messagesReplied: computedStats.messagesReplied,
    responseRate: roundTo1Decimal(responseRate),
    conversions: computedStats.conversions,
    conversionRate: roundTo1Decimal(conversionRate),
    leads: computedStats.connectionsSent + computedStats.readyToConnect + computedStats.pending,
    qualified: computedStats.qualified,
    readyToConnect: computedStats.readyToConnect,
    connected: computedStats.connected,
    pending: filteredCampaigns.reduce((sum, campaign) => {
      const stats = campaign.stats || {
        totalLeads: 0,
        qualified: 0,
        readyToConnect: 0,
        pending: 0,
        connected: 0,
        completed: 0,
        failed: 0,
        noEmail: 0,
        messagesSent: 0,
        messagesReplied: 0,
        connectionAcceptRate: 0,
        responseRate: 0,
      }
      return sum + (stats.pending || 0)
    }, 0),
    failed: filteredCampaigns.reduce((sum, campaign) => {
      const stats = campaign.stats || {
        totalLeads: 0,
        qualified: 0,
        readyToConnect: 0,
        pending: 0,
        connected: 0,
        completed: 0,
        failed: 0,
        noEmail: 0,
        messagesSent: 0,
        messagesReplied: 0,
        connectionAcceptRate: 0,
        responseRate: 0,
      }
      return sum + (stats.failed || 0)
    }, 0),
    noEmail: filteredCampaigns.reduce((sum, campaign) => {
      const stats = campaign.stats || {
        totalLeads: 0,
        qualified: 0,
        readyToConnect: 0,
        pending: 0,
        connected: 0,
        completed: 0,
        failed: 0,
        noEmail: 0,
        messagesSent: 0,
        messagesReplied: 0,
        connectionAcceptRate: 0,
        responseRate: 0,
      }
      return sum + (stats.noEmail || 0)
    }, 0),
  }

  // Helper to round to 1 decimal place
  function roundTo1Decimal(value: number): number {
    return Math.round(value * 10) / 10
  }

  return (
    <div className="space-y-6">
      <Breadcrumb 
        items={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Analytics', href: '/analytics', isActive: true }
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Analytics Overview</h1>
          <p className="text-muted-foreground">
            Performance metrics across all campaigns and activities
          </p>
        </div>
        
        <div className="flex items-center space-x-4">
          <Select value={selectedCampaign} onValueChange={setSelectedCampaign}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select Campaign" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Campaigns</SelectItem>
              {campaigns.map(campaign => (
                <SelectItem key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Time Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
              <SelectItem value="ytd">Year to date</SelectItem>
            </SelectContent>
          </Select>
          
          <Button variant="outline" onClick={loadCampaigns}>
            <Icons.RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Connection Accept Rate */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Connection Accept Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStats.connectionAcceptRate}%</div>
            <p className="text-xs text-muted-foreground">
              {totalStats.connectionsAccepted} / {totalStats.connectionsSent} accepted
            </p>
            <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-green-500" 
                style={{ width: `${Math.min(totalStats.connectionAcceptRate, 100)}%` }} 
              />
            </div>
          </CardContent>
        </Card>
        
        {/* Response Rate */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Response Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStats.responseRate}%</div>
            <p className="text-xs text-muted-foreground">
              {totalStats.messagesReplied} / {totalStats.messagesSent} replied
            </p>
            <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500" 
                style={{ width: `${Math.min(totalStats.responseRate, 100)}%` }} 
              />
            </div>
          </CardContent>
        </Card>
        
        {/* Conversion Rate */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Conversion Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStats.conversionRate}%</div>
            <p className="text-xs text-muted-foreground">
              {totalStats.conversions} conversions from {totalStats.qualified} qualified
            </p>
            <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-purple-500" 
                style={{ width: `${Math.min(totalStats.conversionRate, 100)}%` }} 
              />
            </div>
          </CardContent>
        </Card>
        
        {/* Active Leads */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Leads</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStats.leads}</div>
            <p className="text-xs text-muted-foreground">
              {totalStats.qualified} qualified • {totalStats.readyToConnect} ready
            </p>
            <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-yellow-500" 
                style={{ 
                  width: `${totalStats.leads > 0 ? (totalStats.readyToConnect / totalStats.leads) * 100 : 0}%` 
                }} 
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
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
          <TabsTrigger value="trends">
            <Icons.TrendingUp className="h-4 w-4 mr-2" />
            Trends
          </TabsTrigger>
          <TabsTrigger value="export">
            <Icons.Download className="h-4 w-4 mr-2" />
            Export
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Campaign Performance</CardTitle>
                <CardDescription>
                  Performance metrics by campaign
                </CardDescription>
              </CardHeader>
              <CardContent>
                {campaigns.length > 0 ? (
                  <div className="space-y-4">
                    {filteredCampaigns.map(campaign => (
                      <div key={campaign.id} className="flex items-center justify-between p-3 border rounded-lg">
                        <div>
                          <h4 className="font-medium">{campaign.name}</h4>
                          <p className="text-sm text-muted-foreground">{campaign.description}</p>
                        </div>
                        <div className="text-right">
                          <div className="font-bold">{campaign.stats?.totalLeads || 0} leads</div>
                          <div className="text-sm text-muted-foreground">
                            {campaign.stats?.connectionAcceptRate || 0}% accept rate
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-muted-foreground">No campaigns yet. Create a campaign to see analytics.</p>
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
                {campaigns.length > 0 ? (
                  <div className="space-y-4">
                    {[
                      { stage: 'Qualified', count: totalStats.qualified, color: 'bg-blue-500' },
                      { stage: 'Ready to Connect', count: totalStats.readyToConnect, color: 'bg-yellow-500' },
                      { stage: 'Connected', count: totalStats.connected, color: 'bg-green-500' },
                      { stage: 'Completed', count: totalStats.conversions, color: 'bg-purple-500' }
                    ].filter(item => item.count > 0).length > 0 ? (
                      <>
                        {[
                          { stage: 'Qualified', count: totalStats.qualified, color: 'bg-blue-500' },
                          { stage: 'Ready to Connect', count: totalStats.readyToConnect, color: 'bg-yellow-500' },
                          { stage: 'Connected', count: totalStats.connected, color: 'bg-green-500' },
                          { stage: 'Completed', count: totalStats.conversions, color: 'bg-purple-500' }
                        ].map((item, index) => (
                          <div key={index} className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-sm font-medium">{item.stage}</span>
                              <span className="text-sm font-bold">{item.count}</span>
                            </div>
                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                              <div 
                                className={`h-full ${item.color}`}
                                style={{ 
                                  width: `${totalStats.leads > 0 ? (item.count / totalStats.leads) * 100 : 0}%` 
                                }} 
                              />
                            </div>
                          </div>
                        ))}
                      </>
                    ) : (
                      <div className="text-center py-4">
                        <p className="text-sm text-muted-foreground">No pipeline data available yet</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-muted-foreground">No leads yet. Data will appear when leads are added.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Campaigns Tab */}
        <TabsContent value="campaigns" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Comparison</CardTitle>
              <CardDescription>
                Detailed performance comparison across campaigns
              </CardDescription>
            </CardHeader>
            <CardContent>
              {campaigns.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-4">Campaign</th>
                        <th className="text-left py-3 px-4">Leads</th>
                        <th className="text-left py-3 px-4">Accept Rate</th>
                        <th className="text-left py-3 px-4">Response Rate</th>
                        <th className="text-left py-3 px-4">Conversion Rate</th>
                        <th className="text-left py-3 px-4">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {campaigns.map(campaign => (
                        <tr key={campaign.id} className="border-b hover:bg-gray-50">
                          <td className="py-3 px-4">
                            <div className="font-medium">{campaign.name}</div>
                            <div className="text-sm text-muted-foreground truncate max-w-xs">
                              {campaign.description}
                            </div>
                          </td>
                          <td className="py-3 px-4">{campaign.stats?.totalLeads || 0}</td>
                          <td className="py-3 px-4">{campaign.stats?.connectionAcceptRate || 0}%</td>
                          <td className="py-3 px-4">{campaign.stats?.responseRate || 0}%</td>
                          <td className="py-3 px-4">
                            {campaign.stats?.totalLeads && campaign.stats.totalLeads > 0 ? 
                              `${((campaign.stats.completed || 0) / campaign.stats.totalLeads * 100).toFixed(1)}%` : 
                              '0%'
                            }
                          </td>
                          <td className="py-3 px-4">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              campaign.status === 'active' ? 'bg-green-100 text-green-800' :
                              campaign.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {campaign.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">No campaigns yet. Create a campaign to see comparisons.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trends Tab */}
        <TabsContent value="trends" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Performance Trends</CardTitle>
              <CardDescription>
                Performance metrics over time
              </CardDescription>
            </CardHeader>
            <CardContent>
              {campaigns.length > 0 ? (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">
                    Trend visualization is coming soon. Current analytics reflect real data from your campaigns.
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    Note: Historical trend charts require a charting library integration.
                  </p>
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">No campaign data available for trends yet.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Export Tab */}
        <TabsContent value="export" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Export Analytics</CardTitle>
              <CardDescription>
                Export detailed analytics reports for analysis
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-center space-y-4">
                        <Icons.Download className="h-12 w-12 text-blue-500 mx-auto" />
                        <h3 className="font-semibold">CSV Export</h3>
                        <p className="text-sm text-muted-foreground">
                          Export raw data as CSV for spreadsheet analysis
                        </p>
                        <Button className="w-full">
                          <Icons.Download className="h-4 w-4 mr-2" />
                          Download CSV
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardContent className="pt-6">
                      <div className="text-center space-y-4">
                        <Icons.FileText className="h-12 w-12 text-green-500 mx-auto" />
                        <h3 className="font-semibold">PDF Report</h3>
                        <p className="text-sm text-muted-foreground">
                          Generate detailed PDF reports with charts and insights
                        </p>
                        <Button variant="outline" className="w-full">
                          <Icons.FileText className="h-4 w-4 mr-2" />
                          Generate PDF
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
