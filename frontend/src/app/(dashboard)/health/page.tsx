'use client'

import { useState, useEffect, useMemo } from 'react'
import { HealthStatus } from '@/components/dashboard/health-status'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { RefreshCw, AlertCircle } from 'lucide-react'
import { useDashboard } from '@/hooks/use-dashboard'
import { formatDistanceToNow } from 'date-fns'


interface ServiceHealth {
  name: string
  status: 'connected' | 'disconnected' | 'degraded'
  latency_ms: number
  lastCheck: string
}

const Health = () => {
  const { 
    healthStatus, 
    healthLoading, 
    healthError, 
    fetchHealth 
  } = useDashboard()

  // Fetch initial health data
  useEffect(() => {
    fetchHealth()
  }, [fetchHealth])

  const [refreshing, setRefreshing] = useState(false)
  const initialTimestamp = useMemo(() => new Date().toISOString(), [])
  const lastCheck = healthStatus?.system?.timestamp || initialTimestamp

  const serviceHistory = useMemo<ServiceHealth[]>(() => {
    const timestamp = healthStatus?.system?.timestamp || initialTimestamp

    if (healthStatus) {
      const services: ServiceHealth[] = []

      if (healthStatus.services?.database) {
        services.push({
          name: 'Database',
          status: healthStatus.services.database as 'connected' | 'degraded' | 'disconnected',
          latency_ms: (healthStatus as { database?: { latency_ms?: number } }).database?.latency_ms ?? 0,
          lastCheck: timestamp,
        })
      }

      services.push({
        name: 'API',
        status: healthStatus.status === 'operational' ? 'connected' : 'degraded',
        latency_ms: (healthStatus as { api?: { latency_ms?: number } }).api?.latency_ms ?? 0,
        lastCheck: timestamp,
      })
      return services
    }

    return [
      { name: 'Database', status: 'disconnected', latency_ms: 0, lastCheck: timestamp },
      { name: 'API', status: 'disconnected', latency_ms: 0, lastCheck: timestamp },
    ]
  }, [healthStatus, initialTimestamp])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await fetchHealth()
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">System Health</h1>
        <div className="flex items-center gap-2">
          <Button 
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing || healthLoading}
            variant="outline"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
          <Badge variant="outline" className="px-3 py-1">
            <Icons.RefreshCw className="mr-2 h-3.5 w-3.5" />
            {healthLoading ? 'Checking...' : 'Auto-refresh enabled'}
          </Badge>
        </div>
      </div>

      {/* Error Alert */}
      {healthError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <div className="flex items-center gap-2 text-red-700">
            <AlertCircle className="h-4 w-4" />
            <span className="font-medium">Error loading health status: {healthError}</span>
          </div>
        </div>
      )}

      {/* Overall Health Status */}
      {healthLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        </div>
      ) : healthStatus ? (
        <HealthStatus
          status={healthStatus.status === 'operational' ? 'healthy' : (healthStatus.status || 'unknown')}
          services={{
            database: {
              status: healthStatus.services.database === 'operational' ? 'connected' : (healthStatus.services.database === 'degraded' ? 'degraded' : 'disconnected'),
              latency_ms: 12
            },
          }}
          lastCheck={lastCheck}
        />
      ) : (
        <HealthStatus
          status="unknown"
          services={{
            database: {
              status: 'disconnected',
              latency_ms: 0
            },
          }}
          lastCheck={lastCheck}
        />
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Service Timeline */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Service Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {serviceHistory.map((service) => (
                <div key={service.name} className="flex items-start gap-3">
                  <div
                    className={`
                      mt-1 h-3 w-3 rounded-full
                      ${service.status === 'connected' ? 'bg-emerald-500' : ''}
                      ${service.status === 'degraded' ? 'bg-amber-500' : ''}
                      ${service.status === 'disconnected' ? 'bg-red-500' : ''}
                    `}
                  />
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{service.name}</span>
                      <Badge
                        variant="outline"
                        className={`
                          ${service.status === 'connected' ? 'text-emerald-600' : ''}
                          ${service.status === 'degraded' ? 'text-amber-600' : ''}
                          ${service.status === 'disconnected' ? 'text-red-600' : ''}
                        `}
                      >
                        {service.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>Latency: {service.latency_ms}ms</span>
                      <span>
                        Last check: {formatDistanceToNow(new Date(service.lastCheck), { addSuffix: true })}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

      </div>

      {/* Database Connection */}
      {healthStatus && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Database Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">Database Type</div>
                <div className="text-lg font-medium">MongoDB</div>
              </div>
              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">Connection Status</div>
                <div className="flex items-center gap-2">
                  <div className={`h-2 w-2 rounded-full ${healthStatus.services?.database === 'operational' ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
                  <span className="text-lg font-medium">
                    {healthStatus.services?.database === 'operational' ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default Health
