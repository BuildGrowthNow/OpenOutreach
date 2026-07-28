'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronRight, RefreshCw, Search } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { adminApi, AdminAuditLog } from '@/lib/api/admin'

const ACTIONS = [
  'delete_user', 'restore_user', 'extend_trial', 'cancel_subscription',
  'set_plan', 'force_verify_email', 'send_password_reset', 'impersonate_user',
]

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  if (mins < 2) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'Yesterday'
  if (days < 30) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

const ACTION_BADGE: Record<string, string> = {
  delete_user: 'bg-red-500/10 text-red-400 border-red-500/30',
  restore_user: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  impersonate_user: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  set_plan: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  cancel_subscription: 'bg-red-500/10 text-red-400 border-red-500/30',
  extend_trial: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
  force_verify_email: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  send_password_reset: 'bg-zinc-500/10 text-zinc-300 border-zinc-600',
}

function AuditRow({ log }: { log: AdminAuditLog }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = Object.keys(log.details).length > 0

  return (
    <>
      <tr className="border-b last:border-0 hover:bg-accent/50 transition-colors">
        <td className="px-4 py-3 whitespace-nowrap">
          <span className="text-muted-foreground text-sm" title={log.created_at}>
            {timeAgo(log.created_at)}
          </span>
          <span className="block text-xs text-muted-foreground/60">
            {new Date(log.created_at).toLocaleString()}
          </span>
        </td>
        <td className="px-4 py-3">
          <Link href={`/admin/users/${log.admin_user_id}`} className="hover:underline font-mono text-xs">
            {log.admin_user_id.slice(0, 12)}…
          </Link>
        </td>
        <td className="px-4 py-3">
          <Badge variant="outline" className={`text-xs ${ACTION_BADGE[log.action] ?? 'bg-zinc-500/10 text-zinc-300 border-zinc-600'}`}>
            {log.action}
          </Badge>
        </td>
        <td className="px-4 py-3">
          {log.target_user_id ? (
            <Link href={`/admin/users/${log.target_user_id}`} className="hover:underline font-mono text-xs">
              {log.target_user_id.slice(0, 12)}…
            </Link>
          ) : '—'}
        </td>
        <td className="px-4 py-3">
          {hasDetails ? (
            <Button
              variant="ghost" size="sm"
              className="h-6 px-2 text-xs gap-1"
              onClick={() => setExpanded(e => !e)}
            >
              {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Details
            </Button>
          ) : '—'}
        </td>
      </tr>
      {expanded && hasDetails && (
        <tr className="border-b bg-muted/30">
          <td colSpan={5} className="px-4 py-2">
            <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  )
}

const PAGE_SIZE = 50

export default function AdminAuditPage() {
  const [logs, setLogs] = useState<AdminAuditLog[]>([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  // Filters
  const [adminId, setAdminId] = useState('')
  const [targetId, setTargetId] = useState('')
  const [actionFilter, setActionFilter] = useState('all')
  const [debouncedAdminId, setDebouncedAdminId] = useState('')
  const [debouncedTargetId, setDebouncedTargetId] = useState('')

  const adminTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const targetTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (adminTimer.current) clearTimeout(adminTimer.current)
    adminTimer.current = setTimeout(() => { setDebouncedAdminId(adminId); setSkip(0) }, 400)
    return () => { if (adminTimer.current) clearTimeout(adminTimer.current) }
  }, [adminId])

  useEffect(() => {
    if (targetTimer.current) clearTimeout(targetTimer.current)
    targetTimer.current = setTimeout(() => { setDebouncedTargetId(targetId); setSkip(0) }, 400)
    return () => { if (targetTimer.current) clearTimeout(targetTimer.current) }
  }, [targetId])

  const fetchLogs = useCallback(async () => {
    const res = await adminApi.getAuditLogs({
      admin_user_id: debouncedAdminId || undefined,
      target_user_id: debouncedTargetId || undefined,
      action: actionFilter !== 'all' ? actionFilter : undefined,
      skip,
      limit: PAGE_SIZE,
    })
    if (res.error) { setError(res.error); return }
    if (res.data) { setLogs(res.data.logs); setTotal(res.data.total) }
    setError(null)
  }, [debouncedAdminId, debouncedTargetId, actionFilter, skip])

  useEffect(() => {
    fetchLogs().finally(() => setLoading(false))
  }, [fetchLogs])

  const handleRefresh = async () => {
    setRefreshing(true)
    await fetchLogs()
    setRefreshing(false)
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const currentPage = Math.floor(skip / PAGE_SIZE) + 1

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Audit Log</h1>
          <p className="text-muted-foreground mt-1">{total} total entries — all admin actions</p>
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

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Admin user ID…"
            value={adminId}
            onChange={e => setAdminId(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="relative min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Target user ID…"
            value={targetId}
            onChange={e => setTargetId(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={actionFilter} onValueChange={v => { if (v) { setActionFilter(v); setSkip(0) } }}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Action" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All actions</SelectItem>
            {ACTIONS.map(a => (
              <SelectItem key={a} value={a}>{a}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : logs.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">No audit entries match the current filters.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Time</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Admin</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Action</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Target</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => <AuditRow key={log.id} log={log} />)}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {!loading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <span className="text-sm text-muted-foreground">
                Showing {skip + 1}–{Math.min(skip + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Page {currentPage} of {totalPages}</span>
                <Button
                  variant="outline" size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline" size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
