'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Icons } from '@/lib/types/components'
import { getCampaignAnalytics } from '@/lib/api/dashboard'
import { cn } from '@/lib/utils'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface CampaignAnalyticsResponse {
  period: string
  campaign_id: string
  stats: {
    connections_sent: number
    connections_accepted: number
    connection_accept_rate: number
    messages_sent: number
    messages_replied: number
    response_rate: number
    responses: number
    daily_connections?: number
    daily_messages?: number
    last_7_days?: {
      connections_sent?: number
      connections_accepted?: number
    }
    last_30_days?: {
      connections_accepted?: number
      conversions?: number
    }
    conversions: number
    conversion_rate: number
    connection_success_rate?: number
    errors: number
    rate_limit_warnings: number
    avg_time_to_accept?: string
    total_connection_attempts?: number
    failed_connections?: number
    avg_response_time?: string
    message_open_rate?: number
    total_messages_sent?: number
    positive_responses?: number
    avg_conversion_time?: string
    qualified_leads?: number
    hot_leads?: number
    deals_closed?: number
    profile_views?: number
    link_clicks?: number
    document_downloads?: number
    meeting_bookings?: number
    responses_under_1h?: number
    responses_1_24h?: number
    responses_1_7d?: number
    responses_over_7d?: number
    peak_day?: string
    peak_hour?: string
    timezone_optimization?: string
    high_quality_conversions?: number
    medium_quality_conversions?: number
    low_quality_conversions?: number
    best_performing_source?: string
    best_roi_source?: string
    avg_cost_per_conversion?: number
    best_performing_time?: string
    best_performing_day?: string
  }
  daily_breakdown: Array<{
    date: string
    connections_sent: number
    connections_accepted: number
    messages_sent: number
    messages_replied: number
  }>
  pipeline: {
    qualified: number
    ready_to_connect: number
    pending: number
    connected: number
    completed: number
    failed: number
    no_email: number
  }
}

