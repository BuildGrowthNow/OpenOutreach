'use client'

import { useState } from 'react'
import { format } from 'date-fns'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'
import { Message } from '@/lib/types/components'

interface MessageListProps {
  messages: Message[]
  isLoading?: boolean
  showActions?: boolean
  onViewLead?: (leadId: string, leadName: string) => void
  onViewCampaign?: (campaignId: string, campaignName: string) => void
}

export function MessageList({
  messages,
  isLoading = false,
  showActions = false,
  onViewLead,
  onViewCampaign
}: MessageListProps) {
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set())

  // Group messages by date
  const groupedMessages = messages.reduce<Record<string, Message[]>>((groups, message) => {
    if (!message.creationDate) return groups

    const date = new Date(message.creationDate)
    const dateKey = format(date, 'yyyy-MM-dd')
    
    if (!groups[dateKey]) {
      groups[dateKey] = []
    }
    
    groups[dateKey].push(message)
    return groups
  }, {})

  const toggleExpand = (messageId: string) => {
    const newExpanded = new Set(expandedMessages)
    if (newExpanded.has(messageId)) {
      newExpanded.delete(messageId)
    } else {
      newExpanded.add(messageId)
    }
    setExpandedMessages(newExpanded)
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Messages</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="space-y-3">
              <div className="flex items-center gap-3">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
              <Skeleton className="h-16 w-full" />
              <Separator />
            </div>
          ))}
        </CardContent>
      </Card>
    )
  }

  if (messages.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Messages</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center h-64">
          <Icons.MessageSquare className="h-12 w-12 text-muted-foreground mb-4" />
          <div className="text-muted-foreground">No messages found</div>
          <div className="text-sm text-muted-foreground mt-1">
            All message history will appear here
          </div>
        </CardContent>
      </Card>
    )
  }

  const sortedDates = Object.keys(groupedMessages).sort((a, b) => new Date(b).getTime() - new Date(a).getTime())

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Messages ({messages.length})
          {showActions && (
            <div className="flex items-center gap-2 mt-2">
              <Button size="sm" variant="outline">
                <Icons.Filter className="mr-2 h-3.5 w-3.5" />
                Filter
              </Button>
              <Button size="sm" variant="outline">
                <Icons.Download className="mr-2 h-3.5 w-3.5" />
                Export
              </Button>
            </div>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {sortedDates.map((dateKey) => {
          const currentDate = new Date(dateKey)
          const messagesForDate = groupedMessages[dateKey]
          
          return (
            <div key={dateKey} className="space-y-4">
              {/* Date Header */}
              <div className="flex items-center gap-3">
                <div className="h-px flex-1 bg-border" />
                <div className="text-sm font-medium text-muted-foreground shrink-0">
                  {format(currentDate, 'EEEE, MMMM d, yyyy')}
                </div>
                <div className="h-px flex-1 bg-border" />
              </div>

              {/* Messages for this date */}
              <div className="space-y-4">
                {messagesForDate.map((message) => {
                  const isExpanded = expandedMessages.has(message.id)
                  const isOutgoing = message.isOutgoing

                  return (
                    <div
                      key={message.id}
                      className={cn(
                        'border rounded-lg p-4 transition-colors',
                        isOutgoing 
                          ? 'bg-blue-50 border-blue-200' 
                          : 'bg-white border-gray-200'
                      )}
                    >
                      {/* Message Header */}
                      <div className="flex justify-between items-start mb-3">
                        <div className="flex items-center gap-3">
                          <div className="flex flex-col">
                            <div className="font-medium flex items-center gap-2">
                              {isOutgoing ? 'Me' : message.sender === 'me' ? 'Me' : message.sender}
                              {message.creationDate && (
                                <Badge variant="outline" className="text-xs">
                                  {format(new Date(message.creationDate), 'h:mm a')}
                                </Badge>
                              )}
                            </div>
                            
                            {/* Recipient Info */}
                            <div className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                              <span>To:</span>
                              {onViewLead && message.dealId && message.recipientName && (
                                <Button
                                  variant="link"
                                  className="h-auto p-0 text-sm"
                                  onClick={() => onViewLead(message.dealId!, message.recipientName!)}
                                >
                                  {message.recipientName}
                                  <Icons.ExternalLink className="ml-1 h-3 w-3" />
                                </Button>
                              )}
                              {!onViewLead && message.recipientName && (
                                <span>{message.recipientName}</span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Message Status */}
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={isOutgoing ? 'outline' : 'secondary'}
                            className={cn(
                              'text-xs',
                              isOutgoing 
                                ? 'border-blue-600 text-blue-600' 
                                : 'text-gray-600 border-gray-600'
                            )}
                          >
                            {isOutgoing ? 'Sent' : 'Received'}
                          </Badge>
                          {showActions && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => toggleExpand(message.id)}
                            >
                              {isExpanded ? (
                                <Icons.ChevronUp className="h-4 w-4" />
                              ) : (
                                <Icons.ChevronDown className="h-4 w-4" />
                              )}
                            </Button>
                          )}
                        </div>
                      </div>

                      {/* Message Content */}
                      <div className="mb-3">
                        <div className="whitespace-pre-wrap">{message.content}</div>
                      </div>

                      {/* Expanded Details */}
                      {isExpanded && showActions && (
                        <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
                          <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                              <div className="font-medium">Campaign</div>
                              {onViewCampaign && message.dealId && (
                                <Button
                                  variant="link"
                                  className="h-auto p-0 text-sm"
                                  onClick={() => onViewCampaign(message.dealId!, 'Unknown Campaign')}
                                >
                                  View Campaign
                                  <Icons.ExternalLink className="ml-1 h-3 w-3" />
                                </Button>
                              )}
                              {!onViewCampaign && (
                                <div className="text-muted-foreground">No campaign assigned</div>
                              )}
                            </div>
                            <div>
                              <div className="font-medium">LinkedIn URL</div>
                              {message.recipientUrl ? (
                                <a
                                  href={message.recipientUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:underline text-sm truncate block"
                                >
                                  View Profile
                                  <Icons.ExternalLink className="ml-1 h-3 w-3 inline" />
                                </a>
                              ) : (
                                <div className="text-muted-foreground">Not available</div>
                              )}
                            </div>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex gap-3 pt-2">
                            <Button size="sm" variant="outline">
                              <Icons.ExternalLink className="mr-2 h-3.5 w-3.5" />
                              Share
                            </Button>
                            <Button size="sm" variant="outline">
                              <Icons.MessageSquare className="mr-2 h-3.5 w-3.5" />
                              Reply
                            </Button>
                            <Button size="sm" variant="outline">
                              <Icons.Trash2 className="mr-2 h-3.5 w-3.5" />
                              Delete
                            </Button>
                          </div>
                        </div>
                      )}

                      {/* Quick Actions */}
                      {!isExpanded && (
                        <div className="pt-2 flex justify-end">
                          {onViewLead && message.dealId && message.recipientName && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => onViewLead(message.dealId!, message.recipientName!)}
                            >
                              <Icons.ExternalLink className="mr-2 h-3.5 w-3.5" />
                              View Lead
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => toggleExpand(message.id)}
                          >
                            {isExpanded ? 'Show Less' : 'Show More'}
                          </Button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}