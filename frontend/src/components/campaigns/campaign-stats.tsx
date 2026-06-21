'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'

interface CampaignStatsProps {
  stats: {
    connections_sent: number
    connections_accepted: number
    connection_accept_rate: number
    messages_sent: number
    messages_replied: number
    response_rate: number
    conversions: number
    conversion_rate: number
    errors: number
    rate_limit_warnings: number
  }
  className?: string
}

export function CampaignStats({ stats, className }: CampaignStatsProps) {
  return (
    <div className={cn('space-y-6', className)}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Connection Rate"
          value={`${stats.connection_accept_rate.toFixed(1)}%`}
          subtitle={`${stats.connections_accepted}/${stats.connections_sent} accepted`}
          icon={<Icons.CheckCircle className="h-4 w-4 text-emerald-500" />}
          color="emerald"
        />
        <StatCard
          title="Response Rate"
          value={`${stats.response_rate.toFixed(1)}%`}
          subtitle={`${stats.messages_replied}/${stats.messages_sent} replied`}
          icon={<Icons.MessageSquare className="h-4 w-4 text-blue-500" />}
          color="blue"
        />
        <StatCard
          title="Conversion Rate"
          value={`${stats.conversion_rate.toFixed(1)}%`}
          subtitle={`${stats.conversions} conversions`}
          icon={<Icons.TrendingUp className="h-4 w-4 text-purple-500" />}
          color="purple"
        />
        <StatCard
          title="Error Rate"
          value={`${stats.errors}`}
          subtitle={`${stats.rate_limit_warnings} warnings`}
          icon={<Icons.AlertTriangle className="h-4 w-4 text-amber-500" />}
          color="amber"
        />
      </div>

      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Connection Success</span>
            <span className="text-sm font-medium">{stats.connection_accept_rate.toFixed(1)}%</span>
          </div>
          <Progress value={stats.connection_accept_rate} className="h-2" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Response Rate</span>
            <span className="text-sm font-medium">{stats.response_rate.toFixed(1)}%</span>
          </div>
          <Progress value={stats.response_rate} className="h-2" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Conversion Rate</span>
            <span className="text-sm font-medium">{stats.conversion_rate.toFixed(1)}%</span>
          </div>
          <Progress value={stats.conversion_rate} className="h-2" />
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: string
  subtitle: string
  icon: React.ReactNode
  color?: 'emerald' | 'blue' | 'purple' | 'amber' | 'red'
  className?: string
}

function StatCard({ title, value, subtitle, icon, color = 'emerald', className }: StatCardProps) {
  const colorClasses = {
    emerald: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
    purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
    amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    red: 'bg-red-500/10 text-red-600 dark:text-red-400',
  }

  return (
    <Card className={className}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          </div>
          <div className={cn('p-2 rounded-full', colorClasses[color])}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}