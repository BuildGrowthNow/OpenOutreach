'use client'

import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, Loader2, Plus, RefreshCw, ShieldAlert } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { adminApi, AdminProxy } from '@/lib/api/admin'

const STATUS_BADGE: Record<string, string> = {
  available: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  assigned: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  disabled: 'bg-zinc-500/10 text-zinc-300 border-zinc-600',
  error: 'bg-red-500/10 text-red-400 border-red-500/30',
  retired: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
}

export default function AdminProxiesPage() {
  const [proxies, setProxies] = useState<AdminProxy[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [importText, setImportText] = useState('')
  const [defaultCountry, setDefaultCountry] = useState('')
  const [importing, setImporting] = useState(false)
  const [importErrors, setImportErrors] = useState<{ line: number; error: string }[]>([])
  const [busyId, setBusyId] = useState<string | null>(null)
  const [assignProfileId, setAssignProfileId] = useState('')

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await adminApi.getProxies({ limit: 200 })
      if (response.data) {
        setProxies(response.data.proxies)
        setTotal(response.data.total)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load proxies')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleImport = async () => {
    if (!importText.trim()) return
    try {
      setImporting(true)
      setError(null)
      setMessage(null)
      setImportErrors([])
      const response = await adminApi.importProxies({
        text: importText,
        default_country: defaultCountry.trim().toUpperCase() || undefined,
      })
      if (response.data) {
        setMessage(
          `Imported ${response.data.created}, skipped ${response.data.skipped}, failed ${response.data.failed}.`
        )
        setImportErrors(response.data.errors ?? [])
        setImportText('')
        await load()
      } else if (response.error) {
        throw new Error(response.error)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  const handleTest = async (proxy: AdminProxy) => {
    try {
      setBusyId(proxy.id)
      setError(null)
      const response = await adminApi.testProxy(proxy.id)
      if (response.data) {
        setMessage(
          response.data.success
            ? `Test passed: ${response.data.ip ?? 'unknown IP'} · ${response.data.country ?? 'unknown country'} · ${response.data.latency_ms ?? 0}ms`
            : `Test failed: ${response.data.error ?? response.data.message}`
        )
        await load()
      } else if (response.error) {
        throw new Error(response.error)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Proxy test failed')
    } finally {
      setBusyId(null)
    }
  }

  const handleAssign = async (proxy: AdminProxy) => {
    if (!assignProfileId.trim()) {
      setError('Enter the cloud LinkedIn profile ID before assigning.')
      return
    }
    try {
      setBusyId(proxy.id)
      setError(null)
      const response = await adminApi.assignProxy(proxy.id, assignProfileId.trim())
      if (response.error) throw new Error(response.error)
      setMessage('Proxy assigned.')
      setAssignProfileId('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assignment failed')
    } finally {
      setBusyId(null)
    }
  }

  const handleDisable = async (proxy: AdminProxy) => {
    try {
      setBusyId(proxy.id)
      setError(null)
      const response = await adminApi.disableProxy(proxy.id)
      if (response.error) throw new Error(response.error)
      setMessage('Proxy disabled.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Disable failed')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Managed proxies</h1>
          <p className="text-sm text-muted-foreground">
            {total} proxies in inventory. Passwords are encrypted and never shown.
          </p>
        </div>
        <Button variant="outline" onClick={load} disabled={loading}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
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
      {importErrors.length > 0 && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <p className="font-medium">Import errors</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs">
              {importErrors.map((item) => (
                <li key={`${item.line}-${item.error}`}>
                  Line {item.line}: {item.error}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Bulk import</CardTitle>
          <CardDescription>
            Paste one proxy per line: host:port:user:pass[:country],
            user:pass@host:port, or a full proxy URL. CSV/TSV with a header works too.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={importText}
            onChange={(event) => setImportText(event.target.value)}
            rows={6}
            placeholder={'proxy.example.com:8080:user:pass:US\nproxy.example.com:8080:user:pass'}
            className="font-mono text-xs"
          />
          <div className="flex flex-wrap items-center gap-3">
            <Input
              value={defaultCountry}
              onChange={(event) => setDefaultCountry(event.target.value.toUpperCase())}
              placeholder="Default country (US)"
              maxLength={2}
              className="w-48"
            />
            <Button onClick={handleImport} disabled={importing || !importText.trim()}>
              {importing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Import proxies
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Inventory</CardTitle>
          <CardDescription>
            Assign a proxy to one cloud profile. A proxy is never reused for a different LinkedIn account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            value={assignProfileId}
            onChange={(event) => setAssignProfileId(event.target.value)}
            placeholder="Cloud LinkedIn profile ID for assignment"
            className="max-w-xl font-mono text-xs"
          />
          {loading ? (
            <Skeleton className="h-40 w-full" />
          ) : proxies.length === 0 ? (
            <p className="text-sm text-muted-foreground">No proxies imported yet.</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Endpoint</TableHead>
                    <TableHead>Region</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Assigned profile</TableHead>
                    <TableHead>Last test</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {proxies.map((proxy) => (
                    <TableRow key={proxy.id}>
                      <TableCell>
                        <div className="font-mono text-xs">
                          {proxy.host}:{proxy.port}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {proxy.username ? `${proxy.username} · ` : ''}
                          {proxy.protocol}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">
                        {[proxy.country, proxy.subdivision, proxy.city].filter(Boolean).join(' · ')}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={STATUS_BADGE[proxy.status] ?? ''}>
                          {proxy.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {proxy.linkedin_profile_id ?? '—'}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {proxy.last_test_ip ?? '—'}
                        {proxy.last_test_country ? ` · ${proxy.last_test_country}` : ''}
                        {proxy.last_test_latency_ms ? ` · ${proxy.last_test_latency_ms}ms` : ''}
                        {proxy.last_error ? (
                          <span className="block text-red-400">{proxy.last_error}</span>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleTest(proxy)}
                            disabled={busyId === proxy.id}
                          >
                            {busyId === proxy.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              'Test'
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleAssign(proxy)}
                            disabled={busyId === proxy.id || proxy.status !== 'available'}
                          >
                            Assign
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDisable(proxy)}
                            disabled={busyId === proxy.id || Boolean(proxy.linkedin_profile_id)}
                          >
                            <ShieldAlert className="h-3 w-3" />
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
    </div>
  )
}
