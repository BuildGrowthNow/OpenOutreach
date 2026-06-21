'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Icons } from '@/lib/types/components'

interface MessageComposeProps {
  onSendMessage?: (content: string) => Promise<void>
  isSending?: boolean
  placeholder?: string
  disabled?: boolean
}

export function MessageCompose({
  onSendMessage,
  isSending = false,
  placeholder = 'Type your message...',
  disabled = false
}: MessageComposeProps) {
  const [message, setMessage] = useState('')

  const handleSend = async () => {
    if (!message.trim() || !onSendMessage) return
    
    try {
      await onSendMessage(message.trim())
      setMessage('')
    } catch (error) {
      console.error('Failed to send message:', error)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <div className="flex-1">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="min-h-[60px] resize-none"
            disabled={disabled || isSending}
          />
        </div>
        <div>
          <Button
            onClick={handleSend}
            disabled={!message.trim() || isSending || disabled}
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
      <div className="text-xs text-muted-foreground flex justify-between">
        <span>Press Enter to send, Shift+Enter for new line</span>
        <span>{message.length}/1000</span>
      </div>
    </div>
  )
}