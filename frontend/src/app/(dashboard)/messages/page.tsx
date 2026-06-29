'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { Send } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getMessages, getCampaigns, sendMessageToLead, getLeads } from '@/lib/api/dashboard'
import { Message, Campaign, Lead, Pagination } from '@/lib/types/components'
import { formatDistanceToNow } from 'date-fns'
import { generateExportFilename } from '@/lib/export'

// Calculate campaign stats helper function
function calculateCampaignStats(msgs: Message[]) {
  const stats: Record<string, { sent: number; received: number; responseRate: number }> = {}
  
  msgs.forEach(msg => {
    if (!stats[msg.dealId]) {
      stats[msg.dealId] = { sent: 0, received: 0, responseRate: 0 }
    }
    
    if (msg.isOutgoing) {
      stats[msg.dealId].sent++
    } else {
      stats[msg.dealId].received++
    }
  })
  
  // Calculate response rates
  Object.keys(stats).forEach(key => {
    const total = stats[key].sent + stats[key].received
    stats[key].responseRate = total > 0 ? Math.round((stats[key].received / total) * 100) : 0
  })
  
  return stats
}

const MessagesPage = () => {
  const router = useRouter()
  
  const [messages, setMessages] = useState<Message[]>([])
  const [pagination, setPagination] = useState<Pagination | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Filters
  const [campaignFilter, setCampaignFilter] = useState<string>('all')
  const [dateRange, setDateRange] = useState<string>('all')
  const [hasResponseFilter, setHasResponseFilter] = useState<string>('all')
  const [search, setSearch] = useState('')
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const limit = 20
  
  // Campaigns for filter
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [campaignsLoading, setCampaignsLoading] = useState(false)
  
  // Message thread modal
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null)
  const [modalMessages, setModalMessages] = useState<Message[]>([])
  const [modalLoading, setModalLoading] = useState(false)
  const [sendingMessage, setSendingMessage] = useState(false)

  // Fetch campaigns for filters
  const fetchCampaigns = useCallback(async () => {
    try {
      setCampaignsLoading(true)
      const response = await getCampaigns()
      if (response.data) {
        setCampaigns(response.data.data || [])
      }
    } catch (err) {
      console.error('Error fetching campaigns:', err)
    } finally {
      setCampaignsLoading(false)
    }
  }, [])

  // Fetch messages
  const fetchMessages = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const filters: Record<string, string> = {}
      if (campaignFilter !== 'all') filters.campaign_id = campaignFilter
      if (search) filters.search = search
      filters.page = currentPage.toString()
      filters.limit = limit.toString()
      
      // For date filtering, we'd pass start_date and end_date as query params
      // Implementation depends on backend support
      
      const response = await getMessages(
        campaignFilter !== 'all' ? campaignFilter : undefined,
        undefined,
        undefined,
        currentPage,
        limit
      )
      
      if (response.data) {
        setMessages(response.data.data || [])
        setPagination(response.data.pagination || null)
      } else {
        setError(response.error || 'Failed to fetch messages')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch messages')
    } finally {
      setLoading(false)
    }
  }, [campaignFilter, currentPage, search])

  // Fetch messages with specific lead_id
  const fetchMessageThread = useCallback(async (leadId: string) => {
    try {
      setModalLoading(true)
      const response = await getMessages(undefined, undefined, leadId)
      if (response.data) {
        setModalMessages(response.data.data || [])
      }
    } catch (err) {
      console.error('Error fetching message thread:', err)
    } finally {
      setModalLoading(false)
    }
  }, [])

  // Calculate stats using useMemo to avoid unnecessary re-renders
  const stats = useMemo(() => {
    const sent = messages.filter(m => m.isOutgoing).length
    const received = messages.filter(m => !m.isOutgoing).length
    const total = sent + received
    const responseRate = total > 0 ? Math.round((received / total) * 100) : 0
    
    return {
      totalSent: sent,
      totalReceived: received,
      responseRate,
      campaigns: calculateCampaignStats(messages)
    }
  }, [messages])

  const handleSendMessageToLead = async (content: string) => {
    if (!selectedMessage) return
    
    try {
      setSendingMessage(true)
      const response = await sendMessageToLead(selectedMessage.dealId, content)
      
      const data = response.data
      if (data && typeof data.success === 'boolean' && data.message !== undefined) {
        // Use conditional check then cast as Message type
        setModalMessages(prev => [...prev, data.message])
      }
    } catch (error) {
      console.error('Failed to send message:', error)
    } finally {
      setSendingMessage(false)
    }
  }

  const handleCampaignChange = (value: string) => {
    setCampaignFilter(value)
    setCurrentPage(1)
  }

  const handleSearch = (value: string) => {
    setSearch(value)
    setCurrentPage(1)
  }

  const handlePageChange = (page: number) => {
    setCurrentPage(page)
  }

  const handleExport = () => {
    const exportData = messages.map(msg => ({
      id: msg.id,
      content: msg.content,
      isOutgoing: msg.isOutgoing ? 'Yes' : 'No',
      sender: msg.sender,
      createdAt: msg.creationDate,
      recipient: msg.recipientName,
      dealId: msg.dealId
    }))
    
    const headers = ['ID', 'Content', 'Is Outgoing', 'Sender', 'Created At', 'Recipient', 'Deal ID']
    const rows = exportData.map(item => [
      item.id,
      `"${item.content.replace(/"/g, '""')}"`,
      item.isOutgoing,
      item.sender,
      item.createdAt,
      `"${item.recipient.replace(/"/g, '""')}"`,
      item.dealId
    ].join(','))
    
    const csvContent = [headers.join(','), ...rows].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    if (link.download !== undefined) {
      const url = URL.createObjectURL(blob)
      link.setAttribute('href', url)
      link.setAttribute('download', generateExportFilename('messages'))
      link.style.visibility = 'hidden'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }
  }

  // Lifecycle - only fetch initial data
  useEffect(() => {
    void (async () => {
      await fetchCampaigns()
      await fetchMessages()
    })()
  }, [fetchCampaigns, fetchMessages])

  if (loading && campaignsLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
        
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map(i => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-2" />
                <Skeleton className="h-3 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
        
        <div className="space-y-4">
          <Skeleton className="h-6 w-1/4" />
          <Skeleton className="h-48 w-full" />
        </div>
      </div>
    )
  }

  const getStatusColor = (isOutgoing: boolean) => {
    return isOutgoing 
      ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
      : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Messages</h1>
          <p className="text-muted-foreground mt-1">
            View and manage all messages across your campaigns
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport}>
            <Icons.Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Sent</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalSent}</div>
            <div className="text-xs text-muted-foreground">
              Messages you've sent
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Received</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalReceived}</div>
            <div className="text-xs text-muted-foreground">
              Responses received
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Response Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.responseRate}%</div>
            <div className="text-xs text-muted-foreground">
              Of messages sent
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Campaigns</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{Object.keys(stats.campaigns).length}</div>
            <div className="text-xs text-muted-foreground">
              With messages
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="all">
        <TabsList className="grid grid-cols-4 w-full md:w-auto">
          <TabsTrigger value="all">All Messages</TabsTrigger>
          <TabsTrigger value="sent">Sent</TabsTrigger>
          <TabsTrigger value="received">Received</TabsTrigger>
          <TabsTrigger value="with-response">With Response</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="space-y-6">
          {/* Filters */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Filters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Campaign Filter */}
                <div className="space-y-2">
                  <Label htmlFor="campaign-filter">Campaign</Label>
                  <Select value={campaignFilter} onValueChange={handleCampaignChange}>
                    <SelectTrigger id="campaign-filter">
                      <SelectValue placeholder="All Campaigns" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Campaigns</SelectItem>
                      {campaigns.map(campaign => (
                        <SelectItem key={campaign.id} value={campaign.id}>
                          {campaign.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Search */}
                <div className="space-y-2">
                  <Label htmlFor="search">Search</Label>
                  <div className="relative">
                    <Icons.Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="search"
                      placeholder="Search by content or lead..."
                      value={search}
                      onChange={(e) => handleSearch(e.target.value)}
                      className="pl-9"
                    />
                  </div>
                </div>

                {/* Date Range */}
                <div className="space-y-2">
                  <Label htmlFor="date-range">Date Range</Label>
                  <Select value={dateRange} onValueChange={setDateRange}>
                    <SelectTrigger id="date-range">
                      <SelectValue placeholder="All Time" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Time</SelectItem>
                      <SelectItem value="today">Today</SelectItem>
                      <SelectItem value="week">Last 7 Days</SelectItem>
                      <SelectItem value="month">Last 30 Days</SelectItem>
                      <SelectItem value="3months">Last 90 Days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Has Response */}
                <div className="space-y-2">
                  <Label htmlFor="response-filter">Response Status</Label>
                  <Select value={hasResponseFilter} onValueChange={setHasResponseFilter}>
                    <SelectTrigger id="response-filter">
                      <SelectValue placeholder="All" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="with">With Response</SelectItem>
                      <SelectItem value="without">No Response</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Messages List */}
          <Card>
            <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-2 sm:space-y-0">
              <div>
                <CardTitle>Messages</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {pagination ? `${pagination.total} total messages` : ''}
                </p>
              </div>
              {pagination && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">
                    Page {pagination.page} of {pagination.total_pages || 1}
                  </span>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handlePageChange(pagination.page - 1)}
                      disabled={pagination.page <= 1}
                    >
                      Previous
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handlePageChange(pagination.page + 1)}
                      disabled={pagination.page >= (pagination.total_pages || 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </CardHeader>
            <CardContent>
              {messages.length === 0 ? (
                <div className="text-center py-12">
                  <Icons.MessageSquare className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No Messages Found</h3>
                  <p className="text-sm text-muted-foreground mb-6">
                    {search || campaignFilter !== 'all' 
                      ? 'Try adjusting your filters' 
                      : 'Start a campaign to begin sending messages'}
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className="flex items-start gap-3 p-4 rounded-lg border hover:bg-muted/30 transition-colors cursor-pointer"
                      onClick={() => {
                        setSelectedMessage(message)
                        void fetchMessageThread(message.dealId)
                      }}
                    >
                      <div className={`flex-shrink-0 w-2 h-2 rounded-full ${
                        message.isOutgoing ? 'bg-blue-500' : 'bg-emerald-500'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className={getStatusColor(message.isOutgoing)}>
                              {message.isOutgoing ? 'Outgoing' : 'Incoming'}
                            </Badge>
                            <span className="font-medium truncate">
                              {message.recipientName || 'Unknown'}
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground flex-shrink-0">
                            {message.creationDate 
                              ? formatDistanceToNow(new Date(message.creationDate), { addSuffix: true })
                              : 'Unknown date'
                            }
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">
                          {message.content}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Pagination */}
              {pagination && pagination.total > limit && (
                <div className="mt-4 flex items-center justify-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handlePageChange(pagination.page - 1)}
                    disabled={pagination.page <= 1}
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {pagination.page} of {pagination.total_pages || 1}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handlePageChange(pagination.page + 1)}
                    disabled={pagination.page >= (pagination.total_pages || 1)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sent" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Sent Messages</CardTitle>
              <p className="text-sm text-muted-foreground">
                {messages.filter(m => m.isOutgoing).length} messages
              </p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {messages.filter(m => m.isOutgoing).map((message) => (
                  <div
                    key={message.id}
                    className="flex items-start gap-3 p-4 rounded-lg border hover:bg-muted/30 transition-colors cursor-pointer"
                    onClick={() => {
                      setSelectedMessage(message)
                      void fetchMessageThread(message.dealId)
                    }}
                  >
                    <div className="flex-shrink-0 w-2 h-2 rounded-full bg-blue-500" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">
                            {message.recipientName || 'Unknown'}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground flex-shrink-0">
                          {message.creationDate 
                            ? formatDistanceToNow(new Date(message.creationDate), { addSuffix: true })
                            : 'Unknown date'
                          }
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {message.content}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="received" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Received Messages</CardTitle>
              <p className="text-sm text-muted-foreground">
                {messages.filter(m => !m.isOutgoing).length} messages
              </p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {messages.filter(m => !m.isOutgoing).map((message) => (
                  <div
                    key={message.id}
                    className="flex items-start gap-3 p-4 rounded-lg border hover:bg-muted/30 transition-colors cursor-pointer"
                    onClick={() => {
                      setSelectedMessage(message)
                      void fetchMessageThread(message.dealId)
                    }}
                  >
                    <div className="flex-shrink-0 w-2 h-2 rounded-full bg-emerald-500" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">
                            {message.recipientName || 'Unknown'}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground flex-shrink-0">
                          {message.creationDate 
                            ? formatDistanceToNow(new Date(message.creationDate), { addSuffix: true })
                            : 'Unknown date'
                          }
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {message.content}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="with-response" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Messages with Responses</CardTitle>
              <p className="text-sm text-muted-foreground">
                {messages.filter(m => m.isOutgoing).map(msg => {
                  const hasResponse = messages.some(m2 => m2.dealId === msg.dealId && !m2.isOutgoing)
                  return hasResponse ? msg : null
                }).filter(Boolean).length} conversations
              </p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Array.from(new Set(
                  messages.filter(m => m.isOutgoing).flatMap(msg => {
                    const hasResponse = messages.some(m2 => m2.dealId === msg.dealId && !m2.isOutgoing)
                    return hasResponse ? [msg.dealId] : []
                  })
                )).map(dealId => {
                  const outgoing = messages.find(m => m.dealId === dealId && m.isOutgoing)
                  return outgoing ? (
                    <div
                      key={dealId}
                      className="flex items-start gap-3 p-4 rounded-lg border hover:bg-muted/30 transition-colors cursor-pointer"
                      onClick={() => {
                        setSelectedMessage(outgoing)
                        void fetchMessageThread(outgoing.dealId)
                      }}
                    >
                      <div className="flex-shrink-0 w-2 h-2 rounded-full bg-blue-500" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                              Responded
                            </Badge>
                            <span className="font-medium truncate">
                              {outgoing.recipientName || 'Unknown'}
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground flex-shrink-0">
                            {outgoing.creationDate 
                              ? formatDistanceToNow(new Date(outgoing.creationDate), { addSuffix: true })
                              : 'Unknown date'
                            }
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">
                          {outgoing.content}
                        </p>
                      </div>
                    </div>
                  ) : null
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Message Thread Modal */}
      {selectedMessage && (
        <Dialog open={!!selectedMessage} onOpenChange={(open) => {
          if (!open) setSelectedMessage(null)
        }}>
          <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>Conversation with {selectedMessage.recipientName || 'Lead'}</DialogTitle>
              <DialogDescription>
                Viewing full conversation thread
              </DialogDescription>
            </DialogHeader>
            
            <div className="flex-1 overflow-hidden">
              <div className="flex flex-col h-full">
                <Card className="flex-1 flex flex-col">
                  <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
                    {modalLoading ? (
                      <div className="flex items-center justify-center h-full">
                        <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                      </div>
                    ) : (
                      modalMessages.length === 0 ? (
                        <div className="text-center py-8">
                          <Icons.MessageSquare className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                          <p className="text-muted-foreground">No messages in this thread yet</p>
                        </div>
                      ) : (
                        modalMessages.map((msg) => (
                          <div
                            key={msg.id}
                            className={`flex ${msg.isOutgoing ? 'justify-end' : 'justify-start'}`}
                          >
                            <div
                              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                                msg.isOutgoing
                                  ? 'bg-blue-600 text-white rounded-br-none'
                                  : 'bg-muted text-foreground rounded-bl-none'
                              }`}
                            >
                              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                              <p className="text-xs mt-1 text-right opacity-70">
                                {msg.creationDate 
                                  ? formatDistanceToNow(new Date(msg.creationDate), { addSuffix: true })
                                  : ''
                                }
                              </p>
                            </div>
                          </div>
                        ))
                      )
                    )}
                  </CardContent>
                  
                  <CardContent className="border-t pt-4">
                    <div className="flex gap-3">
                      <div className="flex-1">
                        <Input
                          id="message-input"
                          placeholder="Type your message..."
                          onKeyDown={async (e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault()
                              const input = e.target as HTMLInputElement
                              if (input.value.trim()) {
                                await handleSendMessageToLead(input.value.trim())
                                input.value = ''
                              }
                            }
                          }}
                        />
                      </div>
                      <Button
                        onClick={async () => {
                          const input = document.getElementById('message-input') as HTMLInputElement
                          if (input?.value?.trim()) {
                            await handleSendMessageToLead(input.value.trim())
                            input.value = ''
                          }
                        }}
                        disabled={sendingMessage}
                      >
                        {sendingMessage ? (
                          <Icons.RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <Send className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

export default MessagesPage