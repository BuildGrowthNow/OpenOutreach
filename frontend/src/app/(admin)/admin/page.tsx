'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { adminApi, AdminDashboardResponse, AdminPlatformMetrics, AdminUserListItem } from '@/lib/api/admin'

function StatCard({ title, value, sub }: { title: string; value: string | number; sub?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  )
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <Skeleton className="h-4 w-24" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-8 w-16 mb-2" />
        <Skeleton className="h-3 w-28" />
      </CardContent>
    </Card>
  )
}

function formatCurrency(cents: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(cents)
}

function formatPercent(rate: number) {
  return `${(rate * 100).toFixed(1)}%`
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return `${days}d ago`
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  blocked: 'bg-red-500/10 text-red-400 border-red-500/30',
  inactive: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
}

const PLAN_COLORS: Record<string, string> = {
  starter: 'bg-zinc-500/10 text-zinc-300 border-zinc-600',
  pro: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  business: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  agency: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  cloud: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
  lifetime: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
}

export default function AdminDashboardPage() {
  const [dashboard, setDashboard] = useState<AdminDashboardResponse | null>(null)
  const [platform, setPlatform] = useState<AdminPlatformMetrics | null>(null)
  const [recentUsers, setRecentUsers] = useState<AdminUserListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const [dashRes, platformRes, usersRes] = await Promise.all([
        adminApi.getDashboard(),
        adminApi.getPlatformMetrics(),
        adminApi.getUsers({ limit: 10, skip: 0 }),
      ])

      if (dashRes.error) throw new Error(dashRes.error)
      if (platformRes.error) throw new Error(platformRes.error)

      if (dashRes.data) setDashboard(dashRes.data)
      if (platformRes.data) setPlatform(platformRes.data)
      if (usersRes.data) setRecentUsers(usersRes.data.users)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load dashboard')
    }
  }, [])

  useEffect(() => {
    fetchAll().finally(() => setLoading(false))
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
          <h1 className="text-3xl font-bold tracking-tight">Admin Dashboard</h1>
          <p className="text-muted-foreground mt-1">Platform overview and key metrics</p>
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

      {/* Row 1 - user metrics */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Users</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => <StatCardSkeleton key={i} />)
          ) : (
            <>
              <StatCard title="Total Users" value={dashboard?.summary.total_users ?? 0} />
              <StatCard title="Active Users" value={dashboard?.summary.active_users ?? 0} />
              <StatCard title="Blocked Users" value={dashboard?.summary.blocked_users ?? 0} />
              <StatCard title="New Today" value={dashboard?.summary.new_signups_today ?? 0} />
              <StatCard title="Active Subs" value={dashboard?.summary.active_subscriptions ?? 0} />
              <StatCard title="Expired Trials" value={dashboard?.summary.expired_trials_count ?? 0} />
            </>
          )}
        </div>
      </div>

      {/* Row 2 - finance KPIs */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Finance</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {loading ? (
            Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
          ) : (
            <>
              <StatCard title="MRR" value={formatCurrency(dashboard?.finance.mrr ?? 0)} sub="Monthly recurring revenue" />
              <StatCard title="ARR" value={formatCurrency(dashboard?.finance.arr ?? 0)} sub="Annual recurring revenue" />
              <StatCard title="Trial Conversion" value={formatPercent(dashboard?.finance.trial_conversion_rate ?? 0)} sub="Trial → paid" />
              <StatCard title="Churn Rate" value={formatPercent(dashboard?.finance.churn_rate ?? 0)} sub="Monthly churn" />
            </>
          )}
        </div>
      </div>

      {/* Row 3 - platform */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Platform</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => <StatCardSkeleton key={i} />)
          ) : (
            <>
              <StatCard
                title="Online Daemons"
                value={platform?.daemons.online ?? 0}
                sub={`Desktop: ${platform?.daemons.desktop ?? 0}  Cloud: ${platform?.daemons.cloud ?? 0}`}
              />
              <StatCard title="Running Tasks" value={platform?.tasks.running ?? 0} />
              <StatCard title="Pending Tasks" value={platform?.tasks.pending ?? 0} />
              <StatCard title="Connects (24h)" value={platform?.activity_24h.connects ?? 0} />
              <StatCard title="Follow-ups (24h)" value={platform?.activity_24h.follow_ups ?? 0} />
            </>
          )}
        </div>
      </div>

      {/* Recent users table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-base">Recent Users</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/admin/users">View all</Link>
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : recentUsers.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">No users yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left px-4 py-2 text-muted-foreground font-medium">Email</th>
                    <th className="text-left px-4 py-2 text-muted-foreground font-medium">Plan</th>
                    <th className="text-left px-4 py-2 text-muted-foreground font-medium">Status</th>
                    <th className="text-left px-4 py-2 text-muted-foreground font-medium">Signed up</th>
                    <th className="text-left px-4 py-2 text-muted-foreground font-medium">Last login</th>
                  </tr>
                </thead>
                <tbody>
                  {recentUsers.map((u) => (
                    <tr key={u.id} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                      <td className="px-4 py-2">
                        <Link href={`/admin/users/${u.id}`} className="hover:underline font-medium">
                          {u.email}
                        </Link>
                        {u.full_name && (
                          <span className="block text-xs text-muted-foreground">{u.full_name}</span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <Badge
                          variant="outline"
                          className={`text-xs capitalize ${PLAN_COLORS[u.plan] ?? ''}`}
                        >
                          {u.plan}
                        </Badge>
                      </td>
                      <td className="px-4 py-2">
                        <Badge
                          variant="outline"
                          className={`text-xs capitalize ${STATUS_COLORS[u.status] ?? ''}`}
                        >
                          {u.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {timeAgo(u.created_at)}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {u.last_login ? timeAgo(u.last_login) : '—'}
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
