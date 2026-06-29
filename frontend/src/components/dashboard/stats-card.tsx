'use client'

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { Icons } from '@/lib/types/components'

interface StatsCardProps extends React.ComponentProps<'div'> {
  title: string
  value: string | number
  trend?: string
  trendUp?: boolean
  icon: keyof typeof Icons
  description?: string
}

const StatsCard = ({
  title,
  value,
  trend,
  trendUp,
  icon,
  description,
  className,
  ...props
}: StatsCardProps) => {
  return (
    <Card className={cn('relative overflow-hidden', className)} {...props}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <div className="h-4 w-4 text-muted-foreground">
          {React.createElement(Icons[icon] as React.ElementType)}
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
         {trend && trend !== '+0%' && trend !== '0%' && (
           <p className={`text-xs mt-2 ${trendUp ? 'text-emerald-500' : 'text-red-500'}`}>
             {trendUp ? 'up ' : 'down '}{trend} <span className="text-muted-foreground">vs last period</span>
           </p>
         )}
      </CardContent>
    </Card>
  )
}

export { StatsCard }