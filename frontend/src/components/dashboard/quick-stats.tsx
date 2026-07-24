'use client'

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface QuickStatItem {
  label: string
  value: string | number
  sub?: string
  highlight?: 'green' | 'amber' | 'red' | 'neutral'
}

interface QuickStatsProps {
  items: QuickStatItem[]
  className?: string
}

const highlightClass: Record<string, string> = {
  green: 'text-emerald-600 dark:text-emerald-400',
  amber: 'text-amber-600 dark:text-amber-400',
  red: 'text-red-600 dark:text-red-400',
  neutral: 'text-foreground',
}

const QuickStats = ({ items, className }: QuickStatsProps) => {
  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader>
        <CardTitle className="text-base">Quick Stats</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col justify-between gap-0">
        {items.map((item, i) => (
          <div
            key={i}
            className="flex items-center justify-between py-3 border-b last:border-b-0"
          >
            <div className="text-sm text-muted-foreground">{item.label}</div>
            <div className="text-right">
              <span
                className={cn(
                  'text-sm font-semibold',
                  highlightClass[item.highlight ?? 'neutral']
                )}
              >
                {item.value}
              </span>
              {item.sub && (
                <div className="text-xs text-muted-foreground">{item.sub}</div>
              )}
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <div className="text-center py-8 text-sm text-muted-foreground">No data yet</div>
        )}
      </CardContent>
    </Card>
  )
}

export { QuickStats }
export type { QuickStatItem }
