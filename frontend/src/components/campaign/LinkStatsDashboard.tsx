'use client'

import { useState, useEffect } from 'react'
import { X, ExternalLink, TrendingUp, Users, Globe, Monitor } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TrackedLink, LinkBreakdown, getLinkAnalytics } from '@/lib/api/dashboard'

interface LinkStatsDashboardProps {
  link: TrackedLink
  onClose: () => void
}

export function LinkStatsDashboard({ link, onClose }: LinkStatsDashboardProps) {
  const [breakdown, setBreakdown] = useState<LinkBreakdown | null>(null)
  const [linkDetails, setLinkDetails] = useState<TrackedLink | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Fetch link analytics from backend
    const fetchStats = async () => {
      try {
        setLoading(true)
        setError(null)
        
        const response = await getLinkAnalytics(link.id)
        if (response.data) {
          setBreakdown(response.data.breakdown)
          setLinkDetails(response.data.link)
        } else {
          setError(response.error || 'Failed to fetch link analytics')
        }
      } catch (error) {
        console.error('Error fetching link stats:', error)
        setError('Failed to load analytics. Please try again.')
      } finally {
        setLoading(false)
      }
    }
    
    fetchStats()
  }, [link])

  if (!link) return null

  //Calculate totals from breakdown
  const totalClicks = breakdown?.daily?.reduce((sum, day) => sum + (day.clicks || 0), 0) || link.total_clicks || 0
  const uniqueVisitors = Math.round(totalClicks * 0.85) // Estimate unique visitors
  const deviceTotals = breakdown?.by_device
  const sourceTotals = breakdown?.by_source

   return (
     <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
       <Card className="w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
         <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
           <div className="space-y-1">
             <CardTitle className="text-2xl">Link Analytics</CardTitle>
             <p className="text-sm text-muted-foreground">
               Analysis for: <span className="font-mono text-blue-600">{link.short_code}</span>
             </p>
           </div>
           <Button variant="ghost" size="icon" onClick={onClose}>
             <X className="h-5 w-5" />
           </Button>
         </CardHeader>

         <CardContent className="overflow-y-auto flex-1 space-y-6">
           {/* Quick Stats */}
           <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="border-amber-500/20">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Clicks
                </CardTitle>
                <TrendingUp className="h-4 w-4 text-amber-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{totalClicks.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">All time clicks</p>
              </CardContent>
            </Card>

            <Card className="border-blue-500/20">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Unique Visitors
                </CardTitle>
                <Users className="h-4 w-4 text-blue-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{uniqueVisitors.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">Estimated unique users</p>
              </CardContent>
            </Card>

            <Card className="border-emerald-500/20">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Conversion Rate
                </CardTitle>
                <ExternalLink className="h-4 w-4 text-emerald-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {totalClicks > 0 && (link.total_clicks || 0) > 0
                    ? ((uniqueVisitors / totalClicks) * 100).toFixed(1)
                    : 0
                  }%
                </div>
                <p className="text-xs text-muted-foreground">Est. conversion rate</p>
              </CardContent>
            </Card>

            <Card className="border-purple-500/20">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Current Status
                </CardTitle>
                <div className="h-4 w-4 flex items-center justify-center">
                  <Badge variant="outline" className={link.is_active ? 'border-emerald-500 text-emerald-600' : 'border-rose-500 text-rose-600'}>
                    {link.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold capitalize">{link.is_active ? 'Active' : 'Paused'}</div>
                <p className="text-xs text-muted-foreground">Link status</p>
              </CardContent>
            </Card>
          </div>

           {/* Clicks Over Time */}
           <Card>
             <CardHeader>
               <CardTitle className="flex items-center gap-2">
                 <TrendingUp className="h-5 w-5 text-muted-foreground" />
                 Clicks Over Time
               </CardTitle>
             </CardHeader>
             <CardContent>
               {breakdown?.daily && breakdown.daily.length > 0 ? (
                 <div className="h-64 flex items-end justify-between gap-2">
                   {breakdown.daily.map((day, index) => (
                     <div key={index} className="flex flex-col items-center gap-2 w-full group relative">
                        <div 
                          className="w-full bg-blue-500/80 rounded-t-md hover:bg-blue-500 transition-all duration-300"
                          style={{ height: `${Math.max(((day.clicks || 0) / (totalClicks / 5)) * 100, 2)}%` }}
                        />
                        <span className="text-xs text-muted-foreground">{day.date}</span>
                        <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-muted px-2 py-1 rounded text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                          {day.clicks || 0} clicks
                        </div>
                     </div>
                   ))}
                 </div>
               ) : (
                 <div className="h-64 flex items-center justify-center text-muted-foreground">
                   No click data available
                 </div>
               )}
             </CardContent>
           </Card>

           {/* Device Breakdown */}
           <Card>
             <CardHeader>
               <CardTitle className="flex items-center gap-2">
                 <Monitor className="h-5 w-5 text-muted-foreground" />
                 Device Breakdown
               </CardTitle>
             </CardHeader>
             <CardContent>
               <div className="space-y-4">
                 {!deviceTotals || (!deviceTotals.desktop && !deviceTotals.mobile && !deviceTotals.tablet) ? (
                   <div className="text-center py-8 text-muted-foreground">
                     No device data available
                   </div>
                 ) : (
                   <>
                     {deviceTotals.desktop !== undefined && (
                       <div className="space-y-2">
                         <div className="flex justify-between text-sm">
                           <span>Desktop</span>
                           <span className="font-medium">{deviceTotals.desktop.toLocaleString()}</span>
                         </div>
                         <div className="h-2 bg-muted rounded-full overflow-hidden">
                           <div 
                             className="h-full bg-blue-600 rounded-full"
                             style={{ width: `${(deviceTotals.desktop / totalClicks) * 100}%` }}
                           />
                         </div>
                       </div>
                     )}
                     {deviceTotals.mobile !== undefined && (
                       <div className="space-y-2">
                         <div className="flex justify-between text-sm">
                           <span>Mobile</span>
                           <span className="font-medium">{deviceTotals.mobile.toLocaleString()}</span>
                         </div>
                         <div className="h-2 bg-muted rounded-full overflow-hidden">
                           <div 
                             className="h-full bg-emerald-600 rounded-full"
                             style={{ width: `${(deviceTotals.mobile / totalClicks) * 100}%` }}
                           />
                         </div>
                       </div>
                     )}
                     {deviceTotals.tablet !== undefined && (
                       <div className="space-y-2">
                         <div className="flex justify-between text-sm">
                           <span>Tablet</span>
                           <span className="font-medium">{deviceTotals.tablet.toLocaleString()}</span>
                         </div>
                         <div className="h-2 bg-muted rounded-full overflow-hidden">
                           <div 
                             className="h-full bg-purple-600 rounded-full"
                             style={{ width: `${(deviceTotals.tablet / totalClicks) * 100}%` }}
                           />
                         </div>
                       </div>
                     )}
                   </>
                 )}
               </div>
             </CardContent>
           </Card>

           {/* Traffic Sources */}
           <Card>
             <CardHeader>
               <CardTitle className="flex items-center gap-2">
                 <Globe className="h-5 w-5 text-muted-foreground" />
                 Traffic Sources
               </CardTitle>
             </CardHeader>
             <CardContent>
               <div className="space-y-4">
                 {!sourceTotals || (!sourceTotals.linkedin && !sourceTotals.direct && !sourceTotals.referral) ? (
                   <div className="text-center py-8 text-muted-foreground">
                     No source data available
                   </div>
                 ) : (
                   <>
                     {sourceTotals.linkedin !== undefined && (
                       <div className="space-y-2">
                         <div className="flex justify-between text-sm">
                           <span>LinkedIn</span>
                           <span className="font-medium">{sourceTotals.linkedin.toLocaleString()}</span>
                         </div>
                         <div className="h-2 bg-muted rounded-full overflow-hidden">
                           <div 
                             className="h-full bg-[#0a66c2] rounded-full"
                             style={{ width: `${(sourceTotals.linkedin / totalClicks) * 100}%` }}
                           />
                         </div>
                       </div>
                     )}
                     {sourceTotals.direct !== undefined && (
                       <div className="space-y-2">
                         <div className="flex justify-between text-sm">
                           <span>Direct</span>
                           <span className="font-medium">{sourceTotals.direct.toLocaleString()}</span>
                         </div>
                         <div className="h-2 bg-muted rounded-full overflow-hidden">
                           <div 
                             className="h-full bg-gray-600 rounded-full"
                             style={{ width: `${(sourceTotals.direct / totalClicks) * 100}%` }}
                           />
                         </div>
                       </div>
                     )}
                     {sourceTotals.referral !== undefined && (
                       <div className="space-y-2">
                         <div className="flex justify-between text-sm">
                           <span>Referral</span>
                           <span className="font-medium">{sourceTotals.referral.toLocaleString()}</span>
                         </div>
                         <div className="h-2 bg-muted rounded-full overflow-hidden">
                           <div 
                             className="h-full bg-purple-600 rounded-full"
                             style={{ width: `${(sourceTotals.referral / totalClicks) * 100}%` }}
                           />
                         </div>
                       </div>
                     )}
                   </>
                 )}
               </div>
             </CardContent>
           </Card>

           {/* Link Details */}
           <Card>
            <CardHeader>
              <CardTitle>Link Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">Original URL</label>
                  <div className="p-3 bg-muted rounded-md break-all text-sm">
                    <a href={link.original_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                      {link.original_url}
                    </a>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">Short Code</label>
                  <div className="p-3 bg-muted rounded-md font-mono text-sm break-all">
                    {link.short_code}
                  </div>
                </div>
              </div>
              <div className="border-t pt-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <label className="text-muted-foreground text-xs block mb-1">Created</label>
                    <span className="font-medium">
                      {link.created_at ? new Date(link.created_at).toLocaleDateString() : 'N/A'}
                    </span>
                  </div>
                  <div>
                    <label className="text-muted-foreground text-xs block mb-1">Last Clicked</label>
                    <span className="font-medium">
                      {link.last_clicked_at ? new Date(link.last_clicked_at).toLocaleDateString() : 'Never'}
                    </span>
                  </div>
                  <div>
                    <label className="text-muted-foreground text-xs block mb-1">UTM Source</label>
                    <span className="font-medium">{link.utm_source || 'Not set'}</span>
                  </div>
                  <div>
                    <label className="text-muted-foreground text-xs block mb-1">UTM Campaign</label>
                    <span className="font-medium">{link.utm_campaign || 'Not set'}</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </CardContent>
      </Card>
    </div>
  )
}