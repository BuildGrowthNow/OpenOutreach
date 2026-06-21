'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'

interface AnalyticsData {
  connections_sent: number
  connections_accepted: number
  messages_sent: number
  responses: number
  conversions: number
  conversion_rate: number
  response_rate: number
  connection_success_rate: number
  daily_connections: number
  daily_messages: number
  avg_response_time?: string
  avg_conversion_time?: string
  qualified_leads: number
  hot_leads: number
  deals_closed: number
  profile_views: number
  link_clicks: number
  meeting_bookings: number
  last_7_days?: {
    connections_sent: number
    connections_accepted: number
    conversions: number
  }
  last_30_days?: {
    connections_sent: number
    connections_accepted: number
    conversions: number
  }
}

interface CampaignAnalyticsProps {
  analytics: AnalyticsData
  className?: string
}

export function CampaignAnalytics({ analytics, className }: CampaignAnalyticsProps) {
  return (
    <div className={cn('space-y-6', className)}>
      {/* Quick Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-center">{analytics.connections_sent || 0}</div>
            <div className="text-sm text-muted-foreground text-center mt-2">Connections Sent</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-center">{analytics.connections_accepted || 0}</div>
            <div className="text-sm text-muted-foreground text-center mt-2">Connections Accepted</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-center">{analytics.messages_sent || 0}</div>
            <div className="text-sm text-muted-foreground text-center mt-2">Messages Sent</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-center">{analytics.conversions || 0}</div>
            <div className="text-sm text-muted-foreground text-center mt-2">Conversions</div>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Analytics */}
      <Tabs defaultValue="performance" className="w-full">
        <TabsList className="grid grid-cols-3 w-full md:w-auto">
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="engagement">Engagement</TabsTrigger>
          <TabsTrigger value="quality">Lead Quality</TabsTrigger>
        </TabsList>

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Performance Metrics</CardTitle>
              <CardDescription>Key performance indicators</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2">Connection Success Rate</h4>
                    <div className="flex items-center">
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 mr-4">
                        <div
                          className="bg-emerald-500 h-4 rounded-full"
                          style={{ width: `${Math.min(100, analytics.connection_success_rate || 0)}%` }}
                        />
                      </div>
                      <span className="font-medium">{analytics.connection_success_rate || 0}%</span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">
                      {analytics.connections_accepted || 0} accepted out of {analytics.connections_sent || 0} sent
                    </p>
                  </div>

                  <div>
                    <h4 className="font-medium mb-2">Response Rate</h4>
                    <div className="flex items-center">
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 mr-4">
                        <div
                          className="bg-blue-500 h-4 rounded-full"
                          style={{ width: `${Math.min(100, analytics.response_rate || 0)}%` }}
                        />
                      </div>
                      <span className="font-medium">{analytics.response_rate || 0}%</span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">
                      {analytics.responses || 0} responses to {analytics.messages_sent || 0} messages
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
                          style={{ width: `${Math.min(100, analytics.conversion_rate || 0)}%` }}
                        />
                      </div>
                      <span className="font-medium">{analytics.conversion_rate || 0}%</span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">
                      {analytics.conversions || 0} conversions from {analytics.connections_accepted || 0} accepted connections
                    </p>
                  </div>

                  <div>
                    <h4 className="font-medium mb-2">Daily Activity</h4>
                    <p className="text-sm text-muted-foreground">
                      Average {analytics.daily_connections || 0} connections per day
                      <br />
                      Average {analytics.daily_messages || 0} messages per day
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Response Time Analysis */}
          {(analytics.avg_response_time || analytics.avg_conversion_time) && (
            <Card>
              <CardHeader>
                <CardTitle>Time Analysis</CardTitle>
                <CardDescription>Average time metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  {analytics.avg_response_time && (
                    <div className="text-center">
                      <div className="text-2xl font-bold">{analytics.avg_response_time}</div>
                      <div className="text-sm text-muted-foreground">Avg Response Time</div>
                    </div>
                  )}
                  {analytics.avg_conversion_time && (
                    <div className="text-center">
                      <div className="text-2xl font-bold">{analytics.avg_conversion_time}</div>
                      <div className="text-sm text-muted-foreground">Avg Conversion Time</div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Engagement Tab */}
        <TabsContent value="engagement" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Engagement Metrics</CardTitle>
              <CardDescription>How leads interact with your campaign</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold">{analytics.profile_views || 0}</div>
                  <div className="text-sm text-muted-foreground">Profile Views</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{analytics.link_clicks || 0}</div>
                  <div className="text-sm text-muted-foreground">Link Clicks</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{analytics.meeting_bookings || 0}</div>
                  <div className="text-sm text-muted-foreground">Meetings Booked</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Recent Activity */}
          {analytics.last_7_days && (
            <Card>
              <CardHeader>
                <CardTitle>Last 7 Days Activity</CardTitle>
                <CardDescription>Recent performance trends</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold">{analytics.last_7_days.connections_sent || 0}</div>
                    <div className="text-sm text-muted-foreground">Connections Sent</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold">{analytics.last_7_days.connections_accepted || 0}</div>
                    <div className="text-sm text-muted-foreground">Connections Accepted</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold">{analytics.last_7_days.conversions || 0}</div>
                    <div className="text-sm text-muted-foreground">Conversions</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Lead Quality Tab */}
        <TabsContent value="quality" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Lead Quality Metrics</CardTitle>
              <CardDescription>Quality and progression of leads</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold">{analytics.qualified_leads || 0}</div>
                  <div className="text-sm text-muted-foreground">Qualified Leads</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{analytics.hot_leads || 0}</div>
                  <div className="text-sm text-muted-foreground">Hot Leads</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{analytics.deals_closed || 0}</div>
                  <div className="text-sm text-muted-foreground">Deals Closed</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Progress Bar */}
          <Card>
            <CardHeader>
              <CardTitle>Lead Progression</CardTitle>
              <CardDescription>How leads progress through the funnel</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm font-medium">Connections Sent</span>
                  <span className="text-sm">{analytics.connections_sent || 0}</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4">
                  <div
                    className="bg-blue-500 h-4 rounded-full transition-all duration-300"
                    style={{ width: '100%' }}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm font-medium">Connections Accepted</span>
                  <span className="text-sm">{analytics.connections_accepted || 0}</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4">
                  <div
                    className="bg-green-500 h-4 rounded-full transition-all duration-300"
                    style={{ 
                      width: `${analytics.connections_sent > 0 ? 
                        Math.min(100, ((analytics.connections_accepted || 0) / (analytics.connections_sent || 1)) * 100) : 
                        0}%` 
                    }}
                  />
                </div>
                <div className="text-xs text-muted-foreground">
                  {analytics.connections_sent > 0 ? 
                    Math.round(((analytics.connections_accepted || 0) / (analytics.connections_sent || 1)) * 100) + '% acceptance rate' : 
                    'No connections sent'}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm font-medium">Conversions</span>
                  <span className="text-sm">{analytics.conversions || 0}</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4">
                  <div
                    className="bg-purple-500 h-4 rounded-full transition-all duration-300"
                    style={{ 
                      width: `${analytics.connections_accepted > 0 ? 
                        Math.min(100, ((analytics.conversions || 0) / (analytics.connections_accepted || 1)) * 100) : 
                        0}%` 
                    }}
                  />
                </div>
                <div className="text-xs text-muted-foreground">
                  {analytics.connections_accepted > 0 ? 
                    Math.round(((analytics.conversions || 0) / (analytics.connections_accepted || 1)) * 100) + '% conversion rate' : 
                    'No accepted connections'}
                </div>
              </div>

              <div className="pt-4 border-t">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Overall Conversion Rate</span>
                  <span className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                    {analytics.connections_sent > 0 ? 
                      Math.round(((analytics.conversions || 0) / (analytics.connections_sent || 1)) * 100) + '%' : 
                      '0%'}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {analytics.conversions || 0} conversions from {analytics.connections_sent || 0} initial connections
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Insights & Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle>Insights & Recommendations</CardTitle>
          <CardDescription>Actionable insights based on your data</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {(analytics.connection_success_rate || 0) < 20 && (
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

            {(analytics.response_rate || 0) < 10 && (
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

            {(analytics.conversion_rate || 0) < 5 && (
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

            {(analytics.daily_connections || 0) < 5 && (
              <div className={cn('p-3 rounded-lg border', 'border-purple-500/20 bg-purple-500/5')}>
                <h4 className="font-medium flex items-center gap-2">
                  <Icons.AlertCircle className="h-4 w-4 text-purple-500" />
                  Increase Daily Activity
                </h4>
                <p className="text-sm text-muted-foreground mt-1">
                  Your daily connection rate is low. Consider increasing your campaign velocity or expanding your lead pool.
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}