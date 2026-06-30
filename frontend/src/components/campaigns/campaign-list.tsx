'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
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
import { Icons } from '@/lib/types/components'
import { Lead, DealState } from '@/lib/types/components'
import { stateColorMapping } from '@/components/dashboard/campaign-card'
import { cn } from '@/lib/utils'

interface CampaignListProps {
  leads: Lead[]
  campaignId: string
  className?: string
}

export function CampaignList({ leads, campaignId, className }: CampaignListProps) {
  const router = useRouter()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'name' | 'company' | 'state' | 'date'>('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

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
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
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
                      <div className="font-medium">{lead.name || <span className="text-muted-foreground italic">Unnamed Lead</span>}</div>
                      <div className="text-sm text-muted-foreground">{lead.title || <span className="text-muted-foreground italic">Unnamed Lead</span>}</div>
                    </TableCell>
                   <TableCell>{lead.company || <span className="text-muted-foreground italic">Unnamed Lead</span>}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={cn(stateColorMapping[lead.state])}>
                      {lead.state.replace(/_/g, ' ')}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="text-sm">
                      {new Date(lead.creationDate).toLocaleDateString()}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2" onClick={e => e.stopPropagation()}>
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