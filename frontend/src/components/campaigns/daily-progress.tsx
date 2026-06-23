'use client'

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'

interface DailyProgressProps {
  dailyConnectionsSent: number
  dailyLimit: number
  className?: string
}

export function DailyProgress({ dailyConnectionsSent, dailyLimit, className }: DailyProgressProps) {
  const percentage = dailyLimit > 0 ? (dailyConnectionsSent / dailyLimit) * 100 : 0
  const remaining = dailyLimit - dailyConnectionsSent
  const isNearLimit = percentage >= 80
  const isAtLimit = percentage >= 100

  const getProgressColor = () => {
    if (isAtLimit) return 'bg-destructive'
    if (isNearLimit) return 'bg-amber-500'
    return 'bg-emerald-500'
  }

  const progressColor = getProgressColor()

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h4 className="font-medium text-sm text-muted-foreground">Daily Progress</h4>
          <p className="text-xs text-muted-foreground">
            {isAtLimit 
              ? 'Daily limit reached' 
              : `${remaining} connections remaining today`}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">
            {percentage.toFixed(0)}%
          </div>
        </div>
      </div>

      <div className="relative">
        <Progress value={percentage} className={cn('h-2', progressColor)} />
        <div className="flex justify-between mt-1 text-xs text-muted-foreground">
          <span>{dailyConnectionsSent} sent</span>
          <span>{dailyLimit} limit</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 pt-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icons.MessageSquare className="h-4 w-4" />
            <span>Messages sent</span>
          </div>
          <div className="text-lg font-bold">0</div>
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icons.RefreshCw className="h-4 w-4" />
            <span>Next reset</span>
          </div>
          <div className="text-lg font-bold">
            {formatDistanceToNow(Date.now(), { addSuffix: true })}
          </div>
        </div>
      </div>
    </div>
  )
}