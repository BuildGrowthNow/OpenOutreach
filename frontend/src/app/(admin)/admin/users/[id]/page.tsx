'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, ChevronDown, ChevronRight, Copy, ExternalLink, MoreHorizontal, RefreshCw,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  adminApi,
  AdminUserDetail,
  AdminLinkedInProfile,
  AdminCampaign,
  AdminTask,
  AdminActionLog,
  AdminAuditLog,
  AdminInvoice,
} from '@/lib/api/admin'

// ─────────────────────────────────────── helpers ───────────────────────────────

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
const TASK_STATUS_COLORS: Record<string, string> = {
  COMPLETED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  RUNNING: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  PENDING: 'bg-zinc-500/10 text-zinc-400 border-zinc-600',
  FAILED: 'bg-red-500/10 text-red-400 border-red-500/30',
}

function fmt(dateStr: string | null | undefined) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString()
}
function timeAgo(dateStr: string | null | undefined) {
  if (!dateStr) return '—'
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
function maskStripe(id: string | null | undefined) {
  if (!id) return '—'
  return `${id.slice(0, 8)}****${id.slice(-4)}`
}
function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <Button
      variant="ghost" size="sm" className="h-6 w-6 p-0 ml-1"
      onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
    >
      <Copy className={`h-3 w-3 ${copied ? 'text-emerald-400' : ''}`} />
    </Button>
  )
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  )
}

// ─────────────────────────────────────── page ──────────────────────────────────

