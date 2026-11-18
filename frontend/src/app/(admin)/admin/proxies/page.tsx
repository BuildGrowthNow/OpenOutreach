'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Globe2,
  Loader2,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  Wifi,
} from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  adminApi,
  AdminCloudProfile,
  AdminMassiveAlert,
  AdminMassiveStatus,
  AdminMassiveSubaccount,
  AdminPoolStatsResponse,
  AdminProxy,
  AdminProxyAssignment,
  AdminProxyFilters,
  AdminProxyHealthCheck,
  AdminProxyPreviewResponse,
  AdminProxyStats,
  AdminProxyUsageEntry,
  AdminProxyUsageResponse,
} from '@/lib/api/admin'

const STATUS_BADGE: Record<string, string> = {
  available: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  assigned: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  disabled: 'bg-zinc-500/10 text-zinc-300 border-zinc-600',
  error: 'bg-red-500/10 text-red-400 border-red-500/30',
  retired: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
}

const PAGE_SIZE_OPTIONS = [20, 50, 100]

function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatBytes(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const exponent = Math.min(
    Math.max(0, Math.floor(Math.log(bytes) / Math.log(1000))),
    units.length - 1
  )
  return `${(bytes / 1000 ** exponent).toFixed(exponent > 1 ? 2 : 0)} ${units[exponent]}`
}

function regionLabel(proxy: AdminProxy) {
  return [proxy.country, proxy.subdivision, proxy.city].filter(Boolean).join(' · ') || '—'
}

