'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { formatDistanceToNow } from 'date-fns'
import { cn } from '@/lib/utils'

interface HealthStatusProps {
  status: 'healthy' | 'degraded' | 'unhealthy'
  services: {
    database: {
      status: 'connected' | 'disconnected' | 'degraded'
      latency_ms: number
    }
    cache: {
      status: 'connected' | 'disconnected' | 'degraded'
      latency_ms: number
    }
  }
  lastCheck?: string
  className?: string
}

const statusColors: Record<string, string> = {
  healthy: 'bg-emerald-500 text-emerald-600 dark:bg-emerald-500 dark:text-emerald-50',
  degraded: 'bg-amber-500 text-amber-600 dark:bg-amber-500 dark:text-amber-50',
  unhealthy: 'bg-red-500 text-red-600 dark:bg-red-500 dark:text-red-50',
  unknown: 'bg-gray-500 text-gray-600 dark:bg-gray-500 dark:text-gray-50',
}

const serviceStatusColors: Record<string, string> = {
  connected: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  disconnected: 'bg-red-500/10 text-red-600 dark:text-red-400',
  degraded: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  unknown: 'bg-gray-500/10 text-gray-600 dark:text-gray-400',
}

const HealthStatus = ({
  status,
  services,
  lastCheck,
  className,
}: HealthStatusProps) => {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-base font-medium">System Health</CardTitle>
        <Badge
          className={cn(
            'px-2 py-0.5',
            statusColors[status] || statusColors.unknown
          )}
        >
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Icons.Database className="h-4 w-4 text-muted-foreground" />
              <span>Database</span>
            </div>
            <Badge
              variant="outline"
              className={cn(
                'text-xs mt-1',
                serviceStatusColors[services.database.status] || serviceStatusColors.unknown
              )}
            >
              {services.database.status}
            </Badge>
            <div className="text-xs text-muted-foreground mt-1">
              Latency: {services.database.latency_ms}ms
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Icons.Server className="h-4 w-4 text-muted-foreground" />
              <span>Cache</span>
            </div>
            <Badge
              variant="outline"
              className={cn(
                'text-xs mt-1',
                serviceStatusColors[services.cache.status] || serviceStatusColors.unknown
              )}
            >
              {services.cache.status}
            </Badge>
            <div className="text-xs text-muted-foreground mt-1">
              Latency: {services.cache.latency_ms}ms
            </div>
          </div>
        </div>

        {lastCheck && (
          <div className="mt-4 pt-4 border-t text-xs text-muted-foreground flex items-center gap-2">
            <Icons.Clock className="h-3 w-3" />
            Last check: {formatDistanceToNow(new Date(lastCheck), { addSuffix: true })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export { HealthStatus, statusColors, serviceStatusColors }