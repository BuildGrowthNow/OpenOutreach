'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/lib/types/components'
import { Campaign, DealState } from '@/lib/types/components'

import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'

interface CampaignCardProps {
  campaign: Campaign
  onClick?: () => void
  onEdit?: (campaign: Campaign) => void
  onDelete?: (campaign: Campaign) => void
  className?: string
}

const statusColors = {
  active: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
  paused: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
  draft: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20',
}

const stateColorMapping: Record<DealState, string> = {
  QUALIFIED: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  READY_TO_CONNECT: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400',
  PENDING: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  CONNECTED: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400',
  COMPLETED: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  FAILED: 'bg-red-500/10 text-red-600 dark:text-red-400',
  NO_EMAIL: 'bg-gray-500/10 text-gray-600 dark:text-gray-400',
}

const CampaignCard = ({
  campaign,
  onClick,
  onEdit,
  onDelete,
  className,
}: CampaignCardProps) => {
  const stats = campaign.stats || {
    totalLeads: 0,
    qualified: 0,
    connected: 0,
    completed: 0,
    messagesSent: 0,
    messagesReplied: 0,
  }

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    onEdit?.(campaign)
  }

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    onDelete?.(campaign)
  }

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all hover:shadow-md',
        className,
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base">{campaign.name}</CardTitle>
            <CardDescription className="line-clamp-2">
              {campaign.description || 'No description'}
            </CardDescription>
          </div>
          <Badge variant="outline" className={cn('text-xs', statusColors[campaign.status as keyof typeof statusColors])}>
            {campaign.status.charAt(0).toUpperCase() + campaign.status.slice(1)}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="text-center">
            <div className="text-lg font-bold">{stats.totalLeads}</div>
            <div className="text-xs text-muted-foreground">Leads</div>
          </div>
          <div className="text-center border-l">
            <div className="text-lg font-bold">{stats.connected}</div>
            <div className="text-xs text-muted-foreground">Connected</div>
          </div>
          <div className="text-center border-l">
            <div className="text-lg font-bold">{stats.completed}</div>
            <div className="text-xs text-muted-foreground">Completed</div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <Icons.BarChart3 className="h-3 w-3 text-muted-foreground" />
              <span className="text-muted-foreground">Connection rate:</span>
            </div>
            <span className="font-medium">
              {stats.totalLeads > 0
                ? ((stats.connected / stats.totalLeads) * 100).toFixed(1)
                : '0'}%
            </span>
          </div>

          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <Icons.MessageSquare className="h-3 w-3 text-muted-foreground" />
              <span className="text-muted-foreground">Response rate:</span>
            </div>
            <span className="font-medium">
              {stats.connected > 0
                ? ((stats.messagesReplied / stats.connected) * 100).toFixed(1)
                : '0'}%
            </span>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Icons.Clock className="h-3 w-3" />
            Created {formatDistanceToNow(new Date(campaign.createdAt), { addSuffix: true })}
          </div>

          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={handleEdit}>
              <Icons.Edit className="h-4 w-4" />
            </Button>
            <Button size="sm" variant="ghost" onClick={handleDelete}>
              <Icons.Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export { CampaignCard, statusColors, stateColorMapping }