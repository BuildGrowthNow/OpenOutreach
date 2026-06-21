'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { LeadTable } from '@/components/leads/lead-table'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { getLeads, updateLead, reScrapeLeadProfile, createLead } from '@/lib/api/dashboard'
import { Lead, Pagination } from '@/lib/types/components'
import { exportFilteredLeads } from '@/lib/export'
import { LeadForm } from '@/components/leads/lead-form'

const LeadsPage = () => {
  const router = useRouter()
  
  const [leads, setLeads] = useState<Lead[]>([])
  const [pagination, setPagination] = useState<Pagination | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [disqualifiedFilter, setDisqualifiedFilter] = useState<boolean | undefined>(undefined)
  const [currentPage, setCurrentPage] = useState(1)
  const [showLeadForm, setShowLeadForm] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [stats, setStats] = useState({
    total: 0,
    connected: 0,
    qualified: 0,
    pending: 0,
    completed: 0,
    failed: 0
  })
  
  const limit = 20 // Items per page

  const fetchLeads = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await getLeads(
        statusFilter === 'all' ? undefined : statusFilter,
        search || undefined,
        disqualifiedFilter,
        currentPage,
        limit
      )
      
      if (response.data) {
        setLeads(response.data.data)
        setPagination(response.data.pagination)
        
        // Calculate statistics
        const newStats = {
          total: response.data.pagination?.total || 0,
          connected: response.data.data.filter(lead => lead.state === 'CONNECTED').length,
          qualified: response.data.data.filter(lead => lead.state === 'QUALIFIED').length,
          pending: response.data.data.filter(lead => lead.state === 'PENDING').length,
          completed: response.data.data.filter(lead => lead.state === 'COMPLETED').length,
          failed: response.data.data.filter(lead => lead.state === 'FAILED').length
        }
        setStats(newStats)
        
      } else {
        setError(response.error || 'Failed to fetch leads')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch leads')
    } finally {
      setLoading(false)
    }
  }, [search, statusFilter, disqualifiedFilter, currentPage])

  useEffect(() => {
    void (async () => {
      await fetchLeads()
    })()
  }, [fetchLeads])

  const handleViewLead = (lead: Lead) => {
    router.push(`/leads/${lead.id}`)
  }

  const handleEditLead = (lead: Lead) => {
    // TODO: Implement edit modal using LeadForm
    console.log('Edit lead:', lead)
  }

  const handleDisqualifyLead = async (lead: Lead) => {
    if (!confirm(`Are you sure you want to disqualify ${lead.name || 'this lead'}?`)) {
      return
    }

    try {
      await updateLead(lead.id, { disqualified: true })
      await fetchLeads() // Refresh the list
    } catch (err) {
      alert(`Failed to disqualify lead: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleReScrapeLead = async (lead: Lead) => {
    try {
      const response = await reScrapeLeadProfile(lead.id)
      if (response.data?.success) {
        alert('Profile re-scraped successfully!')
        await fetchLeads() // Refresh the list
      } else {
        alert(`Failed to re-scrape profile: ${response.error || 'Unknown error'}`)
      }
    } catch (err) {
      alert(`Failed to re-scrape profile: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleSearch = (searchTerm: string) => {
    setSearch(searchTerm)
    setCurrentPage(1) // Reset to first page on search
  }

  const handleStatusFilter = (status: string) => {
    setStatusFilter(status)
    setCurrentPage(1) // Reset to first page on filter change
  }

  const handlePageChange = (page: number) => {
    setCurrentPage(page)
  }

  const handleExport = () => {
    exportFilteredLeads(leads, {
      status: statusFilter === 'all' ? undefined : statusFilter,
      search: search || undefined,
      disqualified: disqualifiedFilter
    })
  }

  const handleAddLead = () => {
    setShowLeadForm(true)
  }

  const handleSubmitLead = async (leadData: Partial<Lead>) => {
    try {
      setIsSubmitting(true)
      
      // Create the lead directly using the API
      const leadResponse = await createLead({
        linkedinUrl: leadData.linkedinUrl,
        publicIdentifier: leadData.publicIdentifier,
        name: leadData.name,
      })
      
      if (leadResponse.data) {
        setShowLeadForm(false)
        await fetchLeads() // Refresh the list
      } else {
        throw new Error(leadResponse.error || 'Failed to create lead')
      }
    } catch (err) {
      alert(`Failed to add lead: ${err instanceof Error ? err.message : 'Unknown error'}`)
      throw err
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex-1 space-y-6 p-4 md:p-6 lg:p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Leads Management</h1>
          <p className="text-muted-foreground mt-1">
            Manage and track all your leads in one place
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="px-3 py-1">
            <Icons.Users className="mr-2 h-3.5 w-3.5" />
            {stats.total} Total Leads
          </Badge>
          <Button onClick={handleAddLead}>
            <Icons.UserPlus className="mr-2 h-4 w-4" />
            Add Lead
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          <>
            <Card>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-2" />
                <Skeleton className="h-3 w-32" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-2" />
                <Skeleton className="h-3 w-32" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-2" />
                <Skeleton className="h-3 w-32" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-2" />
                <Skeleton className="h-3 w-32" />
              </CardContent>
            </Card>
          </>
        ) : (
          <>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Total Leads</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total}</div>
                <div className="text-xs text-muted-foreground">
                  Across all campaigns
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Connected</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {stats.connected}
                </div>
                <div className="text-xs text-muted-foreground">
                  {stats.total > 0 ? `${Math.round((stats.connected / stats.total) * 100)}% connection rate` : 'No leads'}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Qualified</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {stats.qualified}
                </div>
                <div className="text-xs text-muted-foreground">
                  Ready for outreach
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Pending</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {stats.pending}
                </div>
                <div className="text-xs text-muted-foreground">
                  Awaiting response
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Main Leads Table */}
      <LeadTable
        leads={leads}
        pagination={pagination || undefined}
        loading={loading}
        onView={handleViewLead}
        onEdit={handleEditLead}
        onDisqualify={handleDisqualifyLead}
        onReScrape={handleReScrapeLead}
        onSearch={handleSearch}
        onStatusFilter={handleStatusFilter}
        onPageChange={handlePageChange}
        onExport={handleExport}
      />

      {/* Filter Options */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filter Options</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-3">
              <div className="font-medium">Status</div>
              <div className="flex flex-wrap gap-2">
                {['all', 'QUALIFIED', 'CONNECTED', 'PENDING', 'COMPLETED', 'FAILED'].map((status) => (
                  <Button
                    key={status}
                    size="sm"
                    variant={statusFilter === status ? 'default' : 'outline'}
                    onClick={() => handleStatusFilter(status)}
                  >
                    {status === 'all' ? 'All' : status.replace('_', ' ').toLowerCase()}
                  </Button>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <div className="font-medium">Disqualified</div>
              <div className="flex flex-wrap gap-2">
                {[undefined, false, true].map((value) => (
                  <Button
                    key={value === undefined ? 'all' : value.toString()}
                    size="sm"
                    variant={(disqualifiedFilter === value) ? 'default' : 'outline'}
                    onClick={() => setDisqualifiedFilter(value)}
                  >
                    {value === undefined ? 'All' : value ? 'Yes' : 'No'}
                  </Button>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <div className="font-medium">Quick Actions</div>
              <div className="flex flex-col gap-2">
                <Button variant="outline" size="sm" onClick={handleExport}>
                  <Icons.Download className="mr-2 h-3.5 w-3.5" />
                  Export All Leads
                </Button>
                <Button variant="outline" size="sm" onClick={() => window.open('https://www.linkedin.com', '_blank')}>
                  <Icons.Globe className="mr-2 h-3.5 w-3.5" />
                  Open LinkedIn
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lead Form Dialog */}
      <LeadForm
        open={showLeadForm}
        onOpenChange={setShowLeadForm}
        onSubmit={handleSubmitLead}
        isSubmitting={isSubmitting}
      />
    </div>
  )
}

export default LeadsPage
