'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/lib/types/components'
import { LeadStatusBadge } from './lead-status-badge'
import { Lead } from '@/lib/types/components'
import { formatDistanceToNow } from 'date-fns'

interface LeadCardProps {
  lead: Lead
  onView?: (lead: Lead) => void
  onEdit?: (lead: Lead) => void
  onDisqualify?: (lead: Lead) => void
  onReScrape?: (lead: Lead) => void
}

export function LeadCard({ lead, onView, onEdit, onDisqualify, onReScrape }: LeadCardProps) {
  const [isHovered, setIsHovered] = useState(false)

  const handleView = () => {
    if (onView) onView(lead)
  }

  const handleEdit = () => {
    if (onEdit) onEdit(lead)
  }

  const handleDisqualify = () => {
    if (onDisqualify) onDisqualify(lead)
  }

  const handleReScrape = () => {
    if (onReScrape) onReScrape(lead)
  }

  return (
    <Card 
      className={`relative overflow-hidden transition-all duration-200 ${isHovered ? 'shadow-lg scale-[1.02]' : ''}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg font-semibold leading-tight">
              {lead.name || 'Unnamed Lead'}
            </CardTitle>
            <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
              {lead.company && (
                <>
                  <Icons.BarChart3 className="h-3 w-3" />
                  <span>{lead.company}</span>
                </>
              )}
              {lead.title && (
                <>
                  <span className="mx-1">•</span>
                  <span>{lead.title}</span>
                </>
              )}
            </div>
          </div>
          <LeadStatusBadge state={lead.state} outcome={lead.outcome} />
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {/* Contact Information */}
        <div className="mb-4 space-y-2">
          {lead.contactInfo?.email && (
            <div className="flex items-center gap-2 text-sm">
              <Icons.Mail className="h-3.5 w-3.5 text-muted-foreground" />
              <a
                href={`mailto:${lead.contactInfo.email}`}
                className="text-blue-600 hover:text-blue-800 hover:underline"
              >
                {lead.contactInfo.email}
              </a>
            </div>
          )}

          {lead.contactInfo?.phoneNumbers && lead.contactInfo.phoneNumbers.length > 0 && (
            <div className="flex items-center gap-2 text-sm">
              <Icons.Phone className="h-3.5 w-3.5 text-muted-foreground" />
              <span>{lead.contactInfo.phoneNumbers[0]}</span>
            </div>
          )}

          {lead.linkedinUrl && (
            <div className="flex items-center gap-2 text-sm">
              <Icons.Globe className="h-3.5 w-3.5 text-muted-foreground" />
              <a
                href={lead.linkedinUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 hover:underline truncate max-w-[200px]"
              >
                LinkedIn Profile
                <Icons.ExternalLink className="ml-1 inline h-3 w-3" />
              </a>
            </div>
          )}
        </div>

        {/* Stats and Metadata */}
        <div className="flex items-center justify-between border-t pt-3 text-sm">
          <div className="space-y-1">
            <div className="text-muted-foreground">
              Added: {formatDistanceToNow(new Date(lead.creationDate), { addSuffix: true })}
            </div>
            <div className="text-muted-foreground">
              Updated: {formatDistanceToNow(new Date(lead.updateDate), { addSuffix: true })}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {lead.messagesCount !== undefined && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <Icons.MessageSquare className="h-3 w-3" />
                <span>{lead.messagesCount} messages</span>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={handleView}
          >
            <Icons.ExternalLink className="mr-2 h-3.5 w-3.5" />
            View Details
          </Button>
          
          <Button
            size="sm"
            variant="outline"
            onClick={handleReScrape}
            title="Re-scrape LinkedIn profile"
          >
            <Icons.RefreshCw className="h-3.5 w-3.5" />
          </Button>
          
          <Button
            size="sm"
            variant="outline"
            onClick={handleEdit}
            title="Edit lead"
          >
            <Icons.Edit className="h-3.5 w-3.5" />
          </Button>
          
          <Button
            size="sm"
            variant="destructive"
            onClick={handleDisqualify}
            title="Disqualify lead"
          >
            <Icons.Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}