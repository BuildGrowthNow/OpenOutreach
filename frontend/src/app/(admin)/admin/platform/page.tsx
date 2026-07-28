'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { adminApi, AdminPlatformMetrics, DaemonListItem } from '@/lib/api/admin'

function StatCard({ title, value, sub, accent }: {
  title: string; value: string | number; sub?: string; accent?: 'green' | 'red' | 'blue'
}) {
  const accentClass = accent === 'green'
    ? 'text-emerald-400'
    : accent === 'red'
      ? 'text-red-400'
      : accent === 'blue'
        ? 'text-blue-400'
        : ''
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${accentClass}`}>{value}</div>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  )
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2"><Skeleton className="h-4 w-24" /></CardHeader>
      <CardContent><Skeleton className="h-8 w-16 mb-2" /><Skeleton className="h-3 w-28" /></CardContent>
    </Card>
  )
}

function timeAgo(dateStr: string | null | undefined) {
  if (!dateStr) return '—'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  if (mins < 2) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  return new Date(dateStr).toLocaleDateString()
}

const AUTO_REFRESH_INTERVAL = 30_000

export default function AdminPlatformPage() {
  const [metrics, setMetrics] = useState<AdminPlatformMetrics | null>(null)
  const [daemons, setDaemons] = useState<DaemonListItem[]>([])
  const [daemonsTotal, setDaemonsTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [daemonsLoading, setDaemonsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null)

  // Filters
  const [statusFilter, setStatusFilter] = useState('all')
  const [modeFilter, setModeFilter] = useState('all')

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchMetrics = useCallback(async () => {
    const res = await adminApi.getPlatformMetrics()
    if (res.error) throw new Error(res.error)
    if (res.data) setMetrics(res.data)
  }, [])

  const fetchDaemons = useCallback(async () => {
    setDaemonsLoading(true)
    const res = await adminApi.getDaemons({
      status: statusFilter !== 'all' ? statusFilter : undefined,
      execution_mode: modeFilter !== 'all' ? modeFilter : undefined,
    })
    if (!res.error && res.data) {
      setDaemons(res.data.daemons)
      setDaemonsTotal(res.data.total)
    }
    setDaemonsLoading(false)
  }, [statusFilter, modeFilter])

  const fetchAll = useCallback(async () => {
    setError(null)
    await Promise.all([
      fetchMetrics().catch(e => setError(e instanceof Error ? e.message : 'Failed to load')),
      fetchDaemons(),
    ])
    setLastRefreshed(new Date())
  }, [fetchMetrics, fetchDaemons])

  useEffect(() => {
    fetchAll().finally(() => setLoading(false))
    intervalRef.current = setInterval(() => fetchAll(), AUTO_REFRESH_INTERVAL)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [fetchAll])

  const handleRefresh = async () => {
    setRefreshing(true)
    await fetchAll()
    setRefreshing(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Platform Health</h1>
          <p className="text-muted-foreground mt-1">
            Live status — auto-refreshes every 30 seconds
            {lastRefreshed && (
              <span className="ml-2 text-xs">· last updated {lastRefreshed.toLocaleTimeString()}</span>
            )}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Live status cards */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Live status</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {loading ? Array.from({ length: 7 }).map((_, i) => <StatCardSkeleton key={i} />) : (
            <>
              <StatCard
                title="Online daemons"
                value={metrics?.daemons.online ?? 0}
                sub={`Desktop: ${metrics?.daemons.desktop ?? 0}  Cloud: ${metrics?.daemons.cloud ?? 0}`}
                accent={(metrics?.daemons.online ?? 0) > 0 ? 'green' : undefined}
              />
              <StatCard title="Running tasks" value={metrics?.tasks.running ?? 0} accent="blue" />
              <StatCard title="Pending tasks" value={metrics?.tasks.pending ?? 0} />
              <StatCard
                title="Failed (24h)"
                value={metrics?.tasks.failed_24h ?? 0}
                accent={(metrics?.tasks.failed_24h ?? 0) > 0 ? 'red' : undefined}
              />
              <StatCard title="Completed (24h)" value={metrics?.tasks.completed_24h ?? 0} accent="green" />
              <StatCard title="Connects (24h)" value={metrics?.activity_24h.connects ?? 0} />
              <StatCard title="Follow-ups (24h)" value={metrics?.activity_24h.follow_ups ?? 0} />
            </>
          )}
        </div>
      </div>

      {/* Daemon map */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between pb-3 flex-wrap gap-3">
          <div>
            <CardTitle className="text-base">Daemon map</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">{daemonsTotal} profiles</p>
          </div>
          <div className="flex gap-2">
            <Select value={statusFilter} onValueChange={v => { if (v) setStatusFilter(v) }}>
              <SelectTrigger className="w-28 h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All status</SelectItem>
                <SelectItem value="online">Online</SelectItem>
                <SelectItem value="offline">Offline</SelectItem>
              </SelectContent>
            </Select>
            <Select value={modeFilter} onValueChange={v => { if (v) setModeFilter(v) }}>
              <SelectTrigger className="w-28 h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All modes</SelectItem>
                <SelectItem value="desktop">Desktop</SelectItem>
                <SelectItem value="cloud">Cloud</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {daemonsLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : daemons.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">No daemons match the current filters.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">User</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">LinkedIn account</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Mode</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Status</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">IP</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Platform</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Browser</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Version</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Last heartbeat</th>
                  </tr>
                </thead>
                <tbody>
                  {daemons.map(d => (
                    <tr key={d.profile_id} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                      <td className="px-4 py-3">
                        {d.user_id ? (
                          <Link href={`/admin/users/${d.user_id}`} className="hover:underline text-sm">
                            {d.user_email ?? d.user_id.slice(0, 8) + '…'}
                          </Link>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{d.username ?? '—'}</td>
                      <td className="px-4 py-3">
                        <Badge
                          variant="outline"
                          className={d.execution_mode === 'cloud'
                            ? 'text-xs bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                            : 'text-xs bg-blue-500/10 text-blue-400 border-blue-500/30'}
                        >
                          {d.execution_mode === 'cloud' ? 'Cloud' : 'Desktop'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant="outline"
                          className={d.daemon_status === 'online'
                            ? 'text-xs bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                            : 'text-xs bg-zinc-500/10 text-zinc-400 border-zinc-600'}
                        >
                          {d.daemon_status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{d.daemon_ip ?? '—'}</td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">{d.daemon_platform ?? '—'}</td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">{d.daemon_browser ?? '—'}</td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">{d.daemon_version ?? '—'}</td>
                      <td className="px-4 py-3 text-muted-foreground text-xs" title={d.last_heartbeat ?? ''}>
                        {timeAgo(d.last_heartbeat)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
