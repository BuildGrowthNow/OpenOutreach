'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { Message } from '@/lib/types/components'
import { formatDistanceToNow } from 'date-fns'
import { MessageCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

type ChannelFilter = 'all' | 'linkedin' | 'whatsapp'

function LinkedinIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-label="LinkedIn" role="img">
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6zM2 9h4v12H2zm2-4a2 2 0 1 0 0 4 2 2 0 0 0 0-4z" />
    </svg>
  )
}

const INTENT_STYLES: Record<string, { label: string; cls: string }> = {
  intent:         { label: 'High intent',    cls: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
  interested:     { label: 'Interested',     cls: 'bg-teal-500/20   text-teal-400   border-teal-500/30'    },
  evaluating:     { label: 'Evaluating',     cls: 'bg-cyan-500/20   text-cyan-400   border-cyan-500/30'    },
  curious:        { label: 'Curious',        cls: 'bg-sky-500/20    text-sky-400    border-sky-500/30'     },
  objecting:      { label: 'Objection',      cls: 'bg-amber-500/20  text-amber-400  border-amber-500/30'   },
  not_interested: { label: 'Not interested', cls: 'bg-red-500/20    text-red-400    border-red-500/30'     },
  busy:           { label: 'Busy',           cls: 'bg-blue-500/20   text-blue-400   border-blue-500/30'    },
  wrong_person:   { label: 'Wrong person',   cls: 'bg-zinc-500/20   text-zinc-400   border-zinc-500/30'    },
  referral:       { label: 'Referral',       cls: 'bg-purple-500/20 text-purple-400 border-purple-500/30'  },
  confused:       { label: 'Confused',       cls: 'bg-orange-500/20 text-orange-400 border-orange-500/30'  },
  unknown:        { label: 'Unknown',        cls: 'bg-slate-500/20  text-slate-400  border-slate-500/30'   },
}

function IntentBadge({ intent }: { intent: string }) {
  const s = INTENT_STYLES[intent]
  if (!s) return null
  return (
    <span className={`mt-1 inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium ${s.cls}`}>
      {s.label}
    </span>
  )
}

function WaTicks({ status }: { status: string }) {
  if (status === 'read') {
    return (
      <span className="text-sky-300" title="Read">
        <svg viewBox="0 0 16 11" className="inline h-3 w-4 fill-current" aria-hidden="true">
          <path d="M11.071.653a.75.75 0 0 0-1.06 1.06l-5.657 5.657L2.69 5.706a.75.75 0 1 0-1.06 1.06l2.474 2.475a.75.75 0 0 0 1.06 0l6.188-6.188a.75.75 0 0 0 0-1.06l-.281-.34zM14.3.653a.75.75 0 0 0-1.06 1.06L7.053 7.9a.75.75 0 0 0 1.06 1.06L14.3 1.714a.75.75 0 0 0 0-1.06z" />
        </svg>
      </span>
    )
  }
  if (status === 'delivered') {
    return (
      <span className="text-blue-200" title="Delivered">
        <svg viewBox="0 0 16 11" className="inline h-3 w-4 fill-current" aria-hidden="true">
          <path d="M11.071.653a.75.75 0 0 0-1.06 1.06l-5.657 5.657L2.69 5.706a.75.75 0 1 0-1.06 1.06l2.474 2.475a.75.75 0 0 0 1.06 0l6.188-6.188a.75.75 0 0 0 0-1.06l-.281-.34zM14.3.653a.75.75 0 0 0-1.06 1.06L7.053 7.9a.75.75 0 0 0 1.06 1.06L14.3 1.714a.75.75 0 0 0 0-1.06z" />
        </svg>
      </span>
    )
  }
  // sent - single tick
  return (
    <span className="text-blue-200" title="Sent">
      <svg viewBox="0 0 8 11" className="inline h-3 w-2 fill-current" aria-hidden="true">
        <path d="M7.071.653a.75.75 0 0 0-1.06 1.06L1.354 6.37a.75.75 0 1 0 1.06 1.06L7.072 1.714a.75.75 0 0 0 0-1.06z" />
      </svg>
    </span>
  )
}

function ChannelIcon({ channel }: { channel?: string }) {
  if (channel === 'whatsapp') {
    return <MessageCircle className="h-3 w-3 text-emerald-400 shrink-0" aria-label="WhatsApp" />
  }
  return <LinkedinIcon className="h-3 w-3 text-blue-400 shrink-0" />
}

interface MessageThreadProps {
  messages?: Message[]
  onSendMessage?: (content: string) => Promise<void>
  isLoading?: boolean
  isSending?: boolean
  leadName?: string
}

export function MessageThread({
  messages = [],
  onSendMessage,
  isLoading = false,
  isSending = false,
  leadName = 'Lead'
}: MessageThreadProps) {
  const [newMessage, setNewMessage] = useState('')
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>('all')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const hasWA = messages.some(m => m.channel === 'whatsapp')
  const hasLI = messages.some(m => !m.channel || m.channel === 'linkedin')
  const showChannelTabs = hasWA && hasLI

  const filteredMessages = channelFilter === 'all'
    ? messages
    : messages.filter(m => channelFilter === 'whatsapp' ? m.channel === 'whatsapp' : (!m.channel || m.channel === 'linkedin'))

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !onSendMessage) return
    
    try {
      await onSendMessage(newMessage.trim())
      setNewMessage('')
    } catch (error) {
      console.error('Failed to send message:', error)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  if (isLoading) {
    return (
      <Card className="h-full flex flex-col">
        <CardHeader>
          <CardTitle>Message Thread</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <div className="text-muted-foreground">Loading messages...</div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="border-b">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle>Conversation with {leadName}</CardTitle>
          <div className="flex items-center gap-2">
            {showChannelTabs && (
              <div className="flex gap-1">
                {(['all', 'linkedin', 'whatsapp'] as ChannelFilter[]).map((ch) => (
                  <button
                    key={ch}
                    onClick={() => setChannelFilter(ch)}
                    className={cn(
                      'flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors',
                      channelFilter === ch
                        ? 'bg-foreground text-background border-foreground'
                        : 'bg-transparent text-muted-foreground border-border hover:border-foreground/40'
                    )}
                  >
                    {ch === 'linkedin' && <LinkedinIcon className="h-3 w-3" />}
                    {ch === 'whatsapp' && <MessageCircle className="h-3 w-3" />}
                    {ch === 'all' ? 'All' : ch === 'linkedin' ? 'LinkedIn' : 'WhatsApp'}
                  </button>
                ))}
              </div>
            )}
            <Badge variant="outline" className="px-2 py-1 text-xs">
              {filteredMessages.length} {filteredMessages.length === 1 ? 'message' : 'messages'}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col p-4">
        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 p-2">
          {filteredMessages.length === 0 ? (
            <div className="text-center py-8">
              <Icons.MessageSquare className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <div className="text-muted-foreground">No messages yet</div>
              <div className="text-sm text-muted-foreground mt-1">
                Start a conversation with {leadName}
              </div>
            </div>
          ) : (
            filteredMessages.map((message, index) => {
              const isOutgoing = message.isOutgoing === true
              const isFirstInGroup = index === 0 || filteredMessages[index - 1].isOutgoing !== message.isOutgoing
              const isLastInGroup = index === filteredMessages.length - 1 || filteredMessages[index + 1].isOutgoing !== message.isOutgoing

              return (
                <div
                  key={message.id || index}
                  className={`flex ${isOutgoing ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-3 ${
                      isOutgoing
                        ? 'bg-blue-600 text-white rounded-br-none'
                        : 'bg-muted text-foreground rounded-bl-none'
                    } ${
                      isFirstInGroup ? 'mt-4' : 'mt-1'
                    } ${isLastInGroup ? 'mb-2' : 'mb-1'}`}
                  >
                    {/* Sender info + channel icon if first in group */}
                    {isFirstInGroup && (
                      <div className={`flex items-center gap-1 text-xs ${isOutgoing ? 'text-blue-200' : 'text-muted-foreground'} mb-1`}>
                        <ChannelIcon channel={message.channel} />
                        <span>{message.sender || (isOutgoing ? 'You' : leadName)}</span>
                      </div>
                    )}

                    {/* Message content */}
                    <div className="text-sm whitespace-pre-wrap">{message.content}</div>

                    {/* Reply intent badge (inbound only) */}
                    {!isOutgoing && message.replyIntent && (
                      <IntentBadge intent={message.replyIntent} />
                    )}

                    {/* Message timestamp + WA delivery ticks */}
                    <div className={`text-xs mt-2 flex items-center justify-end gap-1 ${isOutgoing ? 'text-blue-200' : 'text-muted-foreground'}`}>
                      <span>
                        {message.creationDate
                          ? formatDistanceToNow(new Date(message.creationDate), { addSuffix: true })
                          : 'Recently'
                        }
                      </span>
                      {isOutgoing && message.channel === 'whatsapp' && message.waDeliveryStatus && (
                        <WaTicks status={message.waDeliveryStatus} />
                      )}
                    </div>
                  </div>
                </div>
              )
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t pt-4">
          <div className="flex gap-3">
            <div className="flex-1">
              <Textarea
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Type your message to ${leadName}...`}
                className="min-h-[60px] resize-none"
                disabled={isSending}
              />
               <div className="text-xs text-muted-foreground mt-2 flex justify-between">
                 <span>Press Enter to send, Shift+Enter for new line</span>
                 <span className={newMessage.length >= 900 ? 'text-destructive' : newMessage.length >= 800 ? 'text-amber-600 dark:text-amber-400' : 'text-muted-foreground'}>
                   {newMessage.length}/1000
                 </span>
               </div>
            </div>
            <div>
              <Button
                onClick={handleSendMessage}
                disabled={!newMessage.trim() || isSending}
                className="h-full px-6"
              >
                {isSending ? (
                  <Icons.RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <Icons.MessageSquare className="mr-2 h-4 w-4" />
                    Send
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}