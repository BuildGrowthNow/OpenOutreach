'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { getCampaignLeads, getCampaign } from '@/lib/api/dashboard'
import { cn } from '@/lib/utils'
import { CampaignList } from '@/components/campaigns/campaign-list'
import { Lead } from '@/lib/types/components'

export default function CampaignLeadsPage() {
  const params = useParams()
  const campaignId = params.id as string

  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage] = useState(20)

  const fetchCampaignData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch campaign details
      const campaignResponse = await getCampaign(campaignId)
      if (!campaignResponse.data) {
        setError(campaignResponse.error || campaignResponse.message || 'Failed to fetch campaign')
      }

      // Fetch campaign leads
      const leadsResponse = await getCampaignLeads(campaignId)
      if (leadsResponse.data) {
        setLeads(leadsResponse.data.data || [])
      } else {
        setError(leadsResponse.error || leadsResponse.message || 'Failed to fetch campaign leads')
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

  const refreshData = async () => {
    await fetchCampaignData()
  }

  const filteredLeads = useMemo(() => {
    let filtered = [...leads]

    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase()
      filtered = filtered.filter(lead =>
        (lead.name && lead.name.toLowerCase().includes(term)) ||
        (lead.company && lead.company.toLowerCase().includes(term)) ||
        (lead.title && lead.title.toLowerCase().includes(term)) ||
        (lead.contactInfo?.email && lead.contactInfo.email.toLowerCase().includes(term))
      )
    }

    if (statusFilter !== 'all') {
      const stateMap: Record<string, Lead['state']> = {
        new: 'PENDING',
        contacted: 'CONNECTED',
        qualified: 'QUALIFIED',
        converted: 'COMPLETED',
        disqualified: 'FAILED',
      }
      const dealState = stateMap[statusFilter.toLowerCase()]
      if (dealState) {
        filtered = filtered.filter(lead => lead.state === dealState)
      }
    }

    return filtered
  }, [leads, searchTerm, statusFilter])

  const getStatusBadge = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'new':
        return 'border-blue-500/20 text-blue-600 dark:text-blue-400 bg-blue-500/10'
      case 'contacted':
        return 'border-purple-500/20 text-purple-600 dark:text-purple-400 bg-purple-500/10'
      case 'qualified':
        return 'border-emerald-500/20 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10'
      case 'disqualified':
        return 'border-red-500/20 text-red-600 dark:text-red-400 bg-red-500/10'
      case 'converted':
        return 'border-orange-500/20 text-orange-600 dark:text-orange-400 bg-orange-500/10'
      default:
        return 'border-gray-500/20 text-gray-600 dark:text-gray-400 bg-gray-500/10'
    }
  }

  // Pagination calculations
  const totalPages = Math.ceil(filteredLeads.length / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const paginatedLeads = filteredLeads.slice(startIndex, endIndex)

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
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
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
            <Icons.ChevronLeft className="mr-2 h-4 w-4" />
            Back to Campaign
          </Button>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => window.history.back()}>
          <Icons.ChevronLeft className="mr-2 h-4 w-4" />
          Back to Campaign
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Campaign Stats Card */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{leads.length}</div>
              <div className="text-sm text-muted-foreground">Total Leads</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{leads.filter(l => l.state === 'QUALIFIED').length}</div>
              <div className="text-sm text-muted-foreground">Qualified Leads</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{leads.filter(l => l.state === 'COMPLETED').length}</div>
              <div className="text-sm text-muted-foreground">Converted</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{leads.filter(l => l.state === 'FAILED').length}</div>
              <div className="text-sm text-muted-foreground">Disqualified</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filters and Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            <div className="flex-1">
              <div className="relative">
                <Icons.Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search leads by name, company, title, or email..."
                  className="pl-10"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>
            <div className="w-full md:w-48">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="new">New</SelectItem>
                  <SelectItem value="contacted">Contacted</SelectItem>
                  <SelectItem value="qualified">Qualified</SelectItem>
                  <SelectItem value="converted">Converted</SelectItem>
                  <SelectItem value="disqualified">Disqualified</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results Summary */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Showing {paginatedLeads.length} of {filteredLeads.length} leads
          {searchTerm && ` matching "${searchTerm}"`}
          {statusFilter !== 'all' && ` with status "${statusFilter}"`}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
            disabled={currentPage === 1}
          >
            <Icons.ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm">
            Page {currentPage} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
            disabled={currentPage === totalPages}
          >
            <Icons.ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Leads Table */}
      {leads.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Campaign Leads</CardTitle>
            <CardDescription>All leads associated with this campaign</CardDescription>
          </CardHeader>
          <CardContent>
            <CampaignList leads={paginatedLeads} campaignId={campaignId} />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12">
            <div className="text-center">
              <Icons.Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Leads Yet</h3>
              <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
                Start adding leads to this campaign to see them here. Leads can be added from the main leads page.
              </p>
              <Button onClick={() => window.location.href = '/leads'}>
                <Icons.UserPlus className="mr-2 h-4 w-4" />
                Visit Leads Page
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Lead Status Distribution */}
      <Card>
        <CardHeader>
          <CardTitle>Lead Status Distribution</CardTitle>
          <CardDescription>Breakdown of leads by status</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { status: 'PENDING', label: 'New', color: 'bg-blue-500' },
                { status: 'CONNECTED', label: 'Contacted', color: 'bg-purple-500' },
                { status: 'QUALIFIED', label: 'Qualified', color: 'bg-emerald-500' },
                { status: 'COMPLETED', label: 'Converted', color: 'bg-orange-500' },
                { status: 'FAILED', label: 'Disqualified', color: 'bg-red-500' },
              ].map(({ status, label, color }) => {
                const count = leads.filter(l => l.state === status).length
                const percentage = leads.length > 0 ? Math.round((count / leads.length) * 100) : 0

                return (
                  <div key={status} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className={cn('text-xs', getStatusBadge(status))}>
                          {label}
                        </Badge>
                        <span className="font-medium">{count}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">{percentage}%</span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                      <div
                        className={`${color} h-2 rounded-full transition-all duration-300`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lead Source Analysis */}
      <Card>
        <CardHeader>
          <CardTitle>Lead Source Analysis</CardTitle>
          <CardDescription>Where your campaign leads are coming from</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Lead source analysis requires additional data fields that are not currently available</p>
        </CardContent>
      </Card>

      {/* Lead Quality Score */}
      <Card>
        <CardHeader>
          <CardTitle>Lead Quality Score</CardTitle>
          <CardDescription>Quality metrics for campaign leads</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Lead quality scoring requires additional data fields that are not currently available</p>
        </CardContent>
      </Card>

      {/* Export and Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Export & Actions</CardTitle>
          <CardDescription>Manage campaign leads</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline">
              <Icons.Download className="mr-2 h-4 w-4" />
              Export All Leads
            </Button>
            <Button variant="outline">
              <Icons.FileText className="mr-2 h-4 w-4" />
              Export Filtered Leads
            </Button>
            <Button variant="outline">
              <Icons.Plus className="mr-2 h-4 w-4" />
              Add Selected to List
            </Button>
            <Button variant="outline">
              <Icons.Filter className="mr-2 h-4 w-4" />
              Bulk Update Status
            </Button>
            <Button variant="outline">
              <Icons.Tag className="mr-2 h-4 w-4" />
              Bulk Add Tags
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