export default function AdminUserDetailPage() {
  const params = useParams()
  const router = useRouter()
  const userId = params.id as string

  const [user, setUser] = useState<AdminUserDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  // Tab data
  const [profiles, setProfiles] = useState<AdminLinkedInProfile[]>([])
  const [campaigns, setCampaigns] = useState<AdminCampaign[]>([])
  const [tasks, setTasks] = useState<AdminTask[]>([])
  const [actionLogs, setActionLogs] = useState<AdminActionLog[]>([])
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([])
  const [invoices, setInvoices] = useState<AdminInvoice[]>([])
  const [tabDataLoaded, setTabDataLoaded] = useState<Record<string, boolean>>({})

  // Profile tab edits
  const [editStatus, setEditStatus] = useState('')
  const [editAdminRole, setEditAdminRole] = useState('')
  const [editIsAdmin, setEditIsAdmin] = useState(false)
  const [adminNotes, setAdminNotes] = useState('')
  const notesSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Billing tab edits
  const [editPlan, setEditPlan] = useState('')
  const [editBillingPeriod, setEditBillingPeriod] = useState('')
  const [editLinkedInLimit, setEditLinkedInLimit] = useState('')
  const [editCampaignLimit, setEditCampaignLimit] = useState('')
  const [editCloudProfiles, setEditCloudProfiles] = useState('')

  // Dialog state
  const [deleteDialog, setDeleteDialog] = useState(false)
  const [impersonateDialog, setImpersonateDialog] = useState(false)
  const [extendTrialDialog, setExtendTrialDialog] = useState(false)
  const [cancelSubDialog, setCancelSubDialog] = useState(false)
  const [extendDays, setExtendDays] = useState('7')

  const fetchUser = useCallback(async () => {
    const res = await adminApi.getUser(userId)
    if (res.error) { setError(res.error); return }
    if (res.data) {
      setUser(res.data)
      setEditStatus(res.data.status)
      setEditAdminRole(res.data.admin_role ?? 'none')
      setEditIsAdmin(res.data.is_admin)
      setAdminNotes(res.data.admin_notes ?? '')
      setEditPlan(res.data.plan)
      setEditBillingPeriod(res.data.billing_period ?? 'monthly')
      setEditLinkedInLimit(res.data.linkedin_account_limit.toString())
      setEditCampaignLimit(res.data.campaign_limit?.toString() ?? '')
      setEditCloudProfiles(res.data.cloud_profiles.toString())
    }
  }, [userId])

  useEffect(() => {
    fetchUser().finally(() => setLoading(false))
  }, [fetchUser])

  async function loadTabData(tab: string) {
    if (tabDataLoaded[tab]) return
    setTabDataLoaded(prev => ({ ...prev, [tab]: true }))
    if (tab === 'linkedin') {
      const [profilesRes, tasksRes] = await Promise.all([
        adminApi.getUserLinkedInProfiles(userId),
        adminApi.getUserTasks(userId),
      ])
      if (profilesRes.data) setProfiles(profilesRes.data.profiles)
      if (tasksRes.data) setTasks(tasksRes.data.tasks)
    } else if (tab === 'campaigns') {
      const res = await adminApi.getUserCampaigns(userId)
      if (res.data) setCampaigns(res.data.campaigns)
    } else if (tab === 'activity') {
      const [logsRes, tasksRes] = await Promise.all([
        adminApi.getUserActionLogs(userId),
        adminApi.getUserTasks(userId),
      ])
      if (logsRes.data) setActionLogs(logsRes.data.logs)
      if (tasksRes.data) setTasks(tasksRes.data.tasks)
    } else if (tab === 'audit') {
      const res = await adminApi.getAuditLogs({ target_user_id: userId, limit: 100 })
      if (res.data) setAuditLogs(res.data.logs)
    } else if (tab === 'billing') {
      const res = await adminApi.getInvoices(0, 20, userId)
      if (res.data) setInvoices(res.data.invoices)
    }
  }

  function showSuccess(msg: string) {
    setActionSuccess(msg)
    setTimeout(() => setActionSuccess(null), 3000)
  }

  async function handleSaveProfile() {
    if (!user) return
    setSaving(true)
    setActionError(null)
    const res = await adminApi.updateUser(userId, {
      status: editStatus,
      admin_role: editAdminRole === 'none' ? '' : editAdminRole,
      is_admin: editIsAdmin,
    })
    if (res.error) { setActionError(res.error) }
    else if (res.data) { setUser(res.data); showSuccess('Profile saved') }
    setSaving(false)
  }

  async function handleSavePlan() {
    if (!user) return
    setSaving(true)
    setActionError(null)
    const res = await adminApi.setPlan(userId, {
      plan: editPlan,
      billing_period: editBillingPeriod || undefined,
      linkedin_account_limit: editLinkedInLimit ? Number(editLinkedInLimit) : undefined,
      campaign_limit: editCampaignLimit ? Number(editCampaignLimit) : undefined,
      cloud_profiles: editCloudProfiles ? Number(editCloudProfiles) : undefined,
    })
    if (res.error) { setActionError(res.error) }
    else if (res.data) { setUser(res.data); showSuccess('Billing saved') }
    setSaving(false)
  }

  async function handleForceVerifyEmail() {
    setActionError(null)
    const res = await adminApi.verifyEmail(userId)
    if (res.error) setActionError(res.error)
    else { await fetchUser(); showSuccess('Email marked as verified') }
  }

  async function handleBlockToggle() {
    if (!user) return
    const newStatus = user.status === 'blocked' ? 'active' : 'blocked'
    setActionError(null)
    const res = await adminApi.updateUser(userId, { status: newStatus })
    if (res.error) setActionError(res.error)
    else if (res.data) { setUser(res.data); setEditStatus(res.data.status) }
  }

  async function handleDelete() {
    setActionError(null)
    const res = await adminApi.deleteUser(userId)
    if (res.error) { setActionError(res.error); setDeleteDialog(false) }
    else router.push('/admin/users')
  }

  async function handleRestore() {
    setActionError(null)
    const res = await adminApi.restoreUser(userId)
    if (res.error) setActionError(res.error)
    else { await fetchUser(); showSuccess('User restored') }
  }

  async function handleSendPasswordReset() {
    setActionError(null)
    const res = await adminApi.sendPasswordReset(userId)
    if (res.error) setActionError(res.error)
    else showSuccess('Password reset email sent')
  }

  async function handleImpersonate() {
    setImpersonateDialog(false)
    setActionError(null)
    const res = await adminApi.impersonate(userId)
    if (res.error) { setActionError(res.error); return }
    if (res.data) {
      const token = res.data.access_token
      window.open(`/impersonate?token=${encodeURIComponent(token)}`, '_blank')
    }
  }

  async function handleExtendTrial() {
    const days = parseInt(extendDays, 10)
    if (!days || days < 1 || days > 365) { setActionError('Enter 1–365 days'); return }
    setActionError(null)
    const res = await adminApi.extendTrial(userId, days)
    if (res.error) setActionError(res.error)
    else { await fetchUser(); setExtendTrialDialog(false); showSuccess(`Trial extended by ${days} days`) }
  }

  async function handleCancelSubscription() {
    setCancelSubDialog(false)
    setActionError(null)
    const res = await adminApi.cancelSubscription(userId)
    if (res.error) setActionError(res.error)
    else { await fetchUser(); showSuccess('Subscription canceled') }
  }

  function handleNotesBlur() {
    if (notesSaveTimer.current) clearTimeout(notesSaveTimer.current)
    notesSaveTimer.current = setTimeout(() => {
      adminApi.updateUserNotes(userId, adminNotes || null)
    }, 500)
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (error || !user) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        <Alert variant="destructive">
          <AlertDescription>{error ?? 'User not found'}</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Back nav */}
      <Button variant="ghost" size="sm" asChild>
        <Link href="/admin/users"><ArrowLeft className="mr-2 h-4 w-4" /> Users</Link>
      </Button>

      {/* Action feedback */}
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}
      {actionSuccess && (
        <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
          <AlertDescription>{actionSuccess}</AlertDescription>
        </Alert>
      )}

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold">{user.email}</h1>
            <Badge variant="outline" className={`capitalize ${PLAN_COLORS[user.plan] ?? ''}`}>{user.plan}</Badge>
            <Badge variant="outline" className={`capitalize ${STATUS_COLORS[user.status] ?? ''}`}>{user.status}</Badge>
            {user.is_deleted && <Badge variant="outline" className="bg-red-500/10 text-red-400 border-red-500/30">Deleted</Badge>}
          </div>
          {user.full_name && <p className="text-muted-foreground">{user.full_name}</p>}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant={user.status === 'blocked' ? 'default' : 'outline'}
            size="sm"
            onClick={handleBlockToggle}
          >
            {user.status === 'blocked' ? 'Unblock' : 'Block'}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setImpersonateDialog(true)}>
            Impersonate
          </Button>
          {user.is_deleted ? (
            <Button variant="outline" size="sm" onClick={handleRestore}>Restore</Button>
          ) : (
            <Button variant="outline" size="sm" className="text-destructive border-destructive/40 hover:bg-destructive/10" onClick={() => setDeleteDialog(true)}>
              Delete
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                More <ChevronDown className="ml-1 h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleSendPasswordReset}>Send Password Reset</DropdownMenuItem>
              <DropdownMenuItem onClick={handleForceVerifyEmail}>Force Verify Email</DropdownMenuItem>
              {user.is_deleted && <DropdownMenuItem onClick={handleRestore}>Restore Account</DropdownMenuItem>}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="profile" onValueChange={loadTabData}>
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="billing">Billing</TabsTrigger>
          <TabsTrigger value="linkedin">LinkedIn & Execution</TabsTrigger>
          <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
          <TabsTrigger value="audit">Audit Trail</TabsTrigger>
        </TabsList>

        {/* ─── Tab 1: Profile ─── */}
        <TabsContent value="profile" className="mt-4">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Editable fields */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Account details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1">
                  <Label>Status</Label>
                  <Select value={editStatus} onValueChange={v => { if (v) setEditStatus(v) }}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="blocked">Blocked</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>Admin role</Label>
                  <Select value={editAdminRole} onValueChange={v => { if (v) setEditAdminRole(v) }}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      <SelectItem value="support">Support</SelectItem>
                      <SelectItem value="finance">Finance</SelectItem>
                      <SelectItem value="superadmin">Superadmin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-3">
                  <Switch checked={editIsAdmin} onCheckedChange={setEditIsAdmin} id="is-admin-switch" />
                  <Label htmlFor="is-admin-switch">Admin access</Label>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Email verified:</span>
                  <Badge variant="outline" className={user.email_verified ? STATUS_COLORS.active : STATUS_COLORS.inactive}>
                    {user.email_verified ? 'Verified' : 'Unverified'}
                  </Badge>
                  {!user.email_verified && (
                    <Button variant="outline" size="sm" className="h-6 text-xs" onClick={handleForceVerifyEmail}>
                      Force verify
                    </Button>
                  )}
                </div>
                <Button onClick={handleSaveProfile} disabled={saving} size="sm">
                  {saving ? 'Saving…' : 'Save profile'}
                </Button>
              </CardContent>
            </Card>

            {/* Read-only fields */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Identity & meta</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="User ID">
                  <span className="font-mono text-xs">{user.id}</span>
                  <CopyButton value={user.id} />
                </Field>
                <Field label="Email">
                  <span>{user.email}</span>
                  <span className="block text-xs text-muted-foreground">Email changes require re-verification</span>
                </Field>
                <Field label="Full name">{user.full_name || '—'}</Field>
                <Field label="Signed up">{fmt(user.created_at)}</Field>
                <Field label="Signup IP">{user.signup_ip ?? '—'}</Field>
                <Field label="Last login">{fmt(user.last_login)}</Field>
                <Field label="Last login IP">{user.last_login_ip ?? '—'}</Field>
                <Field label="Referral code">{user.referral_code ?? '—'}</Field>
                <Field label="Referred by">
                  {user.referrer_id ? (
                    <Link href={`/admin/users/${user.referrer_id}`} className="hover:underline flex items-center gap-1">
                      {user.referrer_id.slice(0, 8)}…
                      <ChevronRight className="h-3 w-3" />
                    </Link>
                  ) : '—'}
                </Field>
                <Field label="Referral credits">{user.referral_credits_earned}</Field>
                {user.is_deleted && (
                  <>
                    <Field label="Deleted at">{fmt(user.deleted_at)}</Field>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Admin notes */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Admin notes</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  placeholder="Internal notes — auto-saved on blur"
                  value={adminNotes}
                  onChange={e => setAdminNotes(e.target.value)}
                  onBlur={handleNotesBlur}
                  rows={4}
                  className="resize-none"
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ─── Tab 2: Billing ─── */}
        <TabsContent value="billing" className="mt-4">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Subscription</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1">
                  <Label>Plan</Label>
                  <Select value={editPlan} onValueChange={v => { if (v) setEditPlan(v) }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {['starter', 'pro', 'business', 'agency', 'cloud', 'lifetime'].map(p => (
                        <SelectItem key={p} value={p} className="capitalize">{p}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>Billing period</Label>
                  <Select value={editBillingPeriod} onValueChange={v => { if (v) setEditBillingPeriod(v) }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="monthly">Monthly</SelectItem>
                      <SelectItem value="annual">Annual</SelectItem>
                      <SelectItem value="lifetime">Lifetime</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>LinkedIn account limit</Label>
                  <Input type="number" value={editLinkedInLimit} onChange={e => setEditLinkedInLimit(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Campaign limit</Label>
                  <Input type="number" value={editCampaignLimit} onChange={e => setEditCampaignLimit(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Cloud profiles</Label>
                  <Input type="number" value={editCloudProfiles} onChange={e => setEditCloudProfiles(e.target.value)} />
                </div>
                <div className="flex gap-2">
                  <Button onClick={handleSavePlan} disabled={saving} size="sm">
                    {saving ? 'Saving…' : 'Save plan'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Billing status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Subscription status">
                    <Badge variant="outline" className={`capitalize ${SUB_COLORS[user.subscription_status] ?? ''}`}>
                      {user.subscription_status}
                    </Badge>
                  </Field>
                  <Field label="Trial ends at">{fmt(user.trial_ends_at)}</Field>
                  <Field label="Current period end">{fmt(user.current_period_end)}</Field>
                  <Field label="Stripe customer">
                    <span className="font-mono text-xs">{maskStripe(user.stripe_customer_id)}</span>
                    {user.stripe_customer_id && <CopyButton value={user.stripe_customer_id} />}
                  </Field>
                  <Field label="Stripe subscription">
                    <span className="font-mono text-xs">{maskStripe(user.stripe_subscription_id)}</span>
                    {user.stripe_subscription_id && <CopyButton value={user.stripe_subscription_id} />}
                  </Field>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button variant="outline" size="sm" onClick={() => setExtendTrialDialog(true)}>
                    Extend trial
                  </Button>
                  {user.stripe_subscription_id && (
                    <Button
                      variant="outline" size="sm"
                      className="text-destructive border-destructive/40 hover:bg-destructive/10"
                      onClick={() => setCancelSubDialog(true)}
                    >
                      Cancel subscription
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Invoices */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Invoices</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {invoices.length === 0 ? (
                  <p className="p-4 text-sm text-muted-foreground">No invoices found.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left px-4 py-2 text-muted-foreground font-medium">Date</th>
                          <th className="text-left px-4 py-2 text-muted-foreground font-medium">Amount</th>
                          <th className="text-left px-4 py-2 text-muted-foreground font-medium">Status</th>
                          <th className="text-left px-4 py-2 text-muted-foreground font-medium">Period</th>
                          <th className="w-10 px-4 py-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {invoices.map(inv => (
                          <tr key={inv.id} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                            <td className="px-4 py-2 text-muted-foreground">
                              {new Date(inv.created * 1000).toLocaleDateString()}
                            </td>
                            <td className="px-4 py-2 font-medium">
                              {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(inv.amount / 100)}
                            </td>
                            <td className="px-4 py-2">
                              <Badge variant="outline" className={`capitalize text-xs ${inv.status === 'paid' ? STATUS_COLORS.active : STATUS_COLORS.inactive}`}>
                                {inv.status}
                              </Badge>
                            </td>
                            <td className="px-4 py-2 text-muted-foreground text-xs">
                              {new Date(inv.period_start * 1000).toLocaleDateString()} – {new Date(inv.period_end * 1000).toLocaleDateString()}
                            </td>
                            <td className="px-4 py-2">
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
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ─── Tab 3: LinkedIn & Execution ─── */}
        <TabsContent value="linkedin" className="mt-4">
          {profiles.length === 0 ? (
            <p className="text-sm text-muted-foreground">No LinkedIn profiles.</p>
          ) : (
            <div className="space-y-4">
              {profiles.map(p => {
                const profileTasks = tasks.filter(t => t.linkedin_profile_id === p.id)
                return (
                  <Card key={p.id}>
                    <CardContent className="pt-4 space-y-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{p.username ?? p.display_name ?? p.id}</span>
                        <Badge variant="outline" className={p.execution_mode === 'cloud' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' : 'bg-blue-500/10 text-blue-400 border-blue-500/30'}>
                          {p.execution_mode === 'cloud' ? 'Cloud' : 'Desktop'}
                        </Badge>
                        <Badge variant="outline" className={p.daemon_status === 'online' ? STATUS_COLORS.active : STATUS_COLORS.inactive}>
                          {p.daemon_status}
                        </Badge>
                        {p.requires_verification && (
                          <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/30">
                            Needs {p.verification_type ?? 'verification'}
                          </Badge>
                        )}
                        {!p.is_logged_in && (
                          <Badge variant="outline" className={STATUS_COLORS.inactive}>Logged out</Badge>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
                        <Field label="Daemon IP">{p.daemon_ip ?? '—'}</Field>
                        <Field label="Platform">{p.daemon_platform ?? '—'}</Field>
                        <Field label="Browser">{p.daemon_browser ?? '—'}</Field>
                        <Field label="Version">{p.daemon_version ?? '—'}</Field>
                        <Field label="Last heartbeat">{timeAgo(p.last_heartbeat)}</Field>
                        <Field label="Connect limit / day">{p.connect_daily_limit}</Field>
                        <Field label="Follow-up limit / day">{p.follow_up_daily_limit}</Field>
                        <Field label="Proxy">{p.proxy_server ?? '—'}</Field>
                        <Field label="Created">{fmt(p.created_at)}</Field>
                      </div>
                      {profileTasks.length > 0 && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-2">Recent tasks</p>
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="border-b">
                                  <th className="text-left px-2 py-1 text-muted-foreground font-medium">Type</th>
                                  <th className="text-left px-2 py-1 text-muted-foreground font-medium">Status</th>
                                  <th className="text-left px-2 py-1 text-muted-foreground font-medium">Scheduled</th>
                                  <th className="text-left px-2 py-1 text-muted-foreground font-medium">Error</th>
                                </tr>
                              </thead>
                              <tbody>
                                {profileTasks.slice(0, 5).map(t => (
                                  <tr key={t.id} className="border-b last:border-0">
                                    <td className="px-2 py-1">{t.task_type}</td>
                                    <td className="px-2 py-1">
                                      <Badge variant="outline" className={`text-xs ${TASK_STATUS_COLORS[t.status] ?? ''}`}>{t.status}</Badge>
                                    </td>
                                    <td className="px-2 py-1 text-muted-foreground">{timeAgo(t.scheduled_at)}</td>
                                    <td className="px-2 py-1 text-muted-foreground truncate max-w-xs">{t.last_error ?? '—'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}
        </TabsContent>

        {/* ─── Tab 4: Campaigns ─── */}
        <TabsContent value="campaigns" className="mt-4">
          {campaigns.length === 0 ? (
            <p className="text-sm text-muted-foreground">No campaigns.</p>
          ) : (
            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left px-4 py-3 text-muted-foreground font-medium">Name</th>
                      <th className="text-left px-4 py-3 text-muted-foreground font-medium">Status</th>
                      <th className="text-left px-4 py-3 text-muted-foreground font-medium">Leads</th>
                      <th className="text-left px-4 py-3 text-muted-foreground font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {campaigns.map(c => (
                      <tr key={c.id} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                        <td className="px-4 py-3">
                          <Link href={`/campaigns/${c.id}`} className="hover:underline font-medium flex items-center gap-1">
                            {c.name}
                            <ExternalLink className="h-3 w-3 text-muted-foreground" />
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline" className={c.is_paused ? STATUS_COLORS.inactive : STATUS_COLORS.active}>
                            {c.is_paused ? 'Paused' : 'Active'}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{c.leads_count}</td>
                        <td className="px-4 py-3 text-muted-foreground">{timeAgo(c.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ─── Tab 5: Activity ─── */}
        <TabsContent value="activity" className="mt-4 space-y-6">
          {/* Action logs */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent action logs</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {actionLogs.length === 0 ? (
                <p className="p-4 text-sm text-muted-foreground">No action logs.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Action</th>
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Status</th>
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Campaign</th>
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Duration</th>
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {actionLogs.slice(0, 50).map(log => (
                        <tr key={log.id} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                          <td className="px-4 py-2 font-medium">{log.action_type}</td>
                          <td className="px-4 py-2">
                            <Badge variant="outline" className={`text-xs ${log.status === 'completed' ? STATUS_COLORS.active : STATUS_COLORS.inactive}`}>
                              {log.status}
                            </Badge>
                          </td>
                          <td className="px-4 py-2 text-muted-foreground text-xs font-mono">{log.campaign_id?.slice(0, 8) ?? '—'}</td>
                          <td className="px-4 py-2 text-muted-foreground">{log.duration_ms != null ? `${log.duration_ms}ms` : '—'}</td>
                          <td className="px-4 py-2 text-muted-foreground">{timeAgo(log.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Tasks */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent tasks</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {tasks.length === 0 ? (
                <p className="p-4 text-sm text-muted-foreground">No tasks.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Type</th>
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Status</th>
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Scheduled</th>
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Completed</th>
                        <th className="text-left px-4 py-2 text-muted-foreground font-medium">Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tasks.slice(0, 20).map(t => (
                        <tr key={t.id} className="border-b last:border-0 hover:bg-accent/50 transition-colors">
                          <td className="px-4 py-2 font-medium">{t.task_type}</td>
                          <td className="px-4 py-2">
                            <Badge variant="outline" className={`text-xs ${TASK_STATUS_COLORS[t.status] ?? ''}`}>{t.status}</Badge>
                          </td>
                          <td className="px-4 py-2 text-muted-foreground">{timeAgo(t.scheduled_at)}</td>
                          <td className="px-4 py-2 text-muted-foreground">{timeAgo(t.completed_at)}</td>
                          <td className="px-4 py-2 text-muted-foreground text-xs truncate max-w-xs">{t.last_error ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Tab 6: Audit Trail ─── */}
        <TabsContent value="audit" className="mt-4">
          {auditLogs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No audit entries for this user.</p>
          ) : (
            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left px-4 py-3 text-muted-foreground font-medium">Time</th>
                      <th className="text-left px-4 py-3 text-muted-foreground font-medium">Admin</th>
                      <th className="text-left px-4 py-3 text-muted-foreground font-medium">Action</th>
                      <th className="text-left px-4 py-3 text-muted-foreground font-medium">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map(log => (
                      <AuditLogRow key={log.id} log={log} />
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* ─── Dialogs ─── */}

      {/* Delete */}
      <AlertDialog open={deleteDialog} onOpenChange={setDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete user?</AlertDialogTitle>
            <AlertDialogDescription>
              This soft-deletes <strong>{user.email}</strong> and schedules a data wipe in 30 days.
              You can restore the account before the wipe date.
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

      {/* Impersonate */}
      <AlertDialog open={impersonateDialog} onOpenChange={setImpersonateDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Impersonate user?</AlertDialogTitle>
            <AlertDialogDescription>
              A short-lived 15-minute session token will be issued for <strong>{user.email}</strong>.
              This action is logged. A new tab will open with the impersonated session.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleImpersonate}>Impersonate</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Extend trial */}
      <Dialog open={extendTrialDialog} onOpenChange={setExtendTrialDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Extend trial</DialogTitle>
            <DialogDescription>
              Current trial ends: {fmt(user.trial_ends_at)}. Enter the number of days to add.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <Input
              type="number"
              min={1}
              max={365}
              value={extendDays}
              onChange={e => setExtendDays(e.target.value)}
              placeholder="Days"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExtendTrialDialog(false)}>Cancel</Button>
            <Button onClick={handleExtendTrial}>Extend</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel subscription */}
      <AlertDialog open={cancelSubDialog} onOpenChange={setCancelSubDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel subscription?</AlertDialogTitle>
            <AlertDialogDescription>
              This will immediately cancel the Stripe subscription for <strong>{user.email}</strong>.
              The user will lose access at the end of the current billing period.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
              onClick={handleCancelSubscription}
            >
              Cancel subscription
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function AuditLogRow({ log }: { log: AdminAuditLog }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = Object.keys(log.details).length > 0

  return (
    <>
      <tr className="border-b last:border-0 hover:bg-accent/50 transition-colors">
        <td className="px-4 py-3 text-muted-foreground whitespace-nowrap" title={log.created_at}>
          {new Date(log.created_at).toLocaleString()}
        </td>
        <td className="px-4 py-3">
          <Link href={`/admin/users/${log.admin_user_id}`} className="hover:underline font-mono text-xs">
            {log.admin_user_id.slice(0, 8)}…
          </Link>
        </td>
        <td className="px-4 py-3">
          <Badge variant="outline" className="text-xs bg-zinc-500/10 text-zinc-300 border-zinc-600">{log.action}</Badge>
        </td>
        <td className="px-4 py-3">
          {hasDetails ? (
            <Button variant="ghost" size="sm" className="h-6 text-xs gap-1" onClick={() => setExpanded(e => !e)}>
              {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Details
            </Button>
          ) : '—'}
        </td>
      </tr>
      {expanded && hasDetails && (
        <tr className="border-b last:border-0 bg-muted/30">
          <td colSpan={4} className="px-4 py-2">
            <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  )
}
