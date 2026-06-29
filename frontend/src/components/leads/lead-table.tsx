'use client'

import { useState } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Icons } from '@/lib/types/components'
import { LeadStatusBadge } from './lead-status-badge'
import { Lead, Pagination, DealState } from '@/lib/types/components'
import { formatDistanceToNow } from 'date-fns'

interface LeadTableProps {
  leads: Lead[]
  pagination?: Pagination
  loading?: boolean
  onView: (lead: Lead) => void
  onEdit: (lead: Lead) => void
  onDisqualify: (lead: Lead) => void
  onReScrape: (lead: Lead) => void
  onMessage?: (lead: Lead) => void
  onAddToCampaign?: (lead: Lead, campaignId: string) => void
  onSearch: (search: string) => void
  onStatusFilter: (status: string) => void
  onPageChange: (page: number) => void
  onExport?: () => void
}

export function LeadTable({
  leads,
  pagination,
  loading = false,
  onView,
  onEdit,
  onDisqualify,
  onReScrape,
  onMessage,
  onAddToCampaign,
  onSearch,
  onStatusFilter,
  onPageChange,
  onExport
}: LeadTableProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedStatus, setSelectedStatus] = useState<string>('all')
  const [isSearchFocused, setIsSearchFocused] = useState(false)

  const handleSearchChange = (value: string) => {
    setSearchQuery(value)
    // Debounce search - could be improved with useEffect
    if (value !== searchQuery) {
      onSearch(value)
    }
  }

  const handleStatusChange = (status: string) => {
    setSelectedStatus(status)
    onStatusFilter(status)
  }

  const statusOptions = [
    { value: 'all', label: 'All Statuses' },
    { value: 'QUALIFIED', label: 'Qualified' },
    { value: 'READY_TO_CONNECT', label: 'Ready to Connect' },
    { value: 'PENDING', label: 'Pending' },
    { value: 'CONNECTED', label: 'Connected' },
    { value: 'COMPLETED', label: 'Completed' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'NO_EMAIL', label: 'No Email' }
  ]

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Leads</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64">
            <div className="flex flex-col items-center gap-4">
              <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              <div className="text-muted-foreground">Loading leads...</div>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (leads.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Leads</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <Icons.Users className="h-12 w-12 text-muted-foreground" />
            <div className="text-center space-y-2">
              <div className="text-lg font-semibold">No leads found</div>
              <div className="text-muted-foreground">
                {searchQuery || selectedStatus !== 'all'
                  ? 'Try adjusting your search or filters'
                  : 'Start adding leads to see them here'}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <CardTitle>Leads ({pagination?.total || leads.length})</CardTitle>
          <div className="flex flex-col sm:flex-row gap-3">
            {/* Search */}
            <div className={`relative flex-1 sm:w-64 transition-all duration-200 ${isSearchFocused ? 'ring-2 ring-primary ring-offset-2' : ''}`}>
              <Icons.Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name, email, company..."
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                onFocus={() => setIsSearchFocused(true)}
                onBlur={() => setIsSearchFocused(false)}
                className="pl-10"
              />
            </div>

            {/* Status Filter */}
            <Select value={selectedStatus} onValueChange={handleStatusChange}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <Icons.Filter className="mr-2 h-4 w-4" />
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                {statusOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Export Button */}
            {onExport && (
              <Button variant="outline" onClick={onExport}>
                <Icons.Download className="mr-2 h-4 w-4" />
                Export
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px]">Name</TableHead>
                <TableHead>Company & Title</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Updated</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads.map((lead) => (
                <TableRow key={lead.id} className="group hover:bg-muted/50">
                  <TableCell className="font-medium">
                    <div className="flex flex-col">
                      <span className="font-semibold">{lead.name || 'Unnamed Lead'}</span>
                      <span className="text-xs text-muted-foreground">
                        {lead.publicIdentifier}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      {lead.company && (
                        <span className="font-medium">{lead.company}</span>
                      )}
                      {lead.title && (
                        <span className="text-sm text-muted-foreground">{lead.title}</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      {lead.contactInfo?.email && (
                        <a
                          href={`mailto:${lead.contactInfo.email}`}
                          className="text-blue-600 hover:text-blue-800 hover:underline text-sm truncate max-w-[180px]"
                          title={lead.contactInfo.email}
                        >
                          {lead.contactInfo.email}
                        </a>
                      )}
                      {lead.linkedinUrl && (
                        <a
                          href={lead.linkedinUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 hover:underline text-sm truncate max-w-[180px]"
                          title="LinkedIn Profile"
                        >
                          LinkedIn
                          <Icons.ExternalLink className="ml-1 inline h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <LeadStatusBadge state={lead.state} outcome={lead.outcome} />
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="text-sm">
                        {formatDistanceToNow(new Date(lead.updateDate), { addSuffix: true })}
                      </span>
                      {lead.messagesCount !== undefined && (
                        <span className="text-xs text-muted-foreground">
                          {lead.messagesCount} messages
                        </span>
                      )}
                    </div>
                  </TableCell>
                   <TableCell className="text-right">
                     <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                       <Button
                         size="sm"
                         variant="ghost"
                         onClick={() => onView(lead)}
                         title="View details"
                       >
                         <Icons.ExternalLink className="h-4 w-4" />
                       </Button>
                       {onMessage && (
                         <Button
                           size="sm"
                           variant="ghost"
                           onClick={() => onMessage(lead)}
                           title="Send message"
                         >
                           <Icons.MessageSquare className="h-4 w-4" />
                         </Button>
                       )}
                       {onAddToCampaign && (
                         <Button
                           size="sm"
                           variant="ghost"
                           onClick={() => onAddToCampaign(lead, '')}
                           title="Add to campaign"
                         >
                           <Icons.Users className="h-4 w-4" />
                         </Button>
                       )}
                       <Button
                         size="sm"
                         variant="ghost"
                         onClick={() => onReScrape(lead)}
                         title="Re-scrape profile"
                       >
                         <Icons.RefreshCw className="h-4 w-4" />
                       </Button>
                       <Button
                         size="sm"
                         variant="ghost"
                         onClick={() => onEdit(lead)}
                         title="Edit lead"
                       >
                         <Icons.Edit className="h-4 w-4" />
                       </Button>
                       <Button
                         size="sm"
                         variant="ghost"
                         className="text-red-600 hover:text-red-800 hover:bg-red-50"
                         onClick={() => onDisqualify(lead)}
                         title="Disqualify lead"
                       >
                         <Icons.Trash2 className="h-4 w-4" />
                       </Button>
                     </div>
                   </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        {pagination && pagination.total_pages > 1 && (
          <div className="flex items-center justify-between mt-6">
            <div className="text-sm text-muted-foreground">
              Showing {(pagination.page - 1) * pagination.limit + 1} to{' '}
              {Math.min(pagination.page * pagination.limit, pagination.total)} of{' '}
              {pagination.total} results
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(pagination.page - 1)}
                disabled={pagination.page === 1}
              >
                Previous
              </Button>
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                  const pageNum = i + 1
                  return (
                    <Button
                      key={pageNum}
                      variant={pagination.page === pageNum ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => onPageChange(pageNum)}
                    >
                      {pageNum}
                    </Button>
                  )
                })}
                {pagination.total_pages > 5 && (
                  <>
                    <span className="px-2">...</span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onPageChange(pagination.total_pages)}
                    >
                      {pagination.total_pages}
                    </Button>
                  </>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(pagination.page + 1)}
                disabled={pagination.page === pagination.total_pages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}