function UsageTable({
  title,
  entries,
  idKey,
}: {
  title: string
  entries: AdminProxyUsageEntry[]
  idKey: 'proxy_id' | 'profile_id' | 'workspace_id'
}) {
  return (
    <div className="rounded-lg border">
      <div className="border-b px-3 py-2 text-sm font-medium">{title}</div>
      <div className="max-h-72 overflow-y-auto">
        {entries.length === 0 ? (
          <p className="p-3 text-xs text-muted-foreground">No usage synced.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Entity</TableHead>
                <TableHead className="text-right">Usage</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry, index) => (
                <TableRow key={`${title}-${entry[idKey] ?? index}`}>
                  <TableCell className="text-xs">
                    {entry.label || entry[idKey] || '—'}
                  </TableCell>
                  <TableCell className="text-right text-xs">{formatBytes(entry.bytes)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}

export default function AdminProxiesPage() {
  const [tab, setTab] = useState('inventory')
  const [proxies, setProxies] = useState<AdminProxy[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<AdminProxyStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [skip, setSkip] = useState(0)
  const [pageSize, setPageSize] = useState(50)
  const [bulkBusy, setBulkBusy] = useState(false)

  const [statusFilter, setStatusFilter] = useState('all')
  const [providerFilter, setProviderFilter] = useState('all')
  const [assignmentFilter, setAssignmentFilter] = useState('all')
  const [countryFilter, setCountryFilter] = useState('')
  const [identityFilter, setIdentityFilter] = useState('')
  const [orgFilter, setOrgFilter] = useState('')
  const [searchFilter, setSearchFilter] = useState('')

  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importCountry, setImportCountry] = useState('')
  const [importProvider, setImportProvider] = useState('manual')
  const [importKind, setImportKind] = useState('residential')
  const [preview, setPreview] = useState<AdminProxyPreviewResponse | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importErrors, setImportErrors] = useState<{ line: number; error: string }[]>([])

  const [assignProxy, setAssignProxy] = useState<AdminProxy | null>(null)
  const [cloudProfiles, setCloudProfiles] = useState<AdminCloudProfile[]>([])
  const [profileSearch, setProfileSearch] = useState('')
  const [selectedProfileId, setSelectedProfileId] = useState('')
  const [assigning, setAssigning] = useState(false)

  const [rotateProxy, setRotateProxy] = useState<AdminProxy | null>(null)
  const [rotatePassword, setRotatePassword] = useState('')

  const [assignments, setAssignments] = useState<AdminProxyAssignment[]>([])
  const [assignmentsTotal, setAssignmentsTotal] = useState(0)
  const [assignmentsActive, setAssignmentsActive] = useState('active')
  const [assignmentsLoading, setAssignmentsLoading] = useState(false)

  const [healthChecks, setHealthChecks] = useState<AdminProxyHealthCheck[]>([])
  const [healthTotal, setHealthTotal] = useState(0)
  const [onlyFailures, setOnlyFailures] = useState(false)
  const [onlyMismatch, setOnlyMismatch] = useState(false)
  const [healthLoading, setHealthLoading] = useState(false)

  const [usage, setUsage] = useState<AdminProxyUsageResponse | null>(null)
  const [usageFrom, setUsageFrom] = useState('')
  const [usageTo, setUsageTo] = useState('')
  const [usageLoading, setUsageLoading] = useState(false)

  const [massiveStatus, setMassiveStatus] = useState<AdminMassiveStatus | null>(null)
  const [massiveLoading, setMassiveLoading] = useState(false)
  const [syncFrom, setSyncFrom] = useState('')
  const [syncTo, setSyncTo] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [fallbackProfileId, setFallbackProfileId] = useState('')
  const [provisioning, setProvisioning] = useState(false)
  const [massiveAccounts, setMassiveAccounts] = useState<AdminMassiveSubaccount[]>([])
  const [massiveParentUsage, setMassiveParentUsage] = useState<{
    accounts: number
    used_bytes: number
    limit_bytes: number
    limit_reached: number
    proxy_access_revoked: number
  } | null>(null)
  const [massiveAlerts, setMassiveAlerts] = useState<AdminMassiveAlert[]>([])
  const [massiveAccountsLoading, setMassiveAccountsLoading] = useState(false)
  const [massiveBusyId, setMassiveBusyId] = useState<string | null>(null)
  const [massiveProvisionProfileId, setMassiveProvisionProfileId] = useState('')
  const [massiveProvisioning, setMassiveProvisioning] = useState(false)
  const [massiveAllocateBytes, setMassiveAllocateBytes] = useState('')
  const [poolStats, setPoolStats] = useState<AdminPoolStatsResponse | null>(null)
  const [poolStatsCountry, setPoolStatsCountry] = useState('')

  const filters: AdminProxyFilters = useMemo(
    () => ({
      status: statusFilter === 'all' ? undefined : statusFilter,
      provider: providerFilter === 'all' ? undefined : providerFilter,
      assignment: assignmentFilter === 'all' ? undefined : assignmentFilter,
      country: countryFilter.trim().toUpperCase() || undefined,
      identity_id: identityFilter.trim() || undefined,
      org_id: orgFilter.trim() || undefined,
      search: searchFilter.trim() || undefined,
    }),
    [
      statusFilter,
      providerFilter,
      assignmentFilter,
      countryFilter,
      identityFilter,
      orgFilter,
      searchFilter,
    ]
  )

  const loadInventory = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const [listResponse, statsResponse] = await Promise.all([
        adminApi.getProxies({ ...filters, skip, limit: pageSize }),
        adminApi.getProxyStats(),
      ])
      if (listResponse.error) throw new Error(listResponse.error)
      if (statsResponse.error) throw new Error(statsResponse.error)
      setProxies(listResponse.data?.proxies ?? [])
      setTotal(listResponse.data?.total ?? 0)
      setStats(statsResponse.data ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load proxies')
    } finally {
      setLoading(false)
    }
  }, [filters, skip, pageSize])

  useEffect(() => {
    void loadInventory()
  }, [loadInventory])

  useEffect(() => {
    setSkip(0)
    setSelected(new Set())
  }, [statusFilter, providerFilter, assignmentFilter, countryFilter, identityFilter, orgFilter, searchFilter])

  const loadAssignments = useCallback(async () => {
    try {
      setAssignmentsLoading(true)
      const response = await adminApi.getProxyAssignments({
        active: assignmentsActive === 'all' ? undefined : assignmentsActive === 'active',
        limit: 200,
      })
      if (response.error) throw new Error(response.error)
      setAssignments(response.data?.assignments ?? [])
      setAssignmentsTotal(response.data?.total ?? 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load assignments')
    } finally {
      setAssignmentsLoading(false)
    }
  }, [assignmentsActive])

  useEffect(() => {
    if (tab === 'assignments') void loadAssignments()
  }, [tab, loadAssignments])

  const loadHealth = useCallback(async () => {
    try {
      setHealthLoading(true)
      const response = await adminApi.getProxyHealth({
        only_failures: onlyFailures || undefined,
        only_mismatch: onlyMismatch || undefined,
        limit: 200,
      })
      if (response.error) throw new Error(response.error)
      setHealthChecks(response.data?.checks ?? [])
      setHealthTotal(response.data?.total ?? 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load health checks')
    } finally {
      setHealthLoading(false)
    }
  }, [onlyFailures, onlyMismatch])

  useEffect(() => {
    if (tab === 'health') void loadHealth()
  }, [tab, loadHealth])

  const loadUsage = useCallback(async (from?: string, to?: string) => {
    try {
      setUsageLoading(true)
      const response = await adminApi.getProxyUsage({
        period_start: from || undefined,
        period_end: to || undefined,
      })
      if (response.error) throw new Error(response.error)
      setUsage(response.data ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load usage')
    } finally {
      setUsageLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tab === 'usage') void loadUsage()
  }, [tab, loadUsage])

  const loadMassive = useCallback(async () => {
    try {
      setMassiveLoading(true)
      const response = await adminApi.getMassiveStatus()
      if (response.error) throw new Error(response.error)
      setMassiveStatus(response.data ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Massive status')
    } finally {
      setMassiveLoading(false)
    }
  }, [])

  const loadMassiveAccounts = useCallback(async () => {
    try {
      setMassiveAccountsLoading(true)
      const [accountsResponse, alertsResponse] = await Promise.all([
        adminApi.getMassiveAccounts(),
        adminApi.getMassiveAlerts(),
      ])
      if (accountsResponse.error) throw new Error(accountsResponse.error)
      setMassiveAccounts(accountsResponse.data?.accounts ?? [])
      setMassiveParentUsage(accountsResponse.data?.parent_usage ?? null)
      setMassiveAlerts(alertsResponse.data?.alerts ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Massive sub-accounts')
    } finally {
      setMassiveAccountsLoading(false)
    }
  }, [])

  const loadPoolStats = useCallback(async (country?: string) => {
    try {
      const response = await adminApi.getPoolStats(country?.trim().toUpperCase() || undefined)
      if (response.error) throw new Error(response.error)
      setPoolStats(response.data ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Pool Stats')
    }
  }, [])

  useEffect(() => {
    if (tab === 'massive') {
      void loadMassive()
      void loadMassiveAccounts()
      void loadPoolStats()
    }
  }, [tab, loadMassive, loadMassiveAccounts, loadPoolStats])

  const selectedIds = useMemo(() => Array.from(selected), [selected])

  const toggleSelected = (proxyId: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(proxyId)) next.delete(proxyId)
      else next.add(proxyId)
      return next
    })
  }

  const toggleAll = () => {
    setSelected((current) => {
      if (current.size === proxies.length) return new Set()
      return new Set(proxies.map((proxy) => proxy.id))
    })
  }

  const handlePreview = async () => {
    if (!importText.trim()) return
    try {
      setPreviewing(true)
      setError(null)
      setMessage(null)
      setImportErrors([])
      const response = await adminApi.parseProxies({
        text: importText,
        provider: importProvider,
        kind: importKind,
        default_country: importCountry.trim().toUpperCase() || undefined,
      })
      if (response.error) throw new Error(response.error)
      setPreview(response.data ?? null)
      setImportErrors(response.data?.errors ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preview failed')
    } finally {
      setPreviewing(false)
    }
  }

  const handleImport = async () => {
    if (!importText.trim()) return
    try {
      setImporting(true)
      setError(null)
      setMessage(null)
      const response = await adminApi.importProxies({
        text: importText,
        provider: importProvider,
        kind: importKind,
        default_country: importCountry.trim().toUpperCase() || undefined,
      })
      if (response.error) throw new Error(response.error)
      const result = response.data
      if (!result) throw new Error('Import returned no result')
      setMessage(
        `Imported ${result.created}, skipped ${result.skipped}, failed ${result.failed}.`
      )
      setImportErrors(result.errors ?? [])
      setImportText('')
      setPreview(null)
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  const loadCloudProfiles = useCallback(async (search: string) => {
    const response = await adminApi.getCloudProfiles({
      search: search.trim() || undefined,
      limit: 50,
    })
    if (response.error) throw new Error(response.error)
    setCloudProfiles(response.data?.profiles ?? [])
  }, [])

  const openAssign = async (proxy: AdminProxy) => {
    setAssignProxy(proxy)
    setSelectedProfileId('')
    setProfileSearch('')
    try {
      await loadCloudProfiles('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cloud profiles')
    }
  }

  const handleAssign = async () => {
    if (!assignProxy || !selectedProfileId) return
    try {
      setAssigning(true)
      setError(null)
      const response = await adminApi.assignProxy(assignProxy.id, selectedProfileId)
      if (response.error) throw new Error(response.error)
      setMessage('Proxy assigned.')
      setAssignProxy(null)
      setSelectedProfileId('')
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assignment failed')
    } finally {
      setAssigning(false)
    }
  }

  const handleUnassign = async (proxy: AdminProxy) => {
    if (!window.confirm('Unassign this proxy? The profile will be paused and the proxy will stay reserved for the same account.')) {
      return
    }
    try {
      setError(null)
      const response = await adminApi.unassignProxy(proxy.id, 'admin_request')
      if (response.error) throw new Error(response.error)
      setMessage('Proxy unassigned; profile paused.')
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unassign failed')
    }
  }

  const handleSingleTest = async (proxy: AdminProxy) => {
    try {
      setError(null)
      const response = await adminApi.testProxy(proxy.id)
      if (response.error) throw new Error(response.error)
      const result = response.data
      setMessage(
        result?.success
          ? `Test passed: ${result.ip ?? 'unknown IP'} · ${result.country ?? 'unknown country'} · ${result.latency_ms ?? 0}ms`
          : `Test failed: ${result?.error ?? result?.message ?? 'unknown error'}`
      )
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Proxy test failed')
    }
  }

  const handleLifecycle = async (
    action: 'enable' | 'disable' | 'retire',
    proxy: AdminProxy
  ) => {
    if (action === 'retire' && !window.confirm('Retire this proxy permanently? It cannot be reused.')) {
      return
    }
    try {
      setError(null)
      const response =
        action === 'enable'
          ? await adminApi.enableProxy(proxy.id)
          : action === 'disable'
            ? await adminApi.disableProxy(proxy.id)
            : await adminApi.retireProxy(proxy.id)
      if (response.error) throw new Error(response.error)
      const pastTense =
        action === 'enable' ? 'enabled' : action === 'disable' ? 'disabled' : 'retired'
      setMessage(`Proxy ${pastTense}.`)
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} proxy`)
    }
  }

  const handleRotate = async () => {
    if (!rotateProxy || rotatePassword.length < 8) return
    try {
      setError(null)
      const response = await adminApi.rotateProxy(rotateProxy.id, rotatePassword)
      if (response.error) throw new Error(response.error)
      setMessage('Proxy password rotated. The new value is never displayed.')
      setRotateProxy(null)
      setRotatePassword('')
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rotation failed')
    }
  }

  const handleBulkTest = async (all: boolean) => {
    try {
      setBulkBusy(true)
      setError(null)
      const response = await adminApi.bulkTestProxies({
        all,
        proxy_ids: all ? undefined : selectedIds,
        ...(all ? filters : {}),
      })
      if (response.error) throw new Error(response.error)
      const result = response.data
      setMessage(
        `Tested ${result?.tested ?? 0}: ${result?.passed ?? 0} passed, ${result?.failed ?? 0} failed.`
      )
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bulk test failed')
    } finally {
      setBulkBusy(false)
    }
  }

  const handleBulkLifecycle = async (
    action: 'unassign' | 'enable' | 'disable' | 'retire'
  ) => {
    if (!selectedIds.length) return
    if (
      (action === 'unassign' || action === 'retire') &&
      !window.confirm(`Apply ${action} to ${selectedIds.length} selected proxies?`)
    ) {
      return
    }
    try {
      setBulkBusy(true)
      setError(null)
      const response = await adminApi.bulkProxyAction({
        action,
        proxy_ids: selectedIds,
      })
      if (response.error) throw new Error(response.error)
      const result = response.data
      setMessage(
        `${action}: ${result?.processed ?? 0} processed, ${result?.failed ?? 0} failed.`
      )
      setSelected(new Set())
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Bulk ${action} failed`)
    } finally {
      setBulkBusy(false)
    }
  }

  const handleExport = async () => {
    try {
      setError(null)
      const response = await adminApi.exportProxies(filters)
      if (response.error) throw new Error(response.error)
      if (typeof response.data !== 'string') throw new Error('Export returned no CSV')
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'proxies-export.csv'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
    }
  }

  const handleSyncMassive = async () => {
    try {
      setSyncing(true)
      setError(null)
      const response = await adminApi.syncMassiveUsage({
        from_date: syncFrom || undefined,
        to_date: syncTo || undefined,
      })
      if (response.error) throw new Error(response.error)
      setMessage(
        `Usage sync matched ${response.data?.matched ?? 0} proxies (${formatBytes(response.data?.total_bytes ?? 0)}).`
      )
      await loadUsage(usageFrom, usageTo)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Usage sync failed')
    } finally {
      setSyncing(false)
    }
  }

  const handleProvisionFallback = async () => {
    if (!fallbackProfileId.trim()) return
    try {
      setProvisioning(true)
      setError(null)
      const response = await adminApi.provisionFallbackProxy(fallbackProfileId.trim())
      if (response.error) throw new Error(response.error)
      setMessage('Massive fallback proxy created and assigned.')
      setFallbackProfileId('')
      await loadInventory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fallback provisioning failed')
    } finally {
      setProvisioning(false)
    }
  }

  const handleSyncReseller = async () => {
    try {
      setSyncing(true)
      setError(null)
      const response = await adminApi.syncMassiveReseller({
        from_date: syncFrom || undefined,
        to_date: syncTo || undefined,
      })
      if (response.error) throw new Error(response.error)
      const data = response.data
      setMessage(
        `Reseller sync: ${data?.accounts ?? 0} accounts, ${data?.matched ?? 0} matched, ` +
          `${data?.unmatched ?? 0} unmatched. Budgets disabled ${data?.budget?.disabled ?? 0}, ` +
          `re-enabled ${data?.budget?.re_enabled ?? 0}.`
      )
      await Promise.all([loadMassive(), loadMassiveAccounts(), loadUsage(usageFrom, usageTo)])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reseller sync failed')
    } finally {
      setSyncing(false)
    }
  }

  const handleProvisionMassive = async () => {
    if (!massiveProvisionProfileId.trim()) return
    try {
      setMassiveProvisioning(true)
      setError(null)
      const response = await adminApi.provisionMassiveSubaccount(
        massiveProvisionProfileId.trim()
      )
      if (response.error) throw new Error(response.error)
      setMessage('Massive sub-account provisioned and assigned.')
      setMassiveProvisionProfileId('')
      await Promise.all([loadInventory(), loadMassiveAccounts()])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Massive provisioning failed')
    } finally {
      setMassiveProvisioning(false)
    }
  }

  const handleMassiveAction = async (
    proxyId: string,
    action: 'disable' | 'enable' | 'rotate' | 'allocate'
  ) => {
    try {
      setMassiveBusyId(proxyId)
      setError(null)
      let response
      if (action === 'disable') response = await adminApi.disableMassiveSubaccount(proxyId)
      else if (action === 'enable') response = await adminApi.enableMassiveSubaccount(proxyId)
      else if (action === 'rotate') response = await adminApi.rotateMassiveSubaccount(proxyId)
      else {
        const raw = window.prompt(
          'Top-up bytes to add to this sub-account (cumulative lifetime allowance):',
          massiveAllocateBytes || '5000000000'
        )
        if (raw === null) return
        const bytes = Number(raw)
        if (!Number.isFinite(bytes) || bytes <= 0) {
          setError('Enter a positive byte allowance to allocate.')
          return
        }
        setMassiveAllocateBytes(String(Math.floor(bytes)))
        response = await adminApi.allocateMassiveTraffic(proxyId, Math.floor(bytes))
      }
      if (response.error) throw new Error(response.error)
      setMessage(`Massive ${action} completed.`)
      setMassiveAllocateBytes('')
      await loadMassiveAccounts()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Massive ${action} failed`)
    } finally {
      setMassiveBusyId(null)
    }
  }

  const pageStart = total === 0 ? 0 : skip + 1
  const pageEnd = Math.min(skip + pageSize, total)
  const allSelected = proxies.length > 0 && selected.size === proxies.length

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Managed proxies</h1>
          <p className="text-sm text-muted-foreground">
            {total} proxies in inventory. Passwords and provider keys are never shown.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void loadInventory()} disabled={loading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => void handleExport()}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button onClick={() => setImportOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Import
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {message && (
        <Alert>
          <CheckCircle2 className="h-4 w-4" />
          <AlertDescription>{message}</AlertDescription>
        </Alert>
      )}

      {stats && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          {([
            { label: 'Total', value: stats.total, tone: 'text-foreground' },
            { label: 'Available', value: stats.status.available ?? 0, tone: 'text-emerald-400' },
            { label: 'Assigned', value: stats.status.assigned ?? 0, tone: 'text-blue-400' },
            {
              label: 'Needs attention',
              value: (stats.status.error ?? 0) + (stats.status.disabled ?? 0),
              tone: 'text-amber-400',
            },
            { label: 'Retired', value: stats.status.retired ?? 0, tone: 'text-zinc-400' },
            {
              label: 'Cloud profiles without proxy',
              value: stats.cloud_profiles_without_proxy ?? 0,
              tone: (stats.cloud_profiles_without_proxy ?? 0) > 0 ? 'text-red-400' : 'text-emerald-400',
            },
          ] as { label: string; value: number; tone: string }[]).map((card) => (
            <Card key={card.label}>
              <CardContent className="pt-5">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{card.label}</p>
                <p className={`mt-1 text-2xl font-semibold ${card.tone}`}>{card.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList variant="line">
          <TabsTrigger value="inventory">Inventory</TabsTrigger>
          <TabsTrigger value="assignments">Assignments</TabsTrigger>
          <TabsTrigger value="health">Health</TabsTrigger>
          <TabsTrigger value="usage">Usage</TabsTrigger>
          <TabsTrigger value="massive">Massive</TabsTrigger>
        </TabsList>

        <TabsContent value="inventory" className="space-y-4">
          <Card>
            <CardContent className="pt-5">
              <div className="grid gap-3 lg:grid-cols-6">
                <Input
                  value={searchFilter}
                  onChange={(event) => setSearchFilter(event.target.value)}
                  placeholder="Search label, host, profile"
                  className="lg:col-span-2"
                />
                <Select value={statusFilter} onValueChange={(value) => value && setStatusFilter(value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All statuses</SelectItem>
                    <SelectItem value="available">Available</SelectItem>
                    <SelectItem value="assigned">Assigned</SelectItem>
                    <SelectItem value="disabled">Disabled</SelectItem>
                    <SelectItem value="error">Error</SelectItem>
                    <SelectItem value="retired">Retired</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={providerFilter} onValueChange={(value) => value && setProviderFilter(value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All providers</SelectItem>
                    <SelectItem value="manual">Manual</SelectItem>
                    <SelectItem value="massive_residential">Massive residential</SelectItem>
                    <SelectItem value="massive_isp">Massive ISP</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={assignmentFilter} onValueChange={(value) => value && setAssignmentFilter(value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Assignment" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Assigned & unassigned</SelectItem>
                    <SelectItem value="assigned">Assigned</SelectItem>
                    <SelectItem value="unassigned">Unassigned</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  value={countryFilter}
                  onChange={(event) => setCountryFilter(event.target.value.toUpperCase())}
                  placeholder="Country (US)"
                  maxLength={2}
                />
                <Input
                  value={identityFilter}
                  onChange={(event) => setIdentityFilter(event.target.value)}
                  placeholder="Identity ID"
                />
                <Input
                  value={orgFilter}
                  onChange={(event) => setOrgFilter(event.target.value)}
                  placeholder="Org ID"
                />
                <Select
                  value={pageSize.toString()}
                  onValueChange={(value) => {
                    if (value) {
                      setPageSize(Number(value))
                      setSkip(0)
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Page size" />
                  </SelectTrigger>
                  <SelectContent>
                    {PAGE_SIZE_OPTIONS.map((size) => (
                      <SelectItem key={size} value={size.toString()}>
                        {size} per page
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {selectedIds.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 p-3">
              <span className="text-sm font-medium">{selectedIds.length} selected</span>
              <Button size="sm" variant="outline" onClick={() => void handleBulkTest(false)} disabled={bulkBusy}>
                {bulkBusy ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Wifi className="mr-1 h-3 w-3" />}
                Test selected
              </Button>
              <Button size="sm" variant="outline" onClick={() => void handleBulkLifecycle('unassign')} disabled={bulkBusy}>
                Unassign
              </Button>
              <Button size="sm" variant="outline" onClick={() => void handleBulkLifecycle('enable')} disabled={bulkBusy}>
                Enable
              </Button>
              <Button size="sm" variant="outline" onClick={() => void handleBulkLifecycle('disable')} disabled={bulkBusy}>
                Disable
              </Button>
              <Button size="sm" variant="outline" onClick={() => void handleBulkLifecycle('retire')} disabled={bulkBusy}>
                <Trash2 className="mr-1 h-3 w-3" />
                Retire
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
                Clear
              </Button>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              Showing {pageStart}–{pageEnd} of {total}
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => void handleBulkTest(true)}
                disabled={bulkBusy || total === 0}
              >
                {bulkBusy ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Wifi className="mr-1 h-3 w-3" />}
                Test all filtered
              </Button>
              <Button size="sm" variant="outline" onClick={() => setSkip(Math.max(0, skip - pageSize))} disabled={skip === 0}>
                Previous
              </Button>
              <Button size="sm" variant="outline" onClick={() => setSkip(skip + pageSize)} disabled={pageEnd >= total}>
                Next
              </Button>
            </div>
          </div>

          {loading ? (
            <Skeleton className="h-64 w-full" />
          ) : proxies.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                No proxies match these filters.
              </CardContent>
            </Card>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox checked={allSelected} onCheckedChange={toggleAll} />
                    </TableHead>
                    <TableHead>Endpoint</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Region</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Assigned</TableHead>
                    <TableHead>Last test</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {proxies.map((proxy) => (
                    <TableRow key={proxy.id}>
                      <TableCell>
                        <Checkbox
                          checked={selected.has(proxy.id)}
                          onCheckedChange={() => toggleSelected(proxy.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="font-mono text-xs">{proxy.host}:{proxy.port}</div>
                        <div className="text-xs text-muted-foreground">
                          {proxy.label} · {proxy.protocol} · {proxy.kind}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">{proxy.provider}</TableCell>
                      <TableCell className="text-sm">{regionLabel(proxy)}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={STATUS_BADGE[proxy.status] ?? ''}>
                          {proxy.status}
                        </Badge>
                        {proxy.country_mismatch && (
                          <Badge variant="outline" className="ml-1 border-amber-500/40 text-amber-400">
                            mismatch
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {proxy.linkedin_profile_id ?? proxy.last_assigned_profile_id ?? '—'}
                        {proxy.identity_id ? (
                          <div className="text-muted-foreground">identity {proxy.identity_id}</div>
                        ) : null}
                        {proxy.assigned_org_id ? (
                          <div className="text-muted-foreground">org {proxy.assigned_org_id}</div>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {proxy.last_test_ip ?? '—'}
                        {proxy.last_test_country ? ` · ${proxy.last_test_country}` : ''}
                        {proxy.last_test_latency_ms ? ` · ${proxy.last_test_latency_ms}ms` : ''}
                        <div>{proxy.last_tested_at ? formatDate(proxy.last_tested_at) : 'Never'}</div>
                        {proxy.last_error ? (
                          <span className="block text-red-400">{proxy.last_error}</span>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="outline" onClick={() => void handleSingleTest(proxy)}>
                            Test
                          </Button>
                          {proxy.linkedin_profile_id ? (
                            <Button size="sm" variant="outline" onClick={() => void handleUnassign(proxy)}>
                              Unassign
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => void openAssign(proxy)}
                              disabled={proxy.status === 'retired'}
                            >
                              Assign
                            </Button>
                          )}
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              render={
                                <Button size="sm" variant="ghost" aria-label="More actions">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              }
                            />
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => void handleLifecycle('enable', proxy)}
                                disabled={Boolean(proxy.linkedin_profile_id) || proxy.status === 'retired' || proxy.status === 'available'}
                              >
                                Enable
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => void handleLifecycle('disable', proxy)}
                                disabled={Boolean(proxy.linkedin_profile_id) || proxy.status === 'retired' || proxy.status === 'disabled'}
                              >
                                Disable
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                onClick={() => setRotateProxy(proxy)}
                                disabled={proxy.provider !== 'manual'}
                              >
                                Rotate password
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                onClick={() => void handleLifecycle('retire', proxy)}
                                disabled={Boolean(proxy.linkedin_profile_id) || proxy.status === 'retired'}
                              >
                                <Trash2 className="mr-2 h-3.5 w-3.5" />
                                Retire
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="assignments" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Select value={assignmentsActive} onValueChange={(value) => value && setAssignmentsActive(value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Assignment state" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="all">Active & historical</SelectItem>
                  <SelectItem value="historical">Historical</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" size="sm" onClick={() => void loadAssignments()} disabled={assignmentsLoading}>
                <RefreshCw className="mr-1 h-3 w-3" />
                Refresh
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">{assignmentsTotal} assignments</p>
          </div>
          {assignmentsLoading ? (
            <Skeleton className="h-52 w-full" />
          ) : assignments.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                No assignments recorded yet.
              </CardContent>
            </Card>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Proxy</TableHead>
                    <TableHead>Profile</TableHead>
                    <TableHead>Channel</TableHead>
                    <TableHead>Identity</TableHead>
                    <TableHead>Workspace</TableHead>
                    <TableHead>Assigned</TableHead>
                    <TableHead>Unassigned</TableHead>
                    <TableHead>Reason</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {assignments.map((assignment) => (
                    <TableRow key={assignment.id}>
                      <TableCell className="font-mono text-xs">{assignment.proxy_id}</TableCell>
                      <TableCell className="font-mono text-xs">{assignment.profile_id ?? '—'}</TableCell>
                      <TableCell className="text-sm">{assignment.channel ?? '—'}</TableCell>
                      <TableCell className="font-mono text-xs">{assignment.identity_id ?? '—'}</TableCell>
                      <TableCell className="font-mono text-xs">{assignment.org_id ?? assignment.user_id ?? '—'}</TableCell>
                      <TableCell className="text-xs">{formatDate(assignment.assigned_at)}</TableCell>
                      <TableCell className="text-xs">{formatDate(assignment.unassigned_at)}</TableCell>
                      <TableCell className="text-xs">{assignment.reason ?? '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="health" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={onlyFailures} onCheckedChange={(value) => setOnlyFailures(Boolean(value))} />
                Failures only
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={onlyMismatch} onCheckedChange={(value) => setOnlyMismatch(Boolean(value))} />
                Country mismatch
              </label>
              <Button variant="outline" size="sm" onClick={() => void loadHealth()} disabled={healthLoading}>
                <RefreshCw className="mr-1 h-3 w-3" />
                Refresh
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">{healthTotal} checks</p>
          </div>
          {healthLoading ? (
            <Skeleton className="h-52 w-full" />
          ) : healthChecks.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                No health checks recorded yet. Run a test or wait for the daily job.
              </CardContent>
            </Card>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Checked</TableHead>
                    <TableHead>Proxy</TableHead>
                    <TableHead>Result</TableHead>
                    <TableHead>Egress</TableHead>
                    <TableHead>Expected</TableHead>
                    <TableHead>Latency</TableHead>
                    <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {healthChecks.map((check) => (
                    <TableRow key={check.id}>
                      <TableCell className="text-xs">{formatDate(check.checked_at)}</TableCell>
                      <TableCell className="font-mono text-xs">{check.proxy_id}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={
                            check.success
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                              : 'bg-red-500/10 text-red-400 border-red-500/30'
                          }
                        >
                          {check.success ? 'passed' : 'failed'}
                        </Badge>
                        {check.country_match === false && (
                          <Badge variant="outline" className="ml-1 border-amber-500/40 text-amber-400">
                            mismatch
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-xs">
                        {check.egress_ip ?? '—'}
                        {check.egress_country ? ` · ${check.egress_country}` : ''}
                      </TableCell>
                      <TableCell className="text-xs">{check.expected_country ?? '—'}</TableCell>
                      <TableCell className="text-xs">
                        {check.latency_ms !== null ? `${check.latency_ms}ms` : '—'}
                      </TableCell>
                      <TableCell className="text-xs text-red-400">
                        {check.error_type ? `${check.error_type}: ` : ''}
                        {check.error ?? '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="usage" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Internal usage</CardTitle>
              <CardDescription>
                Per proxy, per profile, and per workspace. This is an internal cost view, not a
                customer-facing allowance.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-end gap-2">
                <Input
                  value={usageFrom}
                  onChange={(event) => setUsageFrom(event.target.value)}
                  placeholder="From (YYYY-MM-DD)"
                  className="w-44"
                />
                <Input
                  value={usageTo}
                  onChange={(event) => setUsageTo(event.target.value)}
                  placeholder="To (YYYY-MM-DD)"
                  className="w-44"
                />
                <Button variant="outline" onClick={() => void loadUsage(usageFrom, usageTo)} disabled={usageLoading}>
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Refresh
                </Button>
                <div className="ml-auto text-sm">
                  Total: <span className="font-semibold">{formatBytes(usage?.total_bytes ?? 0)}</span>
                </div>
              </div>
              {usageLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : (
                <div className="grid gap-4 lg:grid-cols-2">
                  <UsageTable title="Per proxy" entries={usage?.per_proxy ?? []} idKey="proxy_id" />
                  <UsageTable title="Per profile" entries={usage?.per_profile ?? []} idKey="profile_id" />
                  <UsageTable title="Per workspace" entries={usage?.per_workspace ?? []} idKey="workspace_id" />
                  <UsageTable
                    title="Per channel"
                    entries={(usage?.per_channel ?? []).map((entry) => ({
                      label: entry.channel,
                      bytes: entry.bytes,
                    }))}
                    idKey="workspace_id"
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="massive" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Globe2 className="h-4 w-4" />
                Massive connection
              </CardTitle>
              <CardDescription>
                Reseller sub-accounts, cumulative usage, internal budgets, and the Phase 1
                parent-credential fallback. Keys and passwords stay server-side.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {massiveLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {([
                    { label: 'Reseller', configured: massiveStatus?.reseller?.configured },
                    { label: 'Parent username', configured: massiveStatus?.parent_username_set },
                    { label: 'Reseller key', configured: massiveStatus?.reseller?.api_key_set },
                    { label: 'Reporting', configured: massiveStatus?.reporting_configured },
                  ] as { label: string; configured: boolean | undefined }[]).map((card) => (
                    <div key={card.label} className="rounded-lg border p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">{card.label}</p>
                      <p className={`mt-1 text-sm font-medium ${card.configured ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {card.configured ? 'configured' : 'missing'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
              <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                <div>Endpoint: {massiveStatus?.host ?? '—'}:{massiveStatus?.port ?? '—'}</div>
                <div>
                  Default sub-account limit:{' '}
                  {formatBytes(massiveStatus?.reseller?.default_limit_bytes ?? 0)} · Internal soft/hard:{' '}
                  {formatBytes(massiveStatus?.reseller?.monthly_soft_limit_bytes ?? 0)} /{' '}
                  {formatBytes(massiveStatus?.reseller?.monthly_hard_limit_bytes ?? 0)}
                </div>
              </div>
              {massiveParentUsage && (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Sub-accounts</p>
                    <p className="mt-1 text-sm font-medium">{massiveParentUsage.accounts}</p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Parent usage</p>
                    <p className="mt-1 text-sm font-medium">
                      {formatBytes(massiveParentUsage.used_bytes)} /{' '}
                      {formatBytes(massiveParentUsage.limit_bytes)}
                    </p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Limit reached</p>
                    <p className="mt-1 text-sm font-medium">{massiveParentUsage.limit_reached}</p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Access revoked</p>
                    <p className="mt-1 text-sm font-medium">{massiveParentUsage.proxy_access_revoked}</p>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap items-end gap-2 border-t pt-4">
                <Input
                  value={syncFrom}
                  onChange={(event) => setSyncFrom(event.target.value)}
                  placeholder="From (YYYY-MM-DD)"
                  className="w-44"
                />
                <Input
                  value={syncTo}
                  onChange={(event) => setSyncTo(event.target.value)}
                  placeholder="To (YYYY-MM-DD)"
                  className="w-44"
                />
                <Button onClick={() => void handleSyncReseller()} disabled={syncing}>
                  {syncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                  Sync now
                </Button>
                <Button variant="outline" onClick={() => void loadMassive()} disabled={massiveLoading}>
                  Refresh status
                </Button>
              </div>
            </CardContent>
          </Card>

          {massiveAlerts.length > 0 && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {massiveAlerts.length} sub-account alert(s):{' '}
                {massiveAlerts
                  .slice(0, 4)
                  .map((alert) => `${alert.massive_subuser ?? alert.massive_account_id}: ${alert.reasons.join(', ')}`)
                  .join(' · ')}
              </AlertDescription>
            </Alert>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Reseller sub-accounts</CardTitle>
              <CardDescription>
                One sub-account per cloud seat. Used/limit is cumulative lifetime usage; monthly
                budgets are enforced internally and are not shown to customers.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-end gap-2">
                <Input
                  value={massiveProvisionProfileId}
                  onChange={(event) => setMassiveProvisionProfileId(event.target.value)}
                  placeholder="Cloud profile ID to provision"
                  className="w-96 font-mono text-xs"
                />
                <Button
                  onClick={() => void handleProvisionMassive()}
                  disabled={massiveProvisioning || !massiveProvisionProfileId.trim()}
                >
                  {massiveProvisioning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                  Provision for profile
                </Button>
                <Button variant="outline" onClick={() => void loadMassiveAccounts()} disabled={massiveAccountsLoading}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh accounts
                </Button>
              </div>
              {massiveAccountsLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : massiveAccounts.length === 0 ? (
                <p className="text-sm text-muted-foreground">No Reseller sub-accounts yet.</p>
              ) : (
                <div className="overflow-x-auto rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Sub-account</TableHead>
                        <TableHead>Profile</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Used / limit</TableHead>
                        <TableHead>Access</TableHead>
                        <TableHead>Last sync</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {massiveAccounts.map((account) => (
                        <TableRow key={account.proxy_id}>
                          <TableCell className="font-mono text-xs">
                            <div>{account.massive_subuser ?? account.massive_account_id}</div>
                            <div className="text-muted-foreground">{account.massive_account_id}</div>
                          </TableCell>
                          <TableCell className="text-xs">
                            <div>{account.linkedin_username ?? account.profile_id ?? '—'}</div>
                            <div className="font-mono text-muted-foreground">{account.profile_id ?? '—'}</div>
                          </TableCell>
                          <TableCell>
                            <Badge variant={account.massive_status === 'active' ? 'default' : 'secondary'}>
                              {account.massive_status}
                            </Badge>
                            {account.limit_reached && (
                              <Badge variant="destructive" className="ml-1">limit</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-xs">
                            {formatBytes(account.used_bytes)} / {formatBytes(account.limit_bytes ?? 0)}
                          </TableCell>
                          <TableCell className="text-xs">
                            {account.proxy_access === false ? (
                              <Badge variant="destructive">revoked</Badge>
                            ) : account.proxy_access === true ? (
                              <Badge variant="outline">ok</Badge>
                            ) : (
                              '—'
                            )}
                          </TableCell>
                          <TableCell className="text-xs">{formatDate(account.last_sync_at)}</TableCell>
                          <TableCell>
                            <div className="flex flex-wrap justify-end gap-1">
                              {account.massive_status === 'active' ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={massiveBusyId === account.proxy_id}
                                  onClick={() => void handleMassiveAction(account.proxy_id, 'disable')}
                                >
                                  Disable
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={massiveBusyId === account.proxy_id}
                                  onClick={() => void handleMassiveAction(account.proxy_id, 'enable')}
                                >
                                  Enable
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={massiveBusyId === account.proxy_id}
                                onClick={() => void handleMassiveAction(account.proxy_id, 'rotate')}
                              >
                                Rotate
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={massiveBusyId === account.proxy_id}
                                onClick={() => void handleMassiveAction(account.proxy_id, 'allocate')}
                              >
                                Top up
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pool Stats</CardTitle>
              <CardDescription>
                Cached country node counts. Below {massiveStatus?.pool_stats ? 'the configured threshold' : '1,000 nodes'} the
                admin should use country-level targeting.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-end gap-2">
                <Input
                  value={poolStatsCountry}
                  onChange={(event) => setPoolStatsCountry(event.target.value.toUpperCase().slice(0, 2))}
                  placeholder="Country (US)"
                  className="w-32"
                />
                <Button variant="outline" onClick={() => void loadPoolStats(poolStatsCountry)}>
                  Check region
                </Button>
              </div>
              {poolStats?.warnings?.length ? (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{poolStats.warnings.join(' ')}</AlertDescription>
                </Alert>
              ) : null}
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                {Object.entries(poolStats?.country_counts ?? {})
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 12)
                  .map(([country, count]) => (
                    <Badge key={country} variant="outline">
                      {country}: {count.toLocaleString()}
                    </Badge>
                  ))}
                {!poolStats?.configured && <span>Pool Stats is not configured.</span>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Globe2 className="h-4 w-4" />
                Phase 1 fallback
              </CardTitle>
              <CardDescription>
                Parent credentials with a per-profile <code>-subaccount-</code> suffix. Used
                when Reseller is disabled or unavailable.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-end gap-2">
                <Input
                  value={fallbackProfileId}
                  onChange={(event) => setFallbackProfileId(event.target.value)}
                  placeholder="Cloud profile ID"
                  className="w-96 font-mono text-xs"
                />
                <Button
                  variant="outline"
                  onClick={() => void handleProvisionFallback()}
                  disabled={provisioning || !fallbackProfileId.trim()}
                >
                  {provisioning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Provision fallback
                </Button>
                <Button variant="outline" onClick={() => void handleSyncMassive()} disabled={syncing}>
                  Sync reporting usage
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Provision fallback only for a cloud profile that has no proxy and has a region.
                The Reseller path is preferred whenever it is enabled.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog
        open={importOpen}
        onOpenChange={(open) => {
          setImportOpen(open)
          if (open) {
            setImportErrors([])
            setPreview(null)
          }
        }}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Bulk import proxies</DialogTitle>
            <DialogDescription>
              Paste one proxy per line or a CSV/TSV with a header. Passwords are encrypted on
              import and never displayed.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Textarea
              value={importText}
              onChange={(event) => {
                setImportText(event.target.value)
                setPreview(null)
              }}
              rows={7}
              placeholder={'proxy.example.com:8080:user:pass:US\nuser:pass@proxy.example.com:8080\nhttp://user:pass@proxy.example.com:8080'}
              className="font-mono text-xs"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Input
                value={importCountry}
                onChange={(event) => setImportCountry(event.target.value.toUpperCase())}
                placeholder="Default country (US)"
                maxLength={2}
                className="w-40"
              />
              <Select value={importProvider} onValueChange={(value) => value && setImportProvider(value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manual">Manual</SelectItem>
                  <SelectItem value="massive_residential">Massive residential</SelectItem>
                  <SelectItem value="massive_isp">Massive ISP</SelectItem>
                </SelectContent>
              </Select>
              <Select value={importKind} onValueChange={(value) => value && setImportKind(value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="residential">Residential</SelectItem>
                  <SelectItem value="isp">ISP</SelectItem>
                  <SelectItem value="mobile">Mobile</SelectItem>
                  <SelectItem value="datacenter">Datacenter</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" onClick={() => void handlePreview()} disabled={previewing || !importText.trim()}>
                {previewing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Preview & validate
              </Button>
            </div>

            {preview && (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-3 text-sm">
                  <span>{preview.entries} lines</span>
                  <span className="text-emerald-400">{preview.valid} valid</span>
                  <span className="text-amber-400">{preview.duplicates} duplicates</span>
                  <span className="text-red-400">{preview.failed} failed</span>
                </div>
                <div className="max-h-56 overflow-y-auto rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Line</TableHead>
                        <TableHead>Endpoint</TableHead>
                        <TableHead>Region</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Credentials</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {preview.preview.map((row) => (
                        <TableRow key={`${row.line}-${row.host}-${row.port}`}>
                          <TableCell className="text-xs">{row.line}</TableCell>
                          <TableCell className="font-mono text-xs">
                            {row.host}:{row.port}
                          </TableCell>
                          <TableCell className="text-xs">
                            {[row.country, row.subdivision, row.city].filter(Boolean).join(' · ')}
                          </TableCell>
                          <TableCell className="text-xs">{row.kind}</TableCell>
                          <TableCell className="text-xs">
                            username {row.username_masked} · password {row.has_password ? 'set' : 'missing'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}

            {importErrors.length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <p className="font-medium">Per-line errors</p>
                  <ul className="mt-1 max-h-40 list-disc space-y-1 overflow-y-auto pl-4 text-xs">
                    {importErrors.map((item) => (
                      <li key={`${item.line}-${item.error}`}>
                        Line {item.line}: {item.error}
                      </li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setImportOpen(false)}>
              Close
            </Button>
            <Button onClick={() => void handleImport()} disabled={importing || !importText.trim()}>
              {importing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              Import proxies
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(assignProxy)} onOpenChange={(open) => !open && setAssignProxy(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign proxy</DialogTitle>
            <DialogDescription>
              One active proxy per profile. A used proxy can only return to the same LinkedIn
              account.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="rounded-lg border p-3 text-xs">
              <div className="font-mono">{assignProxy?.host}:{assignProxy?.port}</div>
              <div className="text-muted-foreground">
                {assignProxy ? regionLabel(assignProxy) : ''} · {assignProxy?.provider}
              </div>
            </div>
            <div className="flex gap-2">
              <Input
                value={profileSearch}
                onChange={(event) => setProfileSearch(event.target.value)}
                placeholder="Search cloud profiles"
              />
              <Button
                variant="outline"
                onClick={() =>
                  void loadCloudProfiles(profileSearch).catch((err: unknown) =>
                    setError(err instanceof Error ? err.message : 'Failed to search profiles')
                  )
                }
              >
                Search
              </Button>
            </div>
            <div className="max-h-64 space-y-1 overflow-y-auto rounded-lg border p-1">
              {cloudProfiles.length === 0 ? (
                <p className="p-3 text-xs text-muted-foreground">No cloud profiles found.</p>
              ) : (
                cloudProfiles.map((profile) => (
                  <button
                    key={profile.id}
                    type="button"
                    onClick={() => setSelectedProfileId(profile.id)}
                    className={`flex w-full flex-col rounded-md px-3 py-2 text-left text-xs transition-colors ${
                      selectedProfileId === profile.id ? 'bg-muted' : 'hover:bg-muted/60'
                    }`}
                  >
                    <span className="font-medium">{profile.username ?? profile.id}</span>
                    <span className="text-muted-foreground">
                      {profile.email || profile.user_id} · {profile.id}
                    </span>
                    <span className="text-muted-foreground">
                      {profile.has_proxy ? `proxy ${profile.proxy_id ?? 'BYO'}` : 'no proxy'}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAssignProxy(null)}>
              Cancel
            </Button>
            <Button onClick={() => void handleAssign()} disabled={assigning || !selectedProfileId}>
              {assigning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Assign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(rotateProxy)} onOpenChange={(open) => !open && setRotateProxy(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rotate proxy password</DialogTitle>
            <DialogDescription>
              The new password is encrypted at rest and never displayed again.
            </DialogDescription>
          </DialogHeader>
          <Input
            type="password"
            value={rotatePassword}
            onChange={(event) => setRotatePassword(event.target.value)}
            placeholder="New password (min 8 characters)"
            autoComplete="new-password"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRotateProxy(null)}>
              Cancel
            </Button>
            <Button onClick={() => void handleRotate()} disabled={rotatePassword.length < 8}>
              Rotate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
