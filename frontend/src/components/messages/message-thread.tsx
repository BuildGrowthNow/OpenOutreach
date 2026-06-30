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
  const messagesEndRef = useRef<HTMLDivElement>(null)

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
        <div className="flex items-center justify-between">
          <CardTitle>Conversation with {leadName}</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="px-2 py-1 text-xs">
              {messages.length} {messages.length === 1 ? 'message' : 'messages'}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col p-4">
        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 p-2">
          {messages.length === 0 ? (
            <div className="text-center py-8">
              <Icons.MessageSquare className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <div className="text-muted-foreground">No messages yet</div>
              <div className="text-sm text-muted-foreground mt-1">
                Start a conversation with {leadName}
              </div>
            </div>
          ) : (
            messages.map((message, index) => {
              const isOutgoing = message.isOutgoing === true
              const isFirstInGroup = index === 0 || messages[index - 1].isOutgoing !== message.isOutgoing
              const isLastInGroup = index === messages.length - 1 || messages[index + 1].isOutgoing !== message.isOutgoing
              
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
                    {/* Sender info if first in group */}
                    {isFirstInGroup && (
                      <div className={`text-xs ${isOutgoing ? 'text-blue-200' : 'text-muted-foreground'} mb-1`}>
                        {message.sender || (isOutgoing ? 'You' : leadName)}
                      </div>
                    )}
                    
                    {/* Message content */}
                    <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                    
                    {/* Message timestamp */}
                    <div className={`text-xs mt-2 ${isOutgoing ? 'text-blue-200' : 'text-muted-foreground'} text-right`}>
                      {message.creationDate 
                        ? formatDistanceToNow(new Date(message.creationDate), { addSuffix: true })
                        : 'Recently'
                      }
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