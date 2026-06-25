'use client'

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'

interface DailyProgressProps {
  dailyConnectionsSent: number
  dailyLimit: number
  effectiveLimit?: number
  className?: string
}

export function DailyProgress({ dailyConnectionsSent, dailyLimit, effectiveLimit, className }: DailyProgressProps) {
  // Use effective limit if provided, otherwise use dailyLimit
  const actualLimit = effectiveLimit ?? dailyLimit
  const percentage = actualLimit > 0 ? (dailyConnectionsSent / actualLimit) * 100 : 0
  const remaining = actualLimit - dailyConnectionsSent
  const isNearLimit = percentage >= 80
  const isAtLimit = percentage >= 100

  const getProgressColor = () => {
    if (isAtLimit) return 'bg-destructive'
    if (isNearLimit) return 'bg-amber-500'
    return 'bg-emerald-500'
  }

  const progressColor = getProgressColor()

  // Display warning message when approaching limits
  let warningMessage = null
  if (isAtLimit) {
    warningMessage = (
      <div className="rounded-md bg-destructive/10 border border-destructive/20 p-2">
        <div className="flex items-center gap-2 text-destructive text-sm font-medium">
          <Icons.AlertTriangle className="h-4 w-4" />
          Daily limit reached! No more connections can be sent today.
        </div>
      </div>
    )
  } else if (isNearLimit) {
    warningMessage = (
      <div className="rounded-md bg-amber-500/10 border border-amber-500/20 p-2">
        <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-sm font-medium">
          <Icons.AlertCircle className="h-4 w-4" />
          Approaching limit: {Math.max(0, remaining)} connections remaining
          {effectiveLimit && effectiveLimit !== dailyLimit && (
            <span className="text-xs opacity-75">
              (effective limit: {effectiveLimit}, base limit: {dailyLimit})
            </span>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h4 className="font-medium text-sm text-muted-foreground">Daily Progress</h4>
          <p className="text-xs text-muted-foreground">
            {isAtLimit 
              ? 'Daily limit reached' 
              : `${remaining} connections remaining today`}
            {effectiveLimit && effectiveLimit !== dailyLimit && (
              <span className="block text-[10px] text-muted-foreground mt-0.5">
                Effective limit: {effectiveLimit} (context-aware)
              </span>
            )}
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
          <span>{actualLimit} limit{effectiveLimit && effectiveLimit !== dailyLimit ? ' (effective)' : ''}</span>
        </div>
      </div>

      {warningMessage}

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
             {formatDistanceToNow(new Date(), { addSuffix: true })}
           </div>
        </div>
      </div>
    </div>
  )
}
