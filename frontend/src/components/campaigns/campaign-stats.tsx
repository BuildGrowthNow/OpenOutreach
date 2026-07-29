'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  onClearErrors?: () => void
  className?: string
}

export function CampaignStats({ stats, onClearErrors, className }: CampaignStatsProps) {
  const formatConnectionStats = () => {
    if (!stats.connections_sent || stats.connections_sent === 0) {
      return "No connections sent";
    }
    return `${stats.connections_accepted ?? 0}/${stats.connections_sent} accepted`;
  };

  const formatResponseStats = () => {
    if (!stats.messages_sent || stats.messages_sent === 0) {
      return "No messages sent";
    }
    return `${stats.messages_replied ?? 0}/${stats.messages_sent} replied`;
  };

  const formatConversionStats = () => {
    const count = stats.conversions ?? 0;
    if (count === 0) {
      return "No conversions yet";
    }
    return `${count} conversion${count !== 1 ? 's' : ''}`;
  };

  const formatErrorStats = () => {
    const errors = stats.errors ?? 0;
    if (errors === 0) {
      return "No errors";
    }
    return `${errors} task${errors !== 1 ? 's' : ''} failed`;
  };

  return (
    <div className={cn('space-y-6', className)}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Connection Rate"
          value={`${(stats.connection_accept_rate ?? 0).toFixed(1)}%`}
          subtitle={formatConnectionStats()}
          icon={<Icons.CheckCircle className="h-4 w-4 text-emerald-500" />}
          color="emerald"
        />
        <StatCard
          title="Response Rate"
          value={`${(stats.response_rate ?? 0).toFixed(1)}%`}
          subtitle={formatResponseStats()}
          icon={<Icons.MessageSquare className="h-4 w-4 text-blue-500" />}
          color="blue"
        />
        <StatCard
          title="Conversion Rate"
          value={`${(stats.conversion_rate ?? 0).toFixed(1)}%`}
          subtitle={formatConversionStats()}
          icon={<Icons.TrendingUp className="h-4 w-4 text-purple-500" />}
          color="purple"
        />
        <StatCard
          title="Errors"
          value={`${stats.errors ?? 0}`}
          subtitle={formatErrorStats()}
          icon={<Icons.AlertTriangle className="h-4 w-4 text-amber-500" />}
          color="amber"
          onAction={(stats.errors ?? 0) > 0 ? onClearErrors : undefined}
          actionLabel="clear"
        />
      </div>

      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Connection Success</span>
            <span className="text-sm font-medium">{(stats.connection_accept_rate ?? 0).toFixed(1)}%</span>
          </div>
          <Progress value={stats.connection_accept_rate ?? 0} className="h-2" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Response Rate</span>
            <span className="text-sm font-medium">{(stats.response_rate ?? 0).toFixed(1)}%</span>
          </div>
          <Progress value={stats.response_rate ?? 0} className="h-2" />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Conversion Rate</span>
            <span className="text-sm font-medium">{(stats.conversion_rate ?? 0).toFixed(1)}%</span>
          </div>
          <Progress value={stats.conversion_rate ?? 0} className="h-2" />
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
  onAction?: () => void
  actionLabel?: string
  className?: string
}

function StatCard({ title, value, subtitle, icon, color = 'emerald', onAction, actionLabel = 'clear', className }: StatCardProps) {
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
        {onAction && (
          <div className="flex justify-end mt-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={onAction}
              className="h-5 px-1.5 text-[10px] opacity-40 hover:opacity-70 text-muted-foreground"
            >
              {actionLabel}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}