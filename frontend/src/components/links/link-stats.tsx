'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { TrackedLink } from '@/lib/api/dashboard'

interface LinkStatsProps {
  links: (TrackedLink | LinkMetrics)[]
}

// Helper type to handle both TrackedLink and LinkMetrics
interface LinkMetrics {
  id: string
  url: string
  shortUrl: string
  campaignId: string
  campaignName: string
  clicks: number
  uniqueVisitors: number
  lastClickAt: string
  createdAt: string
}

// Helper function to convert either type to LinkMetrics
function toLinkMetrics(link: TrackedLink | LinkMetrics): LinkMetrics {
  if ('original_url' in link) {
    return {
      id: link.id,
      url: link.original_url || '',
      shortUrl: link.short_code || '',
      campaignId: link.campaign?.id || '',
      campaignName: link.campaign?.name || '',
      clicks: link.total_clicks || 0,
      uniqueVisitors: link.unique_clicks || 0,
      lastClickAt: link.last_clicked_at || '',
      createdAt: link.created_at || '',
    }
  }
  return link as LinkMetrics
}

export default function LinkStats({ links }: LinkStatsProps) {
  const [timeRange, setTimeRange] = useState('30d')
  const [campaignFilter, setCampaignFilter] = useState('all')

  if (links.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Link Analytics</CardTitle>
          <CardDescription>
            No link data available for analysis
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <Icons.Link className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="font-semibold text-gray-500">No Data Available</h3>
            <p className="text-sm text-gray-400 mt-2">
              Create tracked links to see detailed analytics
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Convert links to metrics for processing
  const linkMetrics = links.map(toLinkMetrics)

  const filteredLinks = campaignFilter === 'all' 
    ? linkMetrics 
    : linkMetrics.filter(link => link.campaignId === campaignFilter)

  // Calculate statistics
  const stats = {
    totalClicks: filteredLinks.reduce((sum, link) => sum + link.clicks, 0),
    totalUniqueVisitors: filteredLinks.reduce((sum, link) => sum + link.uniqueVisitors, 0),
    avgCTR: filteredLinks.length > 0 
      ? (filteredLinks.reduce((sum, link) => sum + (link.clicks / Math.max(link.uniqueVisitors, 1)), 0) / filteredLinks.length * 100).toFixed(1)
      : '0.0',
    topPerformingLink: filteredLinks.length > 0 
      ? filteredLinks.reduce((prev, current) => (prev.clicks > current.clicks) ? prev : current)
      : null,
    clicksByCampaign: Object.entries(
      filteredLinks.reduce((acc, link) => {
        acc[link.campaignName] = (acc[link.campaignName] || 0) + link.clicks
        return acc
      }, {} as Record<string, number>)
    ).map(([campaign, clicks]) => ({ campaign, clicks })).sort((a, b) => b.clicks - a.clicks)
  }

  // Calculate hourly distribution (mock data for demo)
  const hourlyDistribution = Array.from({ length: 24 }, (_, i) => ({
    hour: `${i}:00`,
    clicks: ((filteredLinks.length * 7) + (i * 13)) % 100 + 10
  }))

  // Device distribution (mock data)
  const deviceDistribution = [
    { device: 'Desktop', percentage: 65 },
    { device: 'Mobile', percentage: 30 },
    { device: 'Tablet', percentage: 5 }
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Detailed Analytics</h2>
          <p className="text-muted-foreground">
            Performance metrics and insights for tracked links
          </p>
        </div>
        
        <div className="flex items-center space-x-4">
          <Select value={campaignFilter} onValueChange={setCampaignFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by Campaign" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Campaigns</SelectItem>
              {Array.from(new Set(linkMetrics.map(l => l.campaignId))).map(campaignId => {
                const campaign = linkMetrics.find(l => l.campaignId === campaignId)
                return (
                  <SelectItem key={campaignId} value={campaignId}>
                    {campaign?.campaignName || campaignId}
                  </SelectItem>
                )
              })}
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
              <SelectItem value="all">All time</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="text-3xl font-bold">{stats.totalClicks.toLocaleString()}</div>
              <p className="text-sm text-muted-foreground">Total Clicks</p>
              <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500" style={{ width: `${Math.min(100, (stats.totalClicks / 10000) * 100)}%` }} />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="text-3xl font-bold">{stats.totalUniqueVisitors.toLocaleString()}</div>
              <p className="text-sm text-muted-foreground">Unique Visitors</p>
              <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-green-500" style={{ width: `${Math.min(100, (stats.totalUniqueVisitors / 5000) * 100)}%` }} />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="text-3xl font-bold">{stats.avgCTR}%</div>
              <p className="text-sm text-muted-foreground">Avg. CTR</p>
              <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-purple-500" style={{ width: `${stats.avgCTR}%` }} />
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="text-3xl font-bold">{filteredLinks.length}</div>
              <p className="text-sm text-muted-foreground">Active Links</p>
              <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-yellow-500" style={{ width: `${Math.min(100, (filteredLinks.length / 50) * 100)}%` }} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="performance" className="space-y-6">
        <TabsList>
          <TabsTrigger value="performance">
            <Icons.TrendingUp className="h-4 w-4 mr-2" />
            Performance
          </TabsTrigger>
          <TabsTrigger value="campaigns">
            <Icons.Users className="h-4 w-4 mr-2" />
            Campaigns
          </TabsTrigger>
          <TabsTrigger value="devices">
            <Icons.HardDrive className="h-4 w-4 mr-2" />
            Devices
          </TabsTrigger>
          <TabsTrigger value="hours">
            <Icons.Clock className="h-4 w-4 mr-2" />
            Hourly
          </TabsTrigger>
        </TabsList>

        <TabsContent value="performance" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Top Performing Links</CardTitle>
                <CardDescription>
                  Links with the highest click-through rates
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {filteredLinks
                    .sort((a, b) => (b.clicks / Math.max(b.uniqueVisitors, 1)) - (a.clicks / Math.max(a.uniqueVisitors, 1)))
                    .slice(0, 5)
                    .map((link, index) => {
                      const ctr = ((link.clicks / Math.max(link.uniqueVisitors, 1)) * 100).toFixed(1)
                      return (
                        <div key={link.id} className="flex items-center justify-between p-3 border rounded-lg">
                          <div className="flex items-center space-x-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-100">
                              <span className="font-bold">{index + 1}</span>
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate">{link.campaignName}</p>
                              <p className="text-xs text-gray-500 truncate max-w-xs">{link.url}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold">{ctr}% CTR</div>
                            <div className="text-xs text-gray-500">{link.clicks} clicks</div>
                          </div>
                        </div>
                      )
                    })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Click Distribution</CardTitle>
                <CardDescription>
                  Distribution of clicks across all links
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {filteredLinks
                    .sort((a, b) => b.clicks - a.clicks)
                    .slice(0, 5)
                    .map((link) => {
                      const percentage = (link.clicks / Math.max(stats.totalClicks, 1)) * 100
                      return (
                        <div key={link.id} className="space-y-2">
                          <div className="flex justify-between">
                            <span className="text-sm font-medium truncate max-w-xs">{link.campaignName}</span>
                            <span className="text-sm">{link.clicks} ({percentage.toFixed(1)}%)</span>
                          </div>
                          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-blue-500"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="campaigns" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Performance</CardTitle>
              <CardDescription>
                Click performance by campaign
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {stats.clicksByCampaign.map((item, index) => (
                  <div key={index} className="space-y-2">
                    <div className="flex justify-between">
                      <span className="font-medium">{item.campaign}</span>
                      <span className="font-bold">{item.clicks.toLocaleString()} clicks</span>
                    </div>
                    <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                        style={{ 
                          width: `${(item.clicks / Math.max(stats.totalClicks, 1)) * 100}%` 
                        }}
                      />
                    </div>
                    <div className="flex justify-between text-xs text-gray-500">
                      <span>{((item.clicks / Math.max(stats.totalClicks, 1)) * 100).toFixed(1)}% of total</span>
                      <span>{
                        filteredLinks
                          .filter(l => l.campaignName === item.campaign)
                          .length
                      } links</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="devices" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Device Distribution</CardTitle>
              <CardDescription>
                Click distribution by device type
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {deviceDistribution.map((device, index) => (
                    <Card key={index}>
                      <CardContent className="pt-6">
                        <div className="text-center">
                          <div className="text-3xl font-bold">{device.percentage}%</div>
                          <p className="text-sm text-muted-foreground">{device.device}</p>
                          <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div 
                              className={`h-full ${
                                index === 0 ? 'bg-blue-500' :
                                index === 1 ? 'bg-green-500' :
                                'bg-yellow-500'
                              }`}
                              style={{ width: `${device.percentage}%` }}
                            />
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="hours" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Hourly Click Distribution</CardTitle>
              <CardDescription>
                Click activity throughout the day
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {hourlyDistribution.map((hour, index) => (
                  <div key={index} className="flex items-center space-x-4">
                    <div className="w-16 text-sm text-gray-600">{hour.hour}</div>
                    <div className="flex-1">
                      <div className="h-6 bg-gradient-to-r from-blue-100 to-blue-500 rounded-md relative">
                        <div 
                          className="absolute inset-0 flex items-center justify-end px-2"
                          style={{ width: `${(hour.clicks / 150) * 100}%` }}
                        >
                          <span className="text-xs font-medium text-white">
                            {hour.clicks} clicks
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {stats.topPerformingLink && (
        <Card>
          <CardHeader>
            <CardTitle>Top Performing Link</CardTitle>
            <CardDescription>
              Highest performing link based on click-through rate
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between p-4 border rounded-lg bg-gradient-to-r from-blue-50 to-purple-50">
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <Badge variant="default" className="bg-green-100 text-green-800 hover:bg-green-100">
                    <Icons.TrendingUp className="h-3 w-3 mr-1" />
                    Top Performer
                  </Badge>
                  <Badge variant="outline">{stats.topPerformingLink.campaignName}</Badge>
                </div>
                <div className="space-y-1">
                  <p className="font-medium truncate max-w-2xl">{stats.topPerformingLink.url}</p>
                  <div className="flex items-center space-x-4 text-sm">
                    <div className="flex items-center">
                      <Icons.ExternalLink className="h-3 w-3 mr-1 text-gray-500" />
                      <span className="text-gray-600">Short URL:</span>
                      <code className="ml-2 bg-gray-100 px-2 py-1 rounded text-xs">
                        {window.location.origin}/l/{stats.topPerformingLink.shortUrl}
                      </code>
                    </div>
                    <div className="flex items-center">
                      <Icons.Clock className="h-3 w-3 mr-1 text-gray-500" />
                      <span className="text-gray-600">Last click:</span>
                      <span className="ml-1">
                        {new Date(stats.topPerformingLink.lastClickAt).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="text-right">
                <div className="text-3xl font-bold">
                  {((stats.topPerformingLink.clicks / Math.max(stats.topPerformingLink.uniqueVisitors, 1)) * 100).toFixed(1)}%
                </div>
                <p className="text-sm text-gray-600">CTR</p>
                <div className="text-lg font-bold">{stats.topPerformingLink.clicks.toLocaleString()}</div>
                <p className="text-sm text-gray-600">Total Clicks</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}