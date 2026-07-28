'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { MoreHorizontal, RefreshCw, Search } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { adminApi, AdminUserListItem } from '@/lib/api/admin'

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

const SUB_COLORS: Record<string, string> = {
  active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  trialing: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  canceled: 'bg-red-500/10 text-red-400 border-red-500/30',
  none: 'bg-zinc-500/10 text-zinc-400 border-zinc-600',
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return 'Just now'
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'Yesterday'
  if (days < 30) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

const PAGE_SIZE_OPTIONS = [20, 50, 100]

export default function AdminUsersPage() {
  const router = useRouter()
  const [users, setUsers] = useState<AdminUserListItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  // Filters
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [planFilter, setPlanFilter] = useState('all')
  const [subStatusFilter, setSubStatusFilter] = useState('all')
  const [pageSize, setPageSize] = useState(20)
  const [skip, setSkip] = useState(0)

  // Inline action state
  const [deleteTarget, setDeleteTarget] = useState<AdminUserListItem | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedSearch, setDebouncedSearch] = useState('')

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(search)
      setSkip(0)
    }, 300)
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current)
    }
  }, [search])

  const fetchUsers = useCallback(async () => {
    try {
      const res = await adminApi.getUsers({
        search: debouncedSearch || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        plan: planFilter !== 'all' ? planFilter : undefined,
        subscription_status: subStatusFilter !== 'all' ? subStatusFilter : undefined,
        skip,
        limit: pageSize,
      })
      if (res.error) throw new Error(res.error)
      if (res.data) {
        setUsers(res.data.users)
        setTotal(res.data.total)
      }
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load users')
    }
  }, [debouncedSearch, statusFilter, planFilter, subStatusFilter, skip, pageSize])

  useEffect(() => {
    fetchUsers().finally(() => setLoading(false))
  }, [fetchUsers])

  const handleRefresh = async () => {
    setRefreshing(true)
    await fetchUsers()
    setRefreshing(false)
  }

  const handleFilterChange = (setter: (v: string) => void) => (v: string | null) => {
    if (v !== null) setter(v)
    setSkip(0)
  }

  const handleBlockToggle = async (user: AdminUserListItem) => {
    setActionLoading(user.id)
    const newStatus = user.status === 'blocked' ? 'active' : 'blocked'
    const res = await adminApi.updateUser(user.id, { status: newStatus })
    if (!res.error) {
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, status: newStatus } : u))
    } else {
      setError(res.error)
    }
    setActionLoading(null)
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setActionLoading(deleteTarget.id)
    const res = await adminApi.deleteUser(deleteTarget.id)
    if (!res.error) {
      setUsers(prev => prev.filter(u => u.id !== deleteTarget.id))
      setTotal(prev => prev - 1)
    } else {
      setError(res.error)
    }
    setDeleteTarget(null)
    setActionLoading(null)
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.floor(skip / pageSize) + 1

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground mt-1">{total} total users</p>
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
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search email or name…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={planFilter} onValueChange={handleFilterChange(setPlanFilter)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Plan" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All plans</SelectItem>
            <SelectItem value="starter">Starter</SelectItem>
            <SelectItem value="pro">Pro</SelectItem>
            <SelectItem value="business">Business</SelectItem>
            <SelectItem value="agency">Agency</SelectItem>
            <SelectItem value="cloud">Cloud</SelectItem>
            <SelectItem value="lifetime">Lifetime</SelectItem>
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={handleFilterChange(setStatusFilter)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="blocked">Blocked</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
        <Select value={subStatusFilter} onValueChange={handleFilterChange(setSubStatusFilter)}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Subscription" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All subs</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="trialing">Trialing</SelectItem>
            <SelectItem value="canceled">Canceled</SelectItem>
            <SelectItem value="none">None</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <CardHeader className="pb-0 pt-4 px-4">
          <CardTitle className="text-sm font-medium text-muted-foreground sr-only">Users table</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : users.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">No users match the current filters.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">User</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Plan</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Status</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Subscription</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">LinkedIn</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Campaigns</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Signed up</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Last login</th>
                    <th className="w-10 px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                      <td className="px-4 py-3">
                        <Link href={`/admin/users/${u.id}`} className="hover:underline font-medium">
                          {u.email}
                        </Link>
                        {u.full_name && (
                          <span className="block text-xs text-muted-foreground">{u.full_name}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={`text-xs capitalize ${PLAN_COLORS[u.plan] ?? ''}`}>
                          {u.plan}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={`text-xs capitalize ${STATUS_COLORS[u.status] ?? ''}`}>
                          {u.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={`text-xs capitalize ${SUB_COLORS[u.subscription_status] ?? ''}`}>
                          {u.subscription_status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{u.linkedin_profiles_count}</td>
                      <td className="px-4 py-3 text-muted-foreground">{u.campaigns_count}</td>
                      <td className="px-4 py-3 text-muted-foreground" title={u.created_at}>
                        {timeAgo(u.created_at)}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {u.last_login ? <span title={u.last_login}>{timeAgo(u.last_login)}</span> : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" disabled={actionLoading === u.id}>
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => router.push(`/admin/users/${u.id}`)}>
                              View
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => handleBlockToggle(u)}>
                              {u.status === 'blocked' ? 'Unblock' : 'Block'}
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() => setDeleteTarget(u)}
                            >
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {!loading && total > 0 && (
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Rows per page:</span>
                <Select value={pageSize.toString()} onValueChange={v => { if (v) { setPageSize(Number(v)); setSkip(0) } }}>
                  <SelectTrigger className="h-7 w-16 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PAGE_SIZE_OPTIONS.map(n => (
                      <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="outline" size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - pageSize))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline" size="sm"
                  disabled={skip + pageSize >= total}
                  onClick={() => setSkip(skip + pageSize)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete confirmation dialog */}
      <AlertDialog open={!!deleteTarget} onOpenChange={open => { if (!open) setDeleteTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete user?</AlertDialogTitle>
            <AlertDialogDescription>
              This will soft-delete <strong>{deleteTarget?.email}</strong> and schedule a data wipe in 30 days.
              The action can be reversed by restoring the user from their detail page.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
              onClick={handleDelete}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
