'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { updateDealState } from '@/lib/api/dashboard'
import { useToast } from '@/components/ui/use-toast'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Icons } from '@/lib/types/components'
import { Lead, DealState } from '@/lib/types/components'
import { stateColorMapping } from '@/components/dashboard/campaign-card'
import { cn } from '@/lib/utils'

interface CampaignListProps {
  leads: Lead[]
  campaignId: string
  className?: string
  onLeadsUpdated?: () => void
}

export function CampaignList({ leads, campaignId, className, onLeadsUpdated }: CampaignListProps) {
  const router = useRouter()
  const { toast } = useToast()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'name' | 'company' | 'state' | 'date'>('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [updatingLeadId, setUpdatingLeadId] = useState<string | null>(null)

  // Filter leads based on search and status
  const filteredLeads = leads.filter(lead => {
    const matchesSearch =
      lead.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lead.company?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lead.title?.toLowerCase().includes(searchQuery.toLowerCase())

    const matchesStatus = statusFilter === 'all' || lead.state === statusFilter

    return matchesSearch && matchesStatus
  })

  // Sort leads
  const sortedLeads = [...filteredLeads].sort((a, b) => {
    let aValue, bValue

    switch (sortBy) {
      case 'name':
        aValue = a.name || ''
        bValue = b.name || ''
        break
      case 'company':
        aValue = a.company || ''
        bValue = b.company || ''
        break
      case 'state':
        aValue = a.state
        bValue = b.state
        break
      case 'date':
        aValue = new Date(a.creationDate).getTime()
        bValue = new Date(b.creationDate).getTime()
        break
    }

    if (sortOrder === 'asc') {
      return aValue > bValue ? 1 : -1
    } else {
      return aValue < bValue ? 1 : -1
    }
  })

  const handleLeadClick = (leadId: string) => {
    router.push(`/leads/${leadId}`)
  }

  const handleCopyEmail = (email: string, e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(email).then(() => {
      toast({ title: 'Email copied', description: email })
    })
  }

  const handleSort = (field: 'name' | 'company' | 'state' | 'date') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('asc')
    }
  }

  const getSortIcon = (field: string) => {
    if (sortBy !== field) return null
    return sortOrder === 'asc' ? <Icons.ChevronUp className="h-4 w-4" /> : <Icons.ChevronDown className="h-4 w-4" />
  }

  const handleQualify = async (leadId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setUpdatingLeadId(leadId)
    try {
      const response = await updateDealState(leadId, campaignId, 'Qualified')
      if (response.data?.success) {
        toast({
          title: 'Lead Qualified',
          description: 'Lead has been manually qualified and will be processed.',
        })
        onLeadsUpdated?.()
      } else {
        throw new Error(response.error || 'Failed to qualify lead')
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to qualify lead',
        variant: 'destructive',
      })
    } finally {
      setUpdatingLeadId(null)
    }
  }

  const handleDisqualify = async (leadId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setUpdatingLeadId(leadId)
    try {
      const response = await updateDealState(leadId, campaignId, 'Failed')
      if (response.data?.success) {
        toast({
          title: 'Lead Disqualified',
          description: 'Lead has been marked as failed.',
        })
        onLeadsUpdated?.()
      } else {
        throw new Error(response.error || 'Failed to disqualify lead')
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to disqualify lead',
        variant: 'destructive',
      })
    } finally {
      setUpdatingLeadId(null)
    }
  }

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search leads by name, company, or title..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="max-w-lg"
          />
        </div>
        <div className="flex gap-2">
          <Select value={statusFilter} onValueChange={(value: string | null) => {
            if (value) setStatusFilter(value)
          }}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="DISCOVERED">Discovered</SelectItem>
              <SelectItem value="QUALIFIED">Qualified</SelectItem>
              <SelectItem value="READY_TO_CONNECT">Ready to Connect</SelectItem>
              <SelectItem value="PENDING">Pending</SelectItem>
              <SelectItem value="CONNECTED">Connected</SelectItem>
              <SelectItem value="COMPLETED">Completed</SelectItem>
              <SelectItem value="FAILED">Failed</SelectItem>
              <SelectItem value="NO_EMAIL">No Email</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="cursor-pointer" onClick={() => handleSort('name')}>
                <div className="flex items-center gap-2">
                  Name
                  {getSortIcon('name')}
                </div>
              </TableHead>
              <TableHead className="cursor-pointer" onClick={() => handleSort('company')}>
                <div className="flex items-center gap-2">
                  Company
                  {getSortIcon('company')}
                </div>
              </TableHead>
              <TableHead className="cursor-pointer" onClick={() => handleSort('state')}>
                <div className="flex items-center gap-2">
                  Status
                  {getSortIcon('state')}
                </div>
              </TableHead>
              <TableHead className="cursor-pointer" onClick={() => handleSort('date')}>
                <div className="flex items-center gap-2">
                  Created
                  {getSortIcon('date')}
                </div>
              </TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedLeads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <Icons.Users className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    {searchQuery
                      ? 'No leads match your search. Try adjusting your search query.'
                      : 'No leads found in this campaign yet. Start adding leads to track progress.'}
                  </p>
                  {searchQuery && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSearchQuery('')}
                      className="mt-2"
                    >
                      Clear search
                    </Button>
                  )}
                  {!searchQuery && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => router.push(`/campaigns/${campaignId}/leads`)}
                      className="mt-2"
                    >
                      <Icons.Download className="mr-2 h-4 w-4" />
                      Add Leads
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              sortedLeads.map(lead => (
                <TableRow
                  key={lead.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => handleLeadClick(lead.id)}
                >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div>
                          <div className="flex items-center gap-1.5 font-medium">
                            {lead.name || <span className="text-muted-foreground italic">Unknown</span>}
                            {lead.contactInfo?.email && (
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <button
                                      className="text-muted-foreground hover:text-foreground transition-colors"
                                      onClick={(e) => handleCopyEmail(lead.contactInfo!.email!, e)}
                                      aria-label={`Copy email: ${lead.contactInfo.email}`}
                                    >
                                      <Icons.Mail className="h-3.5 w-3.5" />
                                    </button>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>{lead.contactInfo.email}</p>
                                    <p className="text-xs text-muted-foreground">Click to copy</p>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            )}
                          </div>
                          <div className="text-sm text-muted-foreground" title={lead.title || undefined}>{lead.title ? (lead.title.length > 25 ? lead.title.slice(0, 25) + '…' : lead.title) : <span className="text-muted-foreground">—</span>}</div>
                        </div>
                        {lead.state === 'QUALIFIED' && (
                          <Badge variant="outline" className="border-emerald-500/20 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10">
                            <Icons.CheckCircle2 className="h-3 w-3 mr-1" />
                            AI Qualified
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                   <TableCell><span title={lead.company || undefined}>{lead.company ? (lead.company.length > 25 ? lead.company.slice(0, 25) + '…' : lead.company) : <span className="text-muted-foreground">—</span>}</span></TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge variant="outline" className={cn(stateColorMapping[lead.state])}>
                              {lead.state.replace(/_/g, ' ')}
                            </Badge>
                          </TooltipTrigger>
                          {lead.state === 'NO_EMAIL' && (
                            <TooltipContent>
                              <p className="font-medium">No email found</p>
                              <p className="text-xs text-muted-foreground max-w-[220px]">
                                Email enrichment returned no result. The daemon retries automatically. Add an email manually on the lead page to unblock.
                              </p>
                            </TooltipContent>
                          )}
                        </Tooltip>
                      </TooltipProvider>
                      {lead.state === 'CONNECTED' && !!lead.unansweredCount && lead.unansweredCount > 0 && (
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-xs text-amber-500 cursor-default">
                                {lead.nextFollowUpAt && new Date(lead.nextFollowUpAt) > new Date()
                                  ? `Next msg in ${Math.ceil((new Date(lead.nextFollowUpAt).getTime() - Date.now()) / 86400000)}d`
                                  : `${lead.unansweredCount} unanswered`}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="font-medium">{lead.unansweredCount} unanswered message{lead.unansweredCount !== 1 ? 's' : ''}</p>
                              <p className="text-xs text-muted-foreground max-w-[220px]">
                                Waiting {lead.unansweredCount} × 3 days between nudges.
                                {lead.nextFollowUpAt ? ` Next message after ${new Date(lead.nextFollowUpAt).toLocaleDateString()}.` : ''}
                              </p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="text-sm">
                      {new Date(lead.creationDate).toLocaleDateString()}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                      {lead.state === 'DISCOVERED' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => handleQualify(lead.id, e)}
                          disabled={updatingLeadId === lead.id}
                          className="border-emerald-500/20 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10"
                        >
                          {updatingLeadId === lead.id ? (
                            <Icons.RefreshCw className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <Icons.CheckCircle2 className="h-4 w-4 mr-1" />
                              Qualify
                            </>
                          )}
                        </Button>
                      )}
                      {(lead.state === 'DISCOVERED' || lead.state === 'QUALIFIED') && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => handleDisqualify(lead.id, e)}
                          disabled={updatingLeadId === lead.id}
                          className="border-red-500/20 text-red-600 dark:text-red-400 hover:bg-red-500/10"
                        >
                          {updatingLeadId === lead.id ? (
                            <Icons.RefreshCw className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <Icons.XCircle className="h-4 w-4 mr-1" />
                              Disqualify
                            </>
                          )}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleLeadClick(lead.id)}
                      >
                        <Icons.ExternalLink className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <div>
          Showing {sortedLeads.length} of {leads.length} leads
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => router.push('/leads')}
          >
            <Icons.UserPlus className="mr-2 h-4 w-4" />
            Add More Leads
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => router.push(`/campaigns/${campaignId}/leads`)}
          >
            <Icons.Users className="mr-2 h-4 w-4" />
            View All
          </Button>
        </div>
      </div>
    </div>
  )
}