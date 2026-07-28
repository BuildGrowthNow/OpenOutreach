'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ExternalLink, RefreshCw } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { adminApi, AdminFinanceMetrics, AdminInvoice } from '@/lib/api/admin'

// ─── helpers ───────────────────────────────────────────────────────────────

function fmtCurrency(amount: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0,
  }).format(amount)
}
function fmtPct(rate: number) {
  return `${rate.toFixed(1)}%`
}

const STATUS_COLORS: Record<string, string> = {
  paid: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  open: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  void: 'bg-zinc-500/10 text-zinc-400 border-zinc-600',
  draft: 'bg-zinc-500/10 text-zinc-400 border-zinc-600',
}

const PLAN_BAR_COLORS: Record<string, string> = {
  starter: '#71717a',
  pro: '#3b82f6',
  business: '#8b5cf6',
  agency: '#f59e0b',
  cloud: '#06b6d4',
  lifetime: '#10b981',
}

// Recharts dark-theme tooltip
function DarkTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number; name: string }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="font-medium mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-muted-foreground">
          {p.name}: <span className="text-foreground font-medium">{fmtCurrency(p.value)}</span>
        </p>
      ))}
    </div>
  )
}

function FunnelDarkTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number; name: string }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="font-medium mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-muted-foreground">
          <span className="text-foreground font-medium">{p.value.toLocaleString()}</span> users
        </p>
      ))}
    </div>
  )
}