export default function CampaignAnalyticsPage() {
  const params = useParams()
  const campaignId = params.id as string

  const [analytics, setAnalytics] = useState<CampaignAnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')

  const fetchAnalytics = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await getCampaignAnalytics(campaignId)
      if (response.data) {
        setAnalytics(response.data)
      } else {
        setError(response.error || response.message || 'Failed to fetch campaign analytics')
      }
    } catch (err) {
      setError('An error occurred while fetching campaign analytics')
      console.error('Error fetching campaign analytics:', err)
    } finally {
      setLoading(false)
    }
  }, [campaignId])

  useEffect(() => {
    void (async () => {
      await fetchAnalytics()
    })()
  }, [fetchAnalytics])

  const refreshAnalytics = async () => {
    await fetchAnalytics()
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
          <Skeleton className="h-10 w-32" />
        </div>

        <div className="space-y-6">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
          <div className="grid grid-cols-2 gap-6">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      </div>
    )
  }

  if (!analytics) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive">
          <AlertTitle>Analytics Not Available</AlertTitle>
          <AlertDescription>
            {error || 'No analytics data is available for this campaign yet.'}
          </AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => window.history.back()}>
          Back to Campaign
        </Button>
      </div>
    )
  }

  const stats = analytics.stats || {}

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">Campaign Analytics</h1>
          <p className="text-muted-foreground">
            Performance metrics and insights for your campaign
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshAnalytics}
            disabled={loading}
          >
            {loading ? (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Refreshing...
              </>
            ) : (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </>
            )}
          </Button>
          <Button variant="outline" size="sm" onClick={() => window.history.back()}>
            Back to Campaign
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Quick Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-center">{stats.connections_sent || 0}</div>
            <div className="text-sm text-muted-foreground text-center mt-2">Connections Sent</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-center">{stats.connections_accepted || 0}</div>
            <div className="text-sm text-muted-foreground text-center mt-2">Connections Accepted</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-center">{stats.messages_sent || 0}</div>
            <div className="text-sm text-muted-foreground text-center mt-2">Messages Sent</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-center">{stats.conversions || 0}</div>
            <div className="text-sm text-muted-foreground text-center mt-2">Conversions</div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs for Detailed Analytics */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-4 w-full md:w-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="engagement">Engagement</TabsTrigger>
          <TabsTrigger value="funnel">Conversion Funnel</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Performance Overview</CardTitle>
              <CardDescription>Key metrics and performance trends</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2">Connection Rate</h4>
                    <div className="flex items-center">
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 mr-4">
                        <div
                          className="bg-emerald-500 h-4 rounded-full"
                          style={{ width: `${Math.min(100, Math.round(((stats.connections_accepted || 0) / (stats.connections_sent || 1)) * 100))}%` }}
                        />
                      </div>
                      <span className="font-medium">
                        {Math.round(((stats.connections_accepted || 0) / (stats.connections_sent || 1)) * 100)}%
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">
                      {stats.connections_accepted || 0} accepted out of {stats.connections_sent || 0} sent
                    </p>
                  </div>

                  <div>
                    <h4 className="font-medium mb-2">Response Rate</h4>
                    <div className="flex items-center">
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 mr-4">
                        <div
                          className="bg-blue-500 h-4 rounded-full"
                          style={{ width: `${Math.min(100, Math.round(((stats.responses || 0) / (stats.messages_sent || 1)) * 100))}%` }}
                        />
                      </div>
                      <span className="font-medium">
                        {Math.round(((stats.responses || 0) / (stats.messages_sent || 1)) * 100)}%
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">
                      {stats.responses || 0} responses to {stats.messages_sent || 0} messages
                    </p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2">Conversion Rate</h4>
                    <div className="flex items-center">
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 mr-4">
                        <div
                          className="bg-purple-500 h-4 rounded-full"
                          style={{ width: `${Math.min(100, Math.round(((stats.conversions || 0) / (stats.connections_accepted || 1)) * 100))}%` }}
                        />
                      </div>
                      <span className="font-medium">
                        {Math.round(((stats.conversions || 0) / (stats.connections_accepted || 1)) * 100)}%
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">
                      {stats.conversions || 0} conversions from {stats.connections_accepted || 0} accepted connections
                    </p>
                  </div>

                  <div>
                    <h4 className="font-medium mb-2">Daily Activity</h4>
                    <p className="text-sm text-muted-foreground">
                      Average {stats.daily_connections || 0} connections per day
                      <br />
                      Average {stats.daily_messages || 0} messages per day
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Time Period Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Time Period Summary</CardTitle>
              <CardDescription>Activity breakdown by time period</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.last_7_days?.connections_sent || 0}</div>
                  <div className="text-sm text-muted-foreground">Connections Last 7 Days</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.last_30_days?.connections_accepted || 0}</div>
                  <div className="text-sm text-muted-foreground">Accepted Last 30 Days</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{stats.last_30_days?.conversions || 0}</div>
                  <div className="text-sm text-muted-foreground">Conversions Last 30 Days</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Performance Metrics</CardTitle>
              <CardDescription>Detailed performance analysis</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Connection Performance */}
                <div className="border rounded-lg p-4">
                  <h4 className="font-medium mb-3">Connection Performance</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.connection_success_rate || 0}%</div>
                      <div className="text-sm text-muted-foreground">Success Rate</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.avg_time_to_accept || 'N/A'}</div>
                      <div className="text-sm text-muted-foreground">Avg Accept Time</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.total_connection_attempts || 0}</div>
                      <div className="text-sm text-muted-foreground">Total Attempts</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.failed_connections || 0}</div>
                      <div className="text-sm text-muted-foreground">Failed</div>
                    </div>
                  </div>
                </div>

                {/* Message Performance */}
                <div className="border rounded-lg p-4">
                  <h4 className="font-medium mb-3">Message Performance</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.avg_response_time || 'N/A'}</div>
                      <div className="text-sm text-muted-foreground">Avg Response Time</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.message_open_rate || 0}%</div>
                      <div className="text-sm text-muted-foreground">Open Rate</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.total_messages_sent || 0}</div>
                      <div className="text-sm text-muted-foreground">Total Sent</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.positive_responses || 0}</div>
                      <div className="text-sm text-muted-foreground">Positive Responses</div>
                    </div>
                  </div>
                </div>

                {/* Conversion Performance */}
                <div className="border rounded-lg p-4">
                  <h4 className="font-medium mb-3">Conversion Performance</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.avg_conversion_time || 'N/A'}</div>
                      <div className="text-sm text-muted-foreground">Avg Conversion Time</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.qualified_leads || 0}</div>
                      <div className="text-sm text-muted-foreground">Qualified Leads</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.hot_leads || 0}</div>
                      <div className="text-sm text-muted-foreground">Hot Leads</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xl font-semibold">{stats.deals_closed || 0}</div>
                      <div className="text-sm text-muted-foreground">Deals Closed</div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Engagement Tab */}
        <TabsContent value="engagement" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Engagement Metrics</CardTitle>
              <CardDescription>How leads are engaging with your campaign</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Engagement Types */}
                  <div className="space-y-4">
                    <h4 className="font-medium">Engagement Types</h4>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-sm">Profile Views</span>
                        <span className="font-medium">{stats.profile_views || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">Link Clicks</span>
                        <span className="font-medium">{stats.link_clicks || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">Document Downloads</span>
                        <span className="font-medium">{stats.document_downloads || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">Meeting Bookings</span>
                        <span className="font-medium">{stats.meeting_bookings || 0}</span>
                      </div>
                    </div>
                  </div>

                  {/* Response Heatmap */}
                  <div className="space-y-4">
                    <h4 className="font-medium">Response Times</h4>
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-sm">Under 1 Hour</span>
                        <span className="font-medium">{stats.responses_under_1h || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">1-24 Hours</span>
                        <span className="font-medium">{stats.responses_1_24h || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">1-7 Days</span>
                        <span className="font-medium">{stats.responses_1_7d || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">Over 7 Days</span>
                        <span className="font-medium">{stats.responses_over_7d || 0}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Peak Activity Times */}
          <Card>
            <CardHeader>
              <CardTitle>Peak Activity Times</CardTitle>
              <CardDescription>When your audience is most active</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-xl font-semibold">{stats.peak_day || 'Weekdays'}</div>
                  <div className="text-sm text-muted-foreground">Best Day</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-semibold">{stats.peak_hour || '10am-2pm'}</div>
                  <div className="text-sm text-muted-foreground">Best Time</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-semibold">{stats.timezone_optimization || 'Auto'}</div>
                  <div className="text-sm text-muted-foreground">Timezone Opt</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Conversion Funnel Tab */}
        <TabsContent value="funnel" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Conversion Funnel</CardTitle>
              <CardDescription>Lead progression through your campaign</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-8">
                {/* Funnel Visualization */}
                <div className="relative">
                  {/* Connection Stage */}
                  <div className="mb-8 text-center">
                    <div className="text-lg font-semibold mb-2">Connection Sent</div>
                    <div className="text-3xl font-bold mb-1">{stats.connections_sent || 0}</div>
                    <div className="w-full h-4 bg-blue-200 dark:bg-blue-900 rounded-lg mx-auto max-w-md"></div>
                  </div>

                  {/* Connection Accepted Stage */}
                  <div className="mb-8 text-center">
                    <div className="text-lg font-semibold mb-2">Connection Accepted</div>
                    <div className="text-3xl font-bold mb-1">{stats.connections_accepted || 0}</div>
                    <div className="w-full h-4 bg-green-200 dark:bg-green-900 rounded-lg mx-auto max-w-md"
                      style={{ width: `${Math.min(100, ((stats.connections_accepted || 0) / (stats.connections_sent || 1)) * 100)}%` }}>
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {Math.round(((stats.connections_accepted || 0) / (stats.connections_sent || 1)) * 100)}% acceptance rate
                    </div>
                  </div>

                  {/* Response Stage */}
                  <div className="mb-8 text-center">
                    <div className="text-lg font-semibold mb-2">Messages / Responses</div>
                    <div className="text-3xl font-bold mb-1">{stats.responses || 0}</div>
                    <div className="w-full h-4 bg-purple-200 dark:bg-purple-900 rounded-lg mx-auto max-w-md"
                      style={{ width: `${Math.min(100, ((stats.responses || 0) / (stats.connections_accepted || 1)) * 100)}%` }}>
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {Math.round(((stats.responses || 0) / (stats.connections_accepted || 1)) * 100)}% response rate
                    </div>
                  </div>

                  {/* Conversion Stage */}
                  <div className="mb-8 text-center">
                    <div className="text-lg font-semibold mb-2">Conversions</div>
                    <div className="text-3xl font-bold mb-1">{stats.conversions || 0}</div>
                    <div className="w-full h-4 bg-orange-200 dark:bg-orange-900 rounded-lg mx-auto max-w-md"
                      style={{ width: `${Math.min(100, ((stats.conversions || 0) / (stats.responses || 1)) * 100)}%` }}>
                    </div>
                    <div className="text-sm text-muted-foreground mt-1">
                      {Math.round(((stats.conversions || 0) / (stats.responses || 1)) * 100)}% conversion rate
                    </div>
                  </div>

                  {/* Overall Conversion Rate */}
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                      Overall Conversion Rate: {Math.round(((stats.conversions || 0) / (stats.connections_sent || 1)) * 100)}%
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">
                      {stats.conversions || 0} conversions from {stats.connections_sent || 0} initial connections
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Lead Quality Analysis */}
          <Card>
            <CardHeader>
              <CardTitle>Lead Quality Analysis</CardTitle>
              <CardDescription>Conversion quality by lead source and type</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium mb-3">Conversion Quality</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-sm">High Quality Conversions</span>
                      <span className="font-medium">{stats.high_quality_conversions || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Medium Quality Conversions</span>
                      <span className="font-medium">{stats.medium_quality_conversions || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Low Quality Conversions</span>
                      <span className="font-medium">{stats.low_quality_conversions || 0}</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium mb-3">Lead Source Effectiveness</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-sm">Best Performing Source</span>
                      <span className="font-medium">{stats.best_performing_source || 'LinkedIn'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Source with Best ROI</span>
                      <span className="font-medium">{stats.best_roi_source || 'LinkedIn'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Avg Cost per Conversion</span>
                      <span className="font-medium">${stats.avg_cost_per_conversion || 0}</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle>Recommendations</CardTitle>
          <CardDescription>Actionable insights to improve campaign performance</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {(stats.connection_success_rate || 0) < 20 && (
              <div className={cn('p-3 rounded-lg border', 'border-blue-500/20 bg-blue-500/5')}>
                <h4 className="font-medium flex items-center gap-2">
                  <Icons.AlertCircle className="h-4 w-4 text-blue-500" />
                  Improve Connection Success Rate
                </h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Your connection success rate is lower than average. Consider reviewing your connection message templates and targeting criteria.
                </p>
              </div>
            )}

            {(stats.response_rate || 0) < 10 && (
              <div className={cn('p-3 rounded-lg border', 'border-amber-500/20 bg-amber-500/5')}>
                <h4 className="font-medium flex items-center gap-2">
                  <Icons.AlertCircle className="h-4 w-4 text-amber-500" />
                  Increase Response Rate
                </h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Response rate could be improved. Try personalizing messages more, following up at optimal times, or segmenting your audience better.
                </p>
              </div>
            )}

            {(stats.conversions || 0) < (stats.connections_accepted || 0) * 0.1 && (
              <div className={cn('p-3 rounded-lg border', 'border-emerald-500/20 bg-emerald-500/5')}>
                <h4 className="font-medium flex items-center gap-2">
                  <Icons.AlertCircle className="h-4 w-4 text-emerald-500" />
                  Optimize Conversion Funnel
                </h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Consider creating a more defined conversion path with clear calls-to-action, better qualification criteria, and more targeted follow-ups.
                </p>
              </div>
            )}

            {(!stats.best_performing_time || !stats.best_performing_day) && (
              <div className={cn('p-3 rounded-lg border', 'border-purple-500/20 bg-purple-500/5')}>
                <h4 className="font-medium flex items-center gap-2">
                  <Icons.AlertCircle className="h-4 w-4 text-purple-500" />
                  Analyze Timing Patterns
                </h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Enable timing analytics to discover when your audience is most responsive and optimize your send times.
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
