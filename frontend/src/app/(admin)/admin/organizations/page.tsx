'use client'

import { useCallback, useEffect, useState } from 'react'
import { Building2, RefreshCw } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  adminApi,
  type AdminOrganizationDetail,
  type AdminOrganizationSummary,
} from '@/lib/api/admin'

function formatBytes(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const exponent = Math.min(
    Math.max(0, Math.floor(Math.log(bytes) / Math.log(1000))),
    units.length - 1
  )
  return `${(bytes / 1000 ** exponent).toFixed(exponent > 1 ? 2 : 0)} ${units[exponent]}`
}

export default function AdminOrganizationsPage() {
  const [organizations, setOrganizations] = useState<AdminOrganizationSummary[]>([])
  const [selected, setSelected] = useState<AdminOrganizationDetail | null>(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [seatCount, setSeatCount] = useState('0')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await adminApi.getOrganizations({ search: search || undefined, limit: 100 })
      if (response.error) {
        setError(response.error)
        return
      }
      setOrganizations(response.data?.organizations ?? [])
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    void load()
  }, [load])

  const openDetail = async (orgId: string) => {
    setDetailLoading(true)
    try {
      const response = await adminApi.getOrganization(orgId)
      if (response.error) {
        setError(response.error)
        return
      }
      setSelected(response.data ?? null)
      setSeatCount(String(response.data?.organization.cloud_seats ?? 0))
      setReason('')
    } finally {
      setDetailLoading(false)
    }
  }

  const applyOverride = async () => {
    if (!selected) return
    if (reason.trim().length < 3) {
      setError('A reason is required for a seat override')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const response = await adminApi.overrideOrganizationSeats(selected.organization.id, {
        cloud_seats: Number(seatCount) || 0,
        reason: reason.trim(),
      })
      if (response.error) {
        setError(response.error)
        return
      }
      await openDetail(selected.organization.id)
      await load()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Organizations</h1>
          <p className="text-muted-foreground mt-1">
            Workspace owners, plans, seats, members, and assigned profiles.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search name or owner id"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="w-64"
          />
          <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Workspaces</CardTitle>
            <CardDescription>{organizations.length} organizations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {loading && <Skeleton className="h-40 w-full" />}
            {!loading && organizations.length === 0 && (
              <p className="text-sm text-muted-foreground">No organizations found.</p>
            )}
            {organizations.map((org) => (
              <button
                key={org.id}
                type="button"
                onClick={() => void openDetail(org.id)}
                className="flex w-full flex-col gap-2 rounded-lg border border-border/60 p-3 text-left transition-colors hover:bg-muted/40 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 shrink-0" />
                    <span className="truncate font-medium">{org.name}</span>
                    <Badge variant={org.seat_override ? 'destructive' : 'secondary'} className="capitalize">
                      {org.plan}
                    </Badge>
                    {org.seat_override && <Badge variant="outline">override</Badge>}
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {org.owner_email || org.owner_user_id}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-4 text-xs text-muted-foreground">
                  <span>{org.members_count} members</span>
                  <span>{org.cloud_seats_used} seats used</span>
                  <span>{org.assigned_profiles} assigned</span>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Organization detail</CardTitle>
            <CardDescription>
              {selected ? selected.organization.name : 'Select a workspace to inspect it.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {detailLoading && <Skeleton className="h-64 w-full" />}
            {!detailLoading && !selected && (
              <p className="text-sm text-muted-foreground">No workspace selected.</p>
            )}
            {selected && (
              <>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Owner</p>
                    <p className="truncate">{selected.organization.owner_email || selected.organization.owner_user_id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Plan</p>
                    <p className="capitalize">{selected.organization.plan}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Cloud seats</p>
                    <p>
                      {selected.organization.cloud_seats_used} of{' '}
                      {selected.organization.linkedin_account_limit} used ·{' '}
                      {selected.organization.cloud_seats} extra
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Channel bundles</p>
                    <p>
                      {selected.organization.linkedin_seats} LinkedIn ·{' '}
                      {selected.organization.duo_seats} Duo ·{' '}
                      {selected.organization.whatsapp_only_seats} WhatsApp-only
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Usage</p>
                    <p>{selected.organization.credentialed_profiles} seats · {selected.organization.assigned_profiles} assigned</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Proxy usage</p>
                    <p>
                      {formatBytes(selected.usage?.total_bytes ?? 0)} ·{' '}
                      {selected.usage?.proxies ?? 0} proxies
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Proxy alerts</p>
                    <p>
                      {selected.usage?.limit_reached ?? 0} limit ·{' '}
                      {selected.usage?.access_revoked ?? 0} revoked ·{' '}
                      {selected.usage?.country_mismatch ?? 0} mismatch
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Usage by channel</p>
                    <p className="text-xs">
                      {Object.entries(selected.usage?.per_channel ?? {})
                        .map(([channel, bytes]) => `${channel}: ${formatBytes(bytes)}`)
                        .join(' · ') || 'No usage synced'}
                    </p>
                  </div>
                </div>

                {(selected.usage?.seat_alerts ?? []).length > 0 && (
                  <Alert variant="destructive">
                    <AlertDescription>
                      This workspace is over its unified cloud seat pool:{' '}
                      {(selected.usage?.seat_alerts ?? [])
                        .map((alert) => `${alert.used}/${alert.limit}`)
                        .join(' · ')}
                    </AlertDescription>
                  </Alert>
                )}

                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Members</p>
                  {selected.members.map((member) => (
                    <div key={member.user_id} className="flex items-center justify-between rounded-md border border-border/60 p-2 text-sm">
                      <span className="truncate">{member.email}</span>
                      <Badge variant="secondary" className="capitalize">{member.role}</Badge>
                    </div>
                  ))}
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Profiles</p>
                  {selected.profiles.map((profile) => (
                    <div key={`${profile.channel ?? 'linkedin'}-${profile.id}`} className="flex items-center justify-between rounded-md border border-border/60 p-2 text-sm">
                      <span className="truncate">
                        {profile.linkedin_username ||
                          profile.phone_number ||
                          profile.display_name ||
                          profile.id}
                      </span>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="capitalize">
                          {profile.channel ?? 'linkedin'}
                        </Badge>
                        {profile.cloud_mode && profile.cloud_mode !== 'desktop' && (
                          <Badge variant="secondary">{profile.cloud_mode}</Badge>
                        )}
                        <Badge variant={profile.active ? 'default' : 'secondary'}>
                          {profile.active ? 'Active' : 'Paused'}
                        </Badge>
                        {profile.proxy_assigned && <Badge variant="outline">Proxy</Badge>}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Proxies</p>
                  {(selected.proxies ?? []).length === 0 && (
                    <p className="text-sm text-muted-foreground">No proxies assigned.</p>
                  )}
                  {(selected.proxies ?? []).map((proxy) => (
                    <div key={proxy.id} className="flex items-center justify-between rounded-md border border-border/60 p-2 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-mono text-xs">{proxy.id}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {[proxy.country, proxy.subdivision, proxy.city].filter(Boolean).join(' · ') || '—'}
                          {' · '}
                          {formatBytes(proxy.massive_used_bytes)} / {formatBytes(proxy.massive_limit_bytes ?? 0)}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <Badge variant={proxy.status === 'assigned' ? 'default' : 'secondary'}>
                          {proxy.status ?? 'unknown'}
                        </Badge>
                        {proxy.massive_status && <Badge variant="outline">{proxy.massive_status}</Badge>}
                        {proxy.country_mismatch && <Badge variant="destructive">mismatch</Badge>}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-3 rounded-lg border border-border/60 p-3">
                  <p className="text-sm font-medium">Seat override</p>
                  <p className="text-xs text-muted-foreground">
                    Audited. This changes the workspace entitlement, not Stripe billing.
                  </p>
                  <div className="flex items-end gap-2">
                    <div className="space-y-1">
                      <Label htmlFor="seat-count">Extra cloud seats</Label>
                      <Input
                        id="seat-count"
                        type="number"
                        min={0}
                        value={seatCount}
                        onChange={(event) => setSeatCount(event.target.value)}
                        className="w-28"
                      />
                    </div>
                    <div className="flex-1 space-y-1">
                      <Label htmlFor="seat-reason">Reason</Label>
                      <Input
                        id="seat-reason"
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        placeholder="Support ticket / approved override"
                      />
                    </div>
                  </div>
                  <Button onClick={() => void applyOverride()} disabled={saving}>
                    {saving ? 'Saving…' : 'Apply override'}
                  </Button>
                </div>

                {selected.audit_events.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Recent audit</p>
                    {selected.audit_events.slice(0, 8).map((event) => (
                      <div key={event.id} className="flex items-center justify-between gap-2 text-xs">
                        <span className="font-mono">{event.event}</span>
                        <span className="truncate text-muted-foreground">
                          {event.target_email || event.target_user_id || '—'}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
