'use client'

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { formatDistanceToNow } from 'date-fns'
import { cn } from '@/lib/utils'

interface ActivityItem {
  id: string
  type: string
  description: string
  timestamp: string
  entity?: string
  status?: 'success' | 'pending' | 'failed'
  icon?: keyof typeof Icons
}

interface RecentActivityProps {
  items: ActivityItem[]
  className?: string
}

const activityIcons: Record<string, keyof typeof Icons> = {
  connection_accepted: 'Users',
  message_sent: 'MessageSquare',
  connection_sent: 'Plus',
  deal_completed: 'CheckCircle2',
  deal_failed: 'AlertCircle',
  email_sent: 'Mail',
  new_lead: 'UserPlus',
}

const statusColors: Record<string, string> = {
  success: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  pending: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  failed: 'bg-red-500/10 text-red-600 dark:text-red-400',
}

const RecentActivity = ({ items, className }: RecentActivityProps) => {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {items.map((item) => {
            const iconKey = activityIcons[item.type] || 'Clock'
            const IconComponent = Icons[iconKey]
            return (
              <div key={item.id} className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                  <IconComponent className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1 space-y-1">
                  <p className="text-sm font-medium leading-none">{item.description}</p>
                  {item.entity && (
                    <p className="text-xs text-muted-foreground">{item.entity}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(item.timestamp), { addSuffix: true })}
                    </span>
                    {item.status && (
                      <Badge
                        variant="outline"
                        className={cn(
                          'text-[0.65rem] px-1.5',
                          statusColors[item.status] || ''
                        )}
                      >
                        {item.status}
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {items.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            <Icons.Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No recent activity</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export { RecentActivity, activityIcons, statusColors }