'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { getLinks } from '@/lib/api/dashboard'
import { Breadcrumb } from '@/components/layout/breadcrumb'
import LinkStats from '@/components/links/link-stats'
import { LinkMetrics } from '@/lib/types/components'

const NOW = Date.now()
const DAY_MS = 24 * 60 * 60 * 1000

export default function LinksPage() {
  const [links, setLinks] = useState<LinkMetrics[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedType, setSelectedType] = useState<string>('all')

  const loadLinks = useCallback(async () => {
    try {
      setLoading(true)
      const response = await getLinks()
      if (response.data && response.data.data) {
        setLinks(response.data.data)
      } else {
        setError('Failed to load links')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      await loadLinks()
    })()
  }, [loadLinks])

  const filteredLinks = useMemo(() => links.filter(link => {
    const matchesSearch = link.url.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         link.campaignName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         link.shortUrl.toLowerCase().includes(searchTerm.toLowerCase())

    if (selectedType === 'all') return matchesSearch
    if (selectedType === 'high-traffic') return matchesSearch && link.clicks > 100
    if (selectedType === 'recent') {
      const lastClick = new Date(link.lastClickAt)
      const sevenDaysAgo = new Date(NOW - 7 * DAY_MS)
      return matchesSearch && lastClick > sevenDaysAgo
    }
    return matchesSearch
  }), [links, searchTerm, selectedType])

  const totalStats = {
    totalLinks: links.length,
    totalClicks: links.reduce((sum, link) => sum + link.clicks, 0),
    totalUniqueVisitors: links.reduce((sum, link) => sum + link.uniqueVisitors, 0),
    averageClickThroughRate: links.length > 0 
      ? (links.reduce((sum, link) => sum + (link.clicks / Math.max(link.uniqueVisitors, 1)), 0) / links.length * 100).toFixed(1)
      : '0.0'
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Breadcrumb 
          items={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Links', href: '/links', isActive: true }
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
            { label: 'Links', href: '/links', isActive: true }
          ]}
        />
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Failed to load links: {error}
            <Button variant="outline" className="ml-4" onClick={loadLinks}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </>
    )
  }

  return (
    <div className="space-y-6">
      <Breadcrumb 
        items={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Links', href: '/links', isActive: true }
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Link Tracking</h1>
          <p className="text-muted-foreground">
            Monitor click-through rates and engagement for tracked links
          </p>
        </div>
        
        <div className="flex items-center space-x-4">
          <Button variant="outline" onClick={loadLinks}>
            <Icons.RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button>
            <Icons.Plus className="h-4 w-4 mr-2" />
            Add Link
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Links</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStats.totalLinks}</div>
            <p className="text-xs text-muted-foreground">
              Across {new Set(links.map(l => l.campaignId)).size} campaigns
            </p>
            <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500" style={{ width: `${Math.min(100, (totalStats.totalLinks / 50) * 100)}%` }} />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Clicks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStats.totalClicks.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              {totalStats.totalUniqueVisitors.toLocaleString()} unique visitors
            </p>
            <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-green-500" style={{ width: `${Math.min(100, (totalStats.totalClicks / 10000) * 100)}%` }} />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg. CTR</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStats.averageClickThroughRate}%</div>
            <p className="text-xs text-muted-foreground">
              Average click-through rate
            </p>
            <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-purple-500" style={{ width: `${totalStats.averageClickThroughRate}%` }} />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Links</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {links.filter(l => {
                const lastClick = new Date(l.lastClickAt)
                const thirtyDaysAgo = new Date(NOW - 30 * DAY_MS)
                return lastClick > thirtyDaysAgo
              }).length}
            </div>
            <p className="text-xs text-muted-foreground">
              Links with clicks in last 30 days
            </p>
            <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-yellow-500" style={{ width: `${(links.filter(l => new Date(l.lastClickAt) > new Date(NOW - 30 * DAY_MS)).length / Math.max(links.length, 1)) * 100}%` }} />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center space-x-4">
        <div className="flex-1">
          <Input
            placeholder="Search links by URL, campaign, or short URL..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-md"
          />
        </div>
        
        <Tabs value={selectedType} onValueChange={setSelectedType} className="w-auto">
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="high-traffic">High Traffic</TabsTrigger>
            <TabsTrigger value="recent">Recent</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">
            <Icons.Link className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="campaigns">
            <Icons.Users className="h-4 w-4 mr-2" />
            By Campaign
          </TabsTrigger>
          <TabsTrigger value="analytics">
            <Icons.BarChart3 className="h-4 w-4 mr-2" />
            Analytics
          </TabsTrigger>
          <TabsTrigger value="create">
            <Icons.Plus className="h-4 w-4 mr-2" />
            Create
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Tracked Links</CardTitle>
              <CardDescription>
                All tracked links with click analytics
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {filteredLinks.length > 0 ? (
                  filteredLinks.map(link => (
                    <div key={link.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-2">
                          <Badge variant="outline" className="text-xs">
                            {link.campaignName}
                          </Badge>
                          <Badge variant="secondary" className="text-xs">
                            {link.clicks} clicks
                          </Badge>
                          {new Date(link.lastClickAt) > new Date(NOW - DAY_MS) && (
                            <Badge variant="default" className="text-xs bg-green-100 text-green-800 hover:bg-green-100">
                              Active Today
                            </Badge>
                          )}
                        </div>
                        
                        <div className="flex items-center space-x-2">
                          <Icons.ExternalLink className="h-4 w-4 text-gray-400 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <a 
                              href={link.url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-blue-600 hover:text-blue-800 truncate block"
                            >
                              {link.url}
                            </a>
                            <div className="flex items-center space-x-2 mt-1">
                              <span className="text-xs text-gray-500">Short URL:</span>
                              <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                                {window.location.origin}/l/{link.shortUrl}
                              </code>
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className="h-6 px-2"
                                onClick={() => navigator.clipboard.writeText(`${window.location.origin}/l/${link.shortUrl}`)}
                              >
                                <Icons.ExternalLink className="h-3 w-3 mr-1" />
                                Copy
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <div className="text-right space-y-1">
                        <div className="text-sm font-medium">{link.clicks.toLocaleString()} clicks</div>
                        <div className="text-xs text-gray-500">
                          {link.uniqueVisitors.toLocaleString()} unique
                        </div>
                        <div className="text-xs">
                          Last: {new Date(link.lastClickAt).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8">
                    <Icons.Link className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                    <h3 className="font-semibold text-gray-500">No links found</h3>
                    <p className="text-sm text-gray-400">
                      {searchTerm ? 'Try a different search term' : 'Start by creating your first tracked link'}
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="campaigns" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Link Performance</CardTitle>
              <CardDescription>
                Link analytics grouped by campaign
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {Array.from(new Set(links.map(l => l.campaignId))).map(campaignId => {
                  const campaignLinks = links.filter(l => l.campaignId === campaignId)
                  const campaignName = campaignLinks[0]?.campaignName || 'Unknown Campaign'
                  const campaignStats = {
                    totalLinks: campaignLinks.length,
                    totalClicks: campaignLinks.reduce((sum, l) => sum + l.clicks, 0),
                    totalUnique: campaignLinks.reduce((sum, l) => sum + l.uniqueVisitors, 0),
                    avgCTR: campaignLinks.length > 0 
                      ? (campaignLinks.reduce((sum, l) => sum + (l.clicks / Math.max(l.uniqueVisitors, 1)), 0) / campaignLinks.length * 100).toFixed(1)
                      : '0.0'
                  }
                  
                  return (
                    <div key={campaignId} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <h4 className="font-semibold">{campaignName}</h4>
                          <p className="text-sm text-gray-500">Campaign ID: {campaignId}</p>
                        </div>
                        <Badge variant="outline">
                          {campaignStats.totalLinks} links
                        </Badge>
                      </div>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold">{campaignStats.totalClicks.toLocaleString()}</div>
                          <p className="text-xs text-gray-500">Total Clicks</p>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold">{campaignStats.totalUnique.toLocaleString()}</div>
                          <p className="text-xs text-gray-500">Unique Visitors</p>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold">{campaignStats.avgCTR}%</div>
                          <p className="text-xs text-gray-500">Avg. CTR</p>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold">
                            {campaignLinks.filter(l => l.clicks > 0).length}
                          </div>
                          <p className="text-xs text-gray-500">Active Links</p>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          {filteredLinks.length > 0 && (
            <LinkStats links={filteredLinks} />
          )}
        </TabsContent>

        <TabsContent value="create" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Create New Tracked Link</CardTitle>
              <CardDescription>
                Create a new tracked link with UTM parameters
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Destination URL</label>
                  <Input placeholder="https://example.com/product" />
                  <p className="text-xs text-gray-500 mt-1">
                    The URL you want to track clicks for
                  </p>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Campaign</label>
                    <select className="w-full border rounded-md px-3 py-2 text-sm">
                      <option value="">Select Campaign</option>
                      {Array.from(new Set(links.map(l => l.campaignName))).map(name => (
                        <option key={name} value={name}>{name}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-2">Custom Short URL</label>
                    <Input placeholder="Optional custom identifier" />
                    <p className="text-xs text-gray-500 mt-1">
                      Leave blank for auto-generated
                    </p>
                  </div>
                </div>
                
                <div>
                  <h4 className="font-semibold mb-2">UTM Parameters (Optional)</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Source</label>
                      <Input placeholder="linkedin, email, etc." />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">Medium</label>
                      <Input placeholder="social, cpc, etc." />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">Campaign Name</label>
                      <Input placeholder="spring-promo, webinar, etc." />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">Term</label>
                      <Input placeholder="keyword, topic, etc." />
                    </div>
                  </div>
                </div>
                
                <div className="pt-4 border-t">
                  <div className="flex justify-end space-x-4">
                    <Button variant="outline">Cancel</Button>
                    <Button>
                      <Icons.Plus className="h-4 w-4 mr-2" />
                      Create Tracked Link
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