function StatCard({ title, value, sub }: { title: string; value: string; sub?: string }) {
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

const PAGE_SIZES = [20, 50, 100]

// ─── page ──────────────────────────────────────────────────────────────────

export default function AdminFinancePage() {
  const [metrics, setMetrics] = useState<AdminFinanceMetrics | null>(null)
  const [invoices, setInvoices] = useState<AdminInvoice[]>([])
  const [invoiceTotal, setInvoiceTotal] = useState(0)
  const [invoiceSkip, setInvoiceSkip] = useState(0)
  const [invoiceLimit, setInvoiceLimit] = useState(20)
  const [loading, setLoading] = useState(true)
  const [invoicesLoading, setInvoicesLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const fetchMetrics = useCallback(async () => {
    const res = await adminApi.getFinanceMetrics()
    if (res.error) throw new Error(res.error)
    if (res.data) setMetrics(res.data)
  }, [])

  const fetchInvoices = useCallback(async (skip: number, limit: number) => {
    setInvoicesLoading(true)
    const res = await adminApi.getInvoices(skip, limit)
    if (!res.error && res.data) {
      setInvoices(res.data.invoices)
      setInvoiceTotal(res.data.total)
    }
    setInvoicesLoading(false)
  }, [])

  useEffect(() => {
    fetchMetrics()
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
    fetchInvoices(0, invoiceLimit)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    setError(null)
    await Promise.all([
      fetchMetrics().catch(e => setError(e instanceof Error ? e.message : 'Failed to load')),
      fetchInvoices(invoiceSkip, invoiceLimit),
    ])
    setRefreshing(false)
  }

  const planChartData = (metrics?.revenue_by_plan ?? [])
    .filter(p => p.mrr > 0)
    .map(p => ({ name: p.display_name, mrr: parseFloat(p.mrr.toFixed(2)), count: p.count, key: p.plan }))

  const funnelChartData = metrics?.funnel ? [
    { name: 'Signups', value: metrics.funnel.total_signups, fill: '#3b82f6' },
    { name: 'Verified', value: metrics.funnel.email_verified, fill: '#8b5cf6' },
    { name: 'Trial started', value: metrics.funnel.trial_started, fill: '#f59e0b' },
    { name: 'Converted', value: metrics.funnel.converted, fill: '#10b981' },
    { name: 'Churned', value: metrics.funnel.churned, fill: '#ef4444' },
  ] : []

  const totalPages = Math.max(1, Math.ceil(invoiceTotal / invoiceLimit))
  const currentPage = Math.floor(invoiceSkip / invoiceLimit) + 1

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Finance</h1>
          <p className="text-muted-foreground mt-1">Revenue metrics, invoices, and user funnel</p>
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

      {/* KPI cards */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Key metrics</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {loading ? Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}><CardHeader className="pb-2"><Skeleton className="h-4 w-24" /></CardHeader><CardContent><Skeleton className="h-8 w-16" /></CardContent></Card>
          )) : (
            <>
              <StatCard title="MRR" value={fmtCurrency(metrics?.mrr ?? 0)} sub="Monthly recurring" />
              <StatCard title="ARR" value={fmtCurrency(metrics?.arr ?? 0)} sub="Annual run-rate" />
              <StatCard title="Active subs" value={(metrics?.active_subscriptions ?? 0).toString()} />
              <StatCard title="Trialing" value={(metrics?.trialing_users ?? 0).toString()} />
              <StatCard title="Trial conversion" value={fmtPct(metrics?.trial_conversion_rate ?? 0)} sub="Trial → paid" />
              <StatCard title="Churn rate" value={fmtPct(metrics?.churn_rate ?? 0)} sub="Canceled / total" />
            </>
          )}
        </div>
      </div>

      {/* Charts row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Revenue by plan bar chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Revenue by plan (MRR)</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-52 w-full" /> : planChartData.length === 0 ? (
              <p className="text-sm text-muted-foreground">No active subscriptions.</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={planChartData} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
                  <XAxis dataKey="name" tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `$${v}`} />
                  <Tooltip content={<DarkTooltip />} />
                  <Bar dataKey="mrr" name="MRR" radius={[4, 4, 0, 0]}>
                    {planChartData.map(entry => (
                      <Cell key={entry.key} fill={PLAN_BAR_COLORS[entry.key] ?? '#71717a'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* User funnel bar chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">User funnel</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-52 w-full" /> : funnelChartData.length === 0 ? (
              <p className="text-sm text-muted-foreground">No data.</p>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={funnelChartData} layout="vertical" margin={{ top: 4, right: 24, left: 4, bottom: 4 }}>
                  <XAxis type="number" tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} width={90} />
                  <Tooltip content={<FunnelDarkTooltip />} />
                  <Bar dataKey="value" name="Users" radius={[0, 4, 4, 0]}>
                    {funnelChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Invoices table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-base">Invoices</CardTitle>
          <span className="text-sm text-muted-foreground">{invoiceTotal} total</span>
        </CardHeader>
        <CardContent className="p-0">
          {invoicesLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : invoices.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">No invoices.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Invoice ID</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">User</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Amount</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Status</th>
                    <th className="text-left px-4 py-3 text-muted-foreground font-medium">Period</th>
                    <th className="w-10 px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {invoices.map(inv => (
                    <tr key={inv.id} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{inv.id.slice(0, 16)}…</td>
                      <td className="px-4 py-3">
                        {inv.user_id !== 'unknown' ? (
                          <Link href={`/admin/users/${inv.user_id}`} className="hover:underline text-sm">
                            {inv.user_email}
                          </Link>
                        ) : (
                          <span className="text-muted-foreground">{inv.user_email}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-medium">
                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(inv.amount / 100)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={`text-xs capitalize ${STATUS_COLORS[inv.status] ?? ''}`}>
                          {inv.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {new Date(inv.period_start * 1000).toLocaleDateString()} – {new Date(inv.period_end * 1000).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        {inv.pdf_url && (
                          <a href={inv.pdf_url} target="_blank" rel="noopener noreferrer">
                            <ExternalLink className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {!invoicesLoading && invoiceTotal > 0 && (
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Rows:</span>
                <div className="flex gap-1">
                  {PAGE_SIZES.map(n => (
                    <Button
                      key={n}
                      variant={invoiceLimit === n ? 'default' : 'outline'}
                      size="sm"
                      className="h-6 px-2 text-xs"
                      onClick={() => { setInvoiceLimit(n); setInvoiceSkip(0); fetchInvoices(0, n) }}
                    >
                      {n}
                    </Button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Page {currentPage} of {totalPages}</span>
                <Button
                  variant="outline" size="sm"
                  disabled={invoiceSkip === 0}
                  onClick={() => {
                    const newSkip = Math.max(0, invoiceSkip - invoiceLimit)
                    setInvoiceSkip(newSkip)
                    fetchInvoices(newSkip, invoiceLimit)
                  }}
                >
                  Previous
                </Button>
                <Button
                  variant="outline" size="sm"
                  disabled={invoiceSkip + invoiceLimit >= invoiceTotal}
                  onClick={() => {
                    const newSkip = invoiceSkip + invoiceLimit
                    setInvoiceSkip(newSkip)
                    fetchInvoices(newSkip, invoiceLimit)
                  }}
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
