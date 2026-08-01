'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Icons } from '@/lib/types/components'
import { Campaign, DealState, CampaignStatus } from '@/lib/types/components'

import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'

interface CampaignCardProps {
  campaign: Campaign
  onClick?: () => void
  onEdit?: (campaign: Campaign) => void
  onDelete?: (campaign: Campaign) => void
  onStart?: (campaign: Campaign) => void
  onPause?: (campaign: Campaign) => void
  className?: string
}

const statusColors = {
  active: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
  paused: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
  draft: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20',
}

const stateColorMapping: Record<DealState, string> = {
  DISCOVERED: 'bg-slate-500/10 text-slate-600 dark:text-slate-400',
  QUALIFIED: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  READY_TO_CONNECT: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400',
  PENDING: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  CONNECTED: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400',
  COMPLETED: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  FAILED: 'bg-red-500/10 text-red-600 dark:text-red-400',
  NO_EMAIL: 'bg-gray-500/10 text-gray-600 dark:text-gray-400',
}

function getCreatedDate(campaign: Campaign): string {
  const raw = (campaign as unknown as Record<string, string>).created_at || campaign.createdAt;
  const d = raw ? new Date(raw) : null;
  return d && !isNaN(d.getTime()) ? formatDistanceToNow(d, { addSuffix: true }) : "recently";
}

const CampaignCard = ({
  campaign,
  onClick,
  onEdit,
  onDelete,
  onStart,
  onPause,
  className,
}: CampaignCardProps) => {
  const stats = campaign.stats || {
    totalLeads: 0,
    qualified: 0,
    connected: 0,
    completed: 0,
    messagesSent: 0,
    messagesReplied: 0,
    noEmailCount: 0,
    todayConnectBudget: null,
  }

  const isActive = campaign.status === 'active'
  const isPaused = campaign.status === 'paused'
  const isDraft = campaign.status === 'draft'

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all hover:shadow-md',
        className,
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-tight">{campaign.name}</CardTitle>
          <div className="flex items-center gap-2 shrink-0">
            <Badge variant="outline" className={cn('text-xs', statusColors[campaign.status as keyof typeof statusColors])}>
              {campaign.status.charAt(0).toUpperCase() + campaign.status.slice(1)}
            </Badge>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Icons.MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                {isDraft && (
                  <DropdownMenuItem onClick={() => onStart?.(campaign)}>
                    <Icons.Play className="mr-2 h-4 w-4" />
                    Start
                  </DropdownMenuItem>
                )}
                {isActive && (
                  <DropdownMenuItem onClick={() => onPause?.(campaign)}>
                    <Icons.Pause className="mr-2 h-4 w-4" />
                    Pause
                  </DropdownMenuItem>
                )}
                {isPaused && (
                  <DropdownMenuItem onClick={() => onStart?.(campaign)}>
                    <Icons.Play className="mr-2 h-4 w-4" />
                    Resume
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={() => onEdit?.(campaign)}>
                  <Icons.Edit className="mr-2 h-4 w-4" />
                  Edit Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => onDelete?.(campaign)}
                  className="text-destructive focus:text-destructive"
                >
                  <Icons.Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
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
            <div className="text-xs text-muted-foreground">Done</div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <Icons.BarChart3 className="h-3 w-3 text-muted-foreground" />
              <span className="text-muted-foreground">Connection rate</span>
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
              <span className="text-muted-foreground">Response rate</span>
            </div>
            <span className="font-medium">
              {stats.connected > 0
                ? ((stats.messagesReplied / stats.connected) * 100).toFixed(1)
                : '0'}%
            </span>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t space-y-1">
          {isActive && stats.todayConnectBudget != null && (
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Today&apos;s connect budget</span>
              <span className="font-medium text-foreground">{stats.todayConnectBudget} left</span>
            </div>
          )}
          {(stats.noEmailCount ?? 0) > 0 && (
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Blocked — no email</span>
              <span className="font-medium text-amber-500">{stats.noEmailCount}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Icons.Clock className="h-3 w-3" />
            Created {getCreatedDate(campaign)}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export { CampaignCard, statusColors, stateColorMapping }
