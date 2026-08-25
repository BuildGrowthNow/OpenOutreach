'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { Phone, Smartphone, Upload } from 'lucide-react'
import { getCampaignLeads, getCampaign, exportLeads, importCsvLeads } from '@/lib/api/dashboard'
import { cn } from '@/lib/utils'
import { CampaignList } from '@/components/campaigns/campaign-list'
import { Lead } from '@/lib/types/components'

export default function CampaignLeadsPage() {
  const params = useParams()
  const campaignId = params.id as string

  const [leads, setLeads] = useState<Lead[]>([])
  const [pipelineCounts, setPipelineCounts] = useState<Record<string, number>>({})
  const [totalLeads, setTotalLeads] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [campaignStatus, setCampaignStatus] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 20
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ added: number; skipped: number; errors: string[] } | null>(null)
  const [channelFilter, setChannelFilter] = useState<'all' | 'linkedin' | 'whatsapp'>('all')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchCampaignData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch campaign details
      const campaignResponse = await getCampaign(campaignId)
      if (!campaignResponse.data) {
        setError(campaignResponse.error || campaignResponse.message || 'Failed to fetch campaign')
      } else {
        setCampaignStatus(campaignResponse.data.status ?? null)
      }

      // Fetch campaign leads with server-side pagination
      const isHoldFilter = statusFilter === 'NEEDS_REVIEW'
      const leadsResponse = await getCampaignLeads(
        campaignId,
        isHoldFilter ? undefined : (statusFilter !== 'all' ? statusFilter : undefined),
        debouncedSearch || undefined,
        currentPage,
        itemsPerPage,
        isHoldFilter ? true : undefined,
      )
      if (leadsResponse.data) {
        setLeads(leadsResponse.data.data || [])
        setPipelineCounts(leadsResponse.data.pipelineCounts || {})
        setTotalLeads(leadsResponse.data.pagination?.total ?? 0)
        setTotalPages(leadsResponse.data.pagination?.total_pages ?? 1)
      } else {
        setError(leadsResponse.error || leadsResponse.message || 'Failed to fetch campaign leads')
      }
    } catch (err) {
      setError('An error occurred while fetching campaign data')
      console.error('Error fetching campaign data:', err)
    } finally {
      setLoading(false)
    }
  }, [campaignId, statusFilter, debouncedSearch, currentPage])

  // Debounce search input 400 ms before triggering a server fetch
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm)
      setCurrentPage(1)
    }, 400)
    return () => clearTimeout(timer)
  }, [searchTerm])

  // Reset to page 1 when status filter changes
  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter])

  useEffect(() => {
    void (async () => {
      await fetchCampaignData()
    })()
  }, [fetchCampaignData])

  const refreshData = async () => {
    await fetchCampaignData()
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)
    try {
      const text = await file.text()
      const result = await importCsvLeads(campaignId, text)
      setImportResult(result)
      if (result.added > 0) refreshData()
    } catch (err) {
      setImportResult({ added: 0, skipped: 0, errors: [err instanceof Error ? err.message : 'Import failed'] })
    } finally {
      setImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleExport = async (filtered: boolean) => {
    setExporting(true)
    try {
      await exportLeads(campaignId, filtered && statusFilter !== 'all' ? statusFilter : undefined)
    } catch (err) {
      console.error('Export error:', err)
    } finally {
      setExporting(false)
    }
  }

  // Server handles status/search filtering; channel filter is client-side
  const filteredLeads = channelFilter === 'all'
    ? leads
    : leads.filter(l => (l.activeChannel || 'linkedin') === channelFilter)

  const getStatusBadge = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'DISCOVERED':
        return 'border-zinc-500/20 text-zinc-600 dark:text-zinc-400 bg-zinc-500/10'
      case 'QUALIFIED':
        return 'border-blue-500/20 text-blue-600 dark:text-blue-400 bg-blue-500/10'
      case 'READY_TO_CONNECT':
        return 'border-indigo-500/20 text-indigo-600 dark:text-indigo-400 bg-indigo-500/10'
      case 'PENDING':
        return 'border-purple-500/20 text-purple-600 dark:text-purple-400 bg-purple-500/10'
      case 'CONNECTED':
        return 'border-emerald-500/20 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10'
      case 'COMPLETED':
        return 'border-orange-500/20 text-orange-600 dark:text-orange-400 bg-orange-500/10'
      case 'FAILED':
        return 'border-red-500/20 text-red-600 dark:text-red-400 bg-red-500/10'
      case 'NO_EMAIL':
        return 'border-gray-500/20 text-gray-500 dark:text-gray-400 bg-gray-500/10'
      default:
        return 'border-gray-500/20 text-gray-600 dark:text-gray-400 bg-gray-500/10'
    }
  }

  // Server-side pagination - leads is already the current page slice
  const paginatedLeads = filteredLeads

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
    <div className="space-y-6 pb-10">
      {/* Campaign Stats Card */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">
                {(pipelineCounts.discovered ?? 0) + (pipelineCounts.qualified ?? 0) + (pipelineCounts.readyToConnect ?? 0) + (pipelineCounts.pending ?? 0) + (pipelineCounts.connected ?? 0) + (pipelineCounts.completed ?? 0) + (pipelineCounts.failed ?? 0)}
              </div>
              <div className="text-sm text-muted-foreground">Total Leads</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{pipelineCounts.qualified ?? 0}</div>
              <div className="text-sm text-muted-foreground">Qualified Leads</div>
            </div>
            {(pipelineCounts.needsReview ?? 0) > 0 && (
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">{pipelineCounts.needsReview}</div>
                <div className="text-sm text-muted-foreground">Needs Review</div>
              </div>
            )}
            <div className="text-center">
              <div className="text-2xl font-bold">{pipelineCounts.completed ?? 0}</div>
              <div className="text-sm text-muted-foreground">Done</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{pipelineCounts.failed ?? 0}</div>
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
              <Select value={statusFilter} onValueChange={(value: string | null) => {
                if (value) setStatusFilter(value)
              }}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="NEEDS_REVIEW">Needs Review</SelectItem>
                  <SelectItem value="DISCOVERED">Discovered</SelectItem>
                  <SelectItem value="QUALIFIED">Qualified</SelectItem>
                  <SelectItem value="READY_TO_CONNECT">Ready to Connect</SelectItem>
                  <SelectItem value="PENDING">Pending</SelectItem>
                  <SelectItem value="CONNECTED">Connected</SelectItem>
                  <SelectItem value="COMPLETED">Done</SelectItem>
                  <SelectItem value="FAILED">Failed</SelectItem>
                  <SelectItem value="NO_EMAIL">No Email</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* Channel filter pills */}
            <div className="flex gap-1.5 shrink-0">
              {(['all', 'linkedin', 'whatsapp'] as const).map((ch) => (
                <button
                  key={ch}
                  onClick={() => setChannelFilter(ch)}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors',
                    channelFilter === ch
                      ? 'bg-foreground text-background border-foreground'
                      : 'bg-transparent text-muted-foreground border-border hover:border-foreground/40'
                  )}
                >
                  {ch === 'linkedin' && <Phone className="h-3 w-3" />}
                  {ch === 'whatsapp' && <Smartphone className="h-3 w-3" />}
                  {ch === 'all' ? 'All' : ch === 'linkedin' ? 'LinkedIn' : 'WhatsApp'}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results Summary */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Showing {paginatedLeads.length} of {totalLeads} leads
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
            disabled={currentPage >= totalPages}
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
            {campaignStatus === 'active' ? (
              <div className="text-center space-y-4">
                <div className="flex items-center justify-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.3s]" />
                  <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.15s]" />
                  <span className="h-2.5 w-2.5 rounded-full bg-blue-500 animate-bounce" />
                </div>
                <h3 className="text-lg font-semibold">Discovering leads…</h3>
                <p className="text-sm text-muted-foreground max-w-md mx-auto">
                  The daemon is searching LinkedIn and qualifying prospects against your ICP. First leads appear within a few minutes.
                </p>
              </div>
            ) : (
              <div className="text-center">
                <Icons.Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Leads Yet</h3>
                <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
                  Activate this campaign to start discovering leads automatically.
                </p>
              </div>
            )}
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
                { status: 'DISCOVERED', key: 'discovered', label: 'Discovered', color: 'bg-zinc-500' },
                { status: 'QUALIFIED', key: 'qualified', label: 'Qualified', color: 'bg-blue-500' },
                { status: 'PENDING', key: 'pending', label: 'Pending', color: 'bg-purple-500' },
                { status: 'CONNECTED', key: 'connected', label: 'Connected', color: 'bg-emerald-500' },
                { status: 'COMPLETED', key: 'completed', label: 'Done', color: 'bg-orange-500' },
                { status: 'FAILED', key: 'failed', label: 'Failed', color: 'bg-red-500' },
                { status: 'NO_EMAIL', key: 'noEmail', label: 'No Email', color: 'bg-gray-400' },
              ].map(({ status, key, label, color }) => {
                const count = pipelineCounts[key] ?? 0
                const total = Object.values(pipelineCounts).reduce((a, b) => a + b, 0)
                const percentage = total > 0 ? Math.round((count / total) * 100) : 0

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
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => handleExport(false)} disabled={exporting}>
              {exporting ? <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Icons.Download className="mr-2 h-4 w-4" />}
              Export All Leads
            </Button>
            <Button variant="outline" onClick={() => handleExport(true)} disabled={exporting}>
              {exporting ? <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Icons.FileText className="mr-2 h-4 w-4" />}
              Export Filtered Leads
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={handleImport}
            />
            <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={importing}>
              {importing ? <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
              Import CSV
            </Button>
          </div>
          {importResult && (
            <div className={cn(
              'rounded-md px-4 py-2 text-sm',
              importResult.errors.length > 0
                ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
            )}>
              {importResult.errors.length > 0
                ? `Import error: ${importResult.errors[0]}`
                : `Imported ${importResult.added} new lead${importResult.added !== 1 ? 's' : ''}, skipped ${importResult.skipped} existing.`
              }
            </div>
          )}
        </CardContent>
      </Card>
    </div>

  )
}
