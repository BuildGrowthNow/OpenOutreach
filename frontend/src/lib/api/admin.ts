'use client'

import { apiClient } from '@/lib/apiClientV2'

const strip = (path: string) => path.replace(/^\/api/, '')
const get = <T>(path: string, params?: Record<string, string | undefined>) => {
  const base = strip(path)
  if (params) {
    const clean = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    ) as Record<string, string>
    const qs = new URLSearchParams(clean).toString()
    return apiClient.get<T>(qs ? `${base}?${qs}` : base)
  }
  return apiClient.get<T>(base)
}
const post = <T>(path: string, data?: unknown) => apiClient.post<T>(strip(path), data)
const patch = <T>(path: string, data?: unknown) => apiClient.patch<T>(strip(path), data)
const del = <T>(path: string) => apiClient.delete<T>(strip(path))

// ──────────────────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────────────────

export interface AdminUserDetail {
  id: string
  email: string
  full_name: string
  created_at: string
  updated_at: string
  last_login: string | null
  last_login_ip: string | null
  signup_ip: string | null
  status: string
  plan: string
  subscription_status: string
  billing_period: string | null
  trial_ends_at: string | null
  current_period_end: string | null
  linkedin_account_limit: number
  whatsapp_account_limit: number
  campaign_limit: number | null
  cloud_profiles: number
  is_admin: boolean
  admin_role: string | null
  admin_notes: string | null
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  referral_code: string | null
  referrer_id: string | null
  referral_credits_earned: number
  email_verified: boolean
  is_deleted: boolean
  deleted_at: string | null
}

export interface AdminUserListItem {
  id: string
  email: string
  full_name: string
  created_at: string
  signup_date: string
  last_login: string | null
  status: string
  plan: string
  subscription_status: string
  linkedin_profiles_count: number
  campaigns_count: number
}

export interface AdminUsersListResponse {
  total: number
  skip: number
  limit: number
  users: AdminUserListItem[]
}

export interface AdminLinkedInProfile {
  id: string
  username: string | null
  display_name: string | null
  is_active: boolean
  created_at: string
  execution_mode: string
  daemon_status: string
  daemon_last_seen: string | null
  daemon_version: string | null
  daemon_platform: string | null
  daemon_browser: string | null
  daemon_ip: string | null
  last_heartbeat: string | null
  is_logged_in: boolean
  requires_verification: boolean
  verification_type: string | null
  connect_daily_limit: number
  follow_up_daily_limit: number
  proxy_server: string | null
}

export interface AdminCampaign {
  id: string
  name: string
  is_paused: boolean
  created_at: string
  leads_count: number
}

export interface AdminTask {
  id: string
  task_type: string
  status: string
  scheduled_at: string
  started_at: string | null
  completed_at: string | null
  campaign_id: string | null
  linkedin_profile_id: string | null
  last_error: string | null
}

export interface AdminActionLog {
  id: string
  action_type: string
  campaign_id: string | null
  linkedin_profile_id: string | null
  status: string
  error_message: string | null
  duration_ms: number | null
  created_at: string
}

export interface AdminAuditLog {
  id: string
  admin_user_id: string
  action: string
  target_user_id: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface AdminAuditLogsResponse {
  total: number
  skip: number
  limit: number
  logs: AdminAuditLog[]
}

export interface RevenuePlanItem {
  plan: string
  display_name: string
  count: number
  mrr: number
}

export interface FunnelMetrics {
  total_signups: number
  email_verified: number
  trial_started: number
  converted: number
  churned: number
}

export interface AdminFinanceMetrics {
  total_users: number
  active_subscriptions: number
  trialing_users: number
  mrr: number
  arr: number
  trial_conversion_rate: number
  churn_rate: number
  revenue_by_plan: RevenuePlanItem[]
  funnel: FunnelMetrics
}

export interface DaemonListItem {
  profile_id: string
  username: string | null
  execution_mode: string
  daemon_status: string
  daemon_ip: string | null
  daemon_platform: string | null
  daemon_browser: string | null
  daemon_version: string | null
  last_heartbeat: string | null
  user_id: string | null
  user_email: string | null
}

export interface DaemonsListResponse {
  daemons: DaemonListItem[]
  total: number
}

export interface AdminInvoice {
  id: string
  user_id: string
  user_email: string
  amount: number
  status: string
  created: number
  period_start: number
  period_end: number
  pdf_url: string | null
}

export interface AdminInvoicesResponse {
  total: number
  skip: number
  limit: number
  invoices: AdminInvoice[]
}

export interface AdminPlatformMetrics {
  tasks: {
    running: number
    pending: number
    failed_24h: number
    completed_24h: number
  }
  daemons: {
    online: number
    desktop: number
    cloud: number
  }
  activity_24h: {
    connects: number
    follow_ups: number
  }
}

export interface AdminDashboardResponse {
  summary: {
    total_users: number
    active_users: number
    blocked_users: number
    new_signups_today: number
    active_subscriptions: number
    expired_trials_count: number
  }
  finance: {
    mrr: number
    arr: number
    trial_conversion_rate: number
    churn_rate: number
  }
}

export interface ImpersonateResponse {
  access_token: string
  expires_in: number
}

export interface SetPlanRequest {
  plan: string
  billing_period?: string
  linkedin_account_limit?: number
  whatsapp_account_limit?: number
  campaign_limit?: number
  cloud_profiles?: number
}

export interface UserUpdateRequest {
  status?: string
  plan?: string
  admin_role?: string
  notes?: string
  is_admin?: boolean
  full_name?: string
}

export interface AdminProxy {
  id: string
  provider: string
  label: string
  protocol: string
  host: string
  port: number
  username: string | null
  has_username: boolean
  has_password: boolean
  country: string
  subdivision: string | null
  city: string | null
  region_mode: string
  kind: string
  device_type: string
  status: string
  identity_id: string | null
  channel: string
  linkedin_profile_id: string | null
  whatsapp_profile_id: string | null
  assigned_user_id: string | null
  assigned_org_id: string | null
  assigned_at: string | null
  assigned_by: string | null
  ever_assigned: boolean
  last_assigned_profile_id: string | null
  last_assigned_whatsapp_profile_id: string | null
  last_assigned_user_id: string | null
  last_assigned_org_id: string | null
  massive_account_id: string | null
  massive_subuser: string | null
  traffic_limit_bytes: number | null
  used_bytes: number
  limit_reached: boolean
  last_tested_at: string | null
  last_test_ip: string | null
  last_test_country: string | null
  last_test_city: string | null
  last_test_latency_ms: number | null
  last_test_error_type: string | null
  country_mismatch: boolean | null
  last_error: string | null
  retired_at: string | null
  disabled_at: string | null
  rotated_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface AdminProxyListResponse {
  total: number
  skip: number
  limit: number
  proxies: AdminProxy[]
}

export interface AdminProxyStats {
  total: number
  status: Record<string, number>
  provider: Record<string, number>
  country: Record<string, number>
  cloud_profiles_total: number
  cloud_profiles_without_proxy: number
  cloud_whatsapp_profiles_total?: number
  cloud_whatsapp_profiles_without_proxy?: number
}

export interface AdminProxyImportResponse {
  created: number
  skipped: number
  failed: number
  errors: { line: number; error: string }[]
  proxies: AdminProxy[]
}

export interface AdminProxyPreviewRow {
  line: number
  label: string
  protocol: string
  host: string
  port: number
  username_masked: string
  has_username: boolean
  has_password: boolean
  country: string
  subdivision: string | null
  city: string | null
  kind: string
  provider: string
  region_mode: string
  device_type: string
}

export interface AdminProxyPreviewResponse {
  entries: number
  valid: number
  duplicates: number
  failed: number
  errors: { line: number; error: string }[]
  preview: AdminProxyPreviewRow[]
}

export interface AdminProxyTestResponse {
  success: boolean
  message: string
  ip?: string | null
  country?: string | null
  city?: string | null
  expected_country?: string | null
  country_match?: boolean | null
  status_code?: number | null
  latency_ms?: number | null
  error?: string
  error_type?: string | null
}

export interface AdminProxyBulkTestResponse {
  tested: number
  passed: number
  failed: number
  results: { proxy_id: string; success: boolean; error?: string }[]
}

export interface AdminProxyBulkResponse {
  action: string
  processed: number
  failed: number
  results: { proxy_id: string; ok: boolean; status?: string; error?: string }[]
}

export interface AdminProxyHealthCheck {
  id: string
  proxy_id: string
  checked_at: string | null
  success: boolean
  egress_ip: string | null
  egress_country: string | null
  egress_city: string | null
  expected_country: string | null
  country_match: boolean | null
  latency_ms: number | null
  error_type: string | null
  error: string | null
}

export interface AdminProxyAssignment {
  id: string
  proxy_id: string
  identity_id: string | null
  profile_id: string | null
  channel: string | null
  user_id: string | null
  org_id: string | null
  assigned_by: string | null
  assigned_at: string | null
  unassigned_at: string | null
  reason: string | null
}

export interface AdminProxyUsageEntry {
  proxy_id?: string
  profile_id?: string
  workspace_id?: string | null
  label?: string | null
  status?: string | null
  provider?: string | null
  channel?: string | null
  channels?: Record<string, number>
  bytes: number
  profile_ids?: string[]
  proxy_ids?: string[]
  workspace_ids?: string[]
}

export interface AdminProxyUsageResponse {
  total_bytes: number
  period_start: string | null
  period_end: string | null
  per_proxy: AdminProxyUsageEntry[]
  per_profile: AdminProxyUsageEntry[]
  per_workspace: AdminProxyUsageEntry[]
  per_channel: { channel: string; bytes: number; proxy_ids: string[]; profile_ids: string[] }[]
  per_workspace_channel?: AdminProxyUsageEntry[]
}

export interface AdminMassiveAlert {
  proxy_id: string
  profile_id: string | null
  whatsapp_profile_id?: string | null
  channel?: string | null
  org_id: string | null
  massive_account_id: string | null
  massive_subuser?: string | null
  status: string
  reasons: string[]
  last_error: string | null
}

export interface AdminSeatAlert {
  type: string
  org_id: string
  org_name?: string | null
  owner_user_id: string
  used: number
  limit: number
  linkedin: number
  whatsapp_only: number
  duo: number
}

export interface AdminMassiveStatus {
  configured: boolean
  parent_username_set: boolean
  proxy_password_set: boolean
  reporting_enabled: boolean
  reporting_key_set: boolean
  reporting_configured: boolean
  host: string
  port: number
  reseller?: {
    enabled: boolean
    configured: boolean
    parent_username_set: boolean
    api_key_set: boolean
    default_limit_bytes: number
    monthly_soft_limit_bytes: number
    monthly_hard_limit_bytes: number
  }
  pool_stats?: { enabled: boolean }
  alerts?: AdminMassiveAlert[]
  seat_alerts?: AdminSeatAlert[]
}

export interface AdminMassiveSubaccount {
  proxy_id: string
  massive_account_id: string
  massive_subuser: string | null
  massive_status: string
  channel?: string | null
  profile_id: string | null
  linkedin_username: string | null
  whatsapp_profile_id?: string | null
  whatsapp_number?: string | null
  org_id: string | null
  assigned_user_id: string | null
  used_bytes: number
  limit_bytes: number | null
  limit_reached: boolean
  proxy_access: boolean | null
  country: string
  last_sync_at: string | null
  last_error: string | null
}

export interface AdminMassiveParentUsage {
  accounts: number
  used_bytes: number
  limit_bytes: number
  limit_reached: number
  proxy_access_revoked: number
}

export interface AdminMassiveAccountsResponse {
  configured: boolean
  accounts: AdminMassiveSubaccount[]
  parent_usage?: AdminMassiveParentUsage
}

export interface AdminMassiveSyncResponse {
  accounts: number
  matched: number
  updated: number
  unmatched: number
  parent?: {
    accounts: number
    used_bytes: number
    limit_bytes: number
    limit_reached: number
    proxy_access_revoked: number
  }
  budget?: { disabled: number; re_enabled: number; soft_alerts: number }
  reporting?: {
    group_by: string
    matched: number
    skipped: number
    total_bytes: number
  }
}

export interface AdminPoolStatsResponse {
  configured: boolean
  warnings: string[]
  country_counts: Record<string, number>
  min_nodes?: number
}

export interface AdminCloudProfile {
  id: string
  username: string | null
  user_id: string | null
  email: string
  identity_id: string | null
  org_id: string | null
  proxy_id: string | null
  proxy_mode: string
  has_proxy: boolean
  is_active: boolean
}

export interface AdminWhatsAppProfile {
  id: string
  phone_number: string | null
  display_name: string | null
  user_id: string | null
  email: string
  identity_id: string | null
  org_id: string | null
  cloud_mode: string | null
  proxy_id: string | null
  proxy_mode: string
  is_active: boolean
}

export interface AdminProxyFilters {
  status?: string
  country?: string
  provider?: string
  kind?: string
  channel?: string
  assignment?: string
  identity_id?: string
  org_id?: string
  search?: string
  skip?: number
  limit?: number
}

// ──────────────────────────────────────────────────────────────────────────────
// API functions
// ──────────────────────────────────────────────────────────────────────────────

export const adminApi = {
  getDashboard: () =>
    get<AdminDashboardResponse>('/api/admin/dashboard'),

  getUsers: (params: {
    status?: string
    plan?: string
    search?: string
    subscription_status?: string
    skip?: number
    limit?: number
  }) =>
    get<AdminUsersListResponse>('/api/admin/users', {
      status: params.status,
      plan: params.plan,
      search: params.search,
      subscription_status: params.subscription_status,
      skip: params.skip?.toString(),
      limit: params.limit?.toString(),
    }),

  getUser: (userId: string) =>
    get<AdminUserDetail>(`/api/admin/users/${userId}`),

  updateUser: (userId: string, body: UserUpdateRequest) =>
    patch<AdminUserDetail>(`/api/admin/users/${userId}`, body),

  setPlan: (userId: string, body: SetPlanRequest) =>
    post<AdminUserDetail>(`/api/admin/users/${userId}/set-plan`, body),

  getProxies: (params: AdminProxyFilters) =>
    get<AdminProxyListResponse>('/api/admin/proxies', {
      status: params.status,
      country: params.country,
      provider: params.provider,
      kind: params.kind,
      channel: params.channel,
      assignment: params.assignment,
      identity_id: params.identity_id,
      org_id: params.org_id,
      search: params.search,
      skip: params.skip?.toString(),
      limit: params.limit?.toString(),
    }),

  getProxyStats: () => get<AdminProxyStats>('/api/admin/proxies/stats'),

  parseProxies: (body: {
    text: string
    provider?: string
    kind?: string
    default_country?: string
  }) => post<AdminProxyPreviewResponse>('/api/admin/proxies/parse', body),

  importProxies: (body: {
    text: string
    provider?: string
    kind?: string
    default_country?: string
  }) => post<AdminProxyImportResponse>('/api/admin/proxies/import', body),

  exportProxies: (params: AdminProxyFilters) =>
    get<string>('/api/admin/proxies/export', {
      status: params.status,
      country: params.country,
      provider: params.provider,
      kind: params.kind,
      channel: params.channel,
      assignment: params.assignment,
      identity_id: params.identity_id,
      org_id: params.org_id,
      search: params.search,
    }),

  getCloudProfiles: (params: { search?: string; limit?: number }) =>
    get<{ profiles: AdminCloudProfile[] }>('/api/admin/proxies/cloud-profiles', {
      search: params.search,
      limit: params.limit?.toString(),
    }),

  getWhatsAppProfiles: (params: { search?: string; limit?: number }) =>
    get<{ profiles: AdminWhatsAppProfile[] }>('/api/admin/proxies/whatsapp-profiles', {
      search: params.search,
      limit: params.limit?.toString(),
    }),

  getProxyAssignments: (params: {
    active?: boolean
    proxy_id?: string
    profile_id?: string
    skip?: number
    limit?: number
  }) =>
    get<{ total: number; skip: number; limit: number; assignments: AdminProxyAssignment[] }>(
      '/api/admin/proxies/assignments',
      {
        active: params.active === undefined ? undefined : String(params.active),
        proxy_id: params.proxy_id,
        profile_id: params.profile_id,
        skip: params.skip?.toString(),
        limit: params.limit?.toString(),
      }
    ),

  getProxyHealth: (params: {
    proxy_id?: string
    only_failures?: boolean
    only_mismatch?: boolean
    skip?: number
    limit?: number
  }) =>
    get<{ total: number; skip: number; limit: number; checks: AdminProxyHealthCheck[] }>(
      '/api/admin/proxies/health',
      {
        proxy_id: params.proxy_id,
        only_failures: params.only_failures === undefined ? undefined : String(params.only_failures),
        only_mismatch: params.only_mismatch === undefined ? undefined : String(params.only_mismatch),
        skip: params.skip?.toString(),
        limit: params.limit?.toString(),
      }
    ),

  getProxyUsage: (params: { period_start?: string; period_end?: string; limit?: number }) =>
    get<AdminProxyUsageResponse>('/api/admin/proxies/usage', {
      period_start: params.period_start,
      period_end: params.period_end,
      limit: params.limit?.toString(),
    }),

  getMassiveStatus: () => get<AdminMassiveStatus>('/api/admin/proxies/massive/status'),

  syncMassiveUsage: (body: { from_date?: string; to_date?: string }) =>
    post<{ matched: number; skipped: number; total_bytes: number }>(
      '/api/admin/proxies/sync-massive',
      body
    ),

  getMassiveAccounts: () =>
    get<AdminMassiveAccountsResponse>('/api/admin/proxies/massive/accounts'),

  getMassiveAlerts: () =>
    get<{ alerts: AdminMassiveAlert[] }>('/api/admin/proxies/massive/alerts'),

  syncMassiveReseller: (body: { from_date?: string; to_date?: string }) =>
    post<AdminMassiveSyncResponse>('/api/admin/proxies/massive/sync', body),

  provisionMassiveSubaccount: (profileId: string, channel: 'linkedin' | 'whatsapp' = 'linkedin') =>
    post<{ proxy: AdminProxy; profile_id: string; channel: string }>(
      '/api/admin/proxies/massive/provision',
      { profile_id: profileId, channel }
    ),

  disableMassiveSubaccount: (proxyId: string) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/massive/${proxyId}/disable`),

  enableMassiveSubaccount: (proxyId: string) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/massive/${proxyId}/enable`),

  rotateMassiveSubaccount: (proxyId: string) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/massive/${proxyId}/rotate`),

  allocateMassiveTraffic: (proxyId: string, bytes: number) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/massive/${proxyId}/allocate`, {
      bytes,
    }),

  getPoolStats: (country?: string) =>
    get<AdminPoolStatsResponse>('/api/admin/proxies/pool-stats', { country }),

  bulkTestProxies: (body: {
    proxy_ids?: string[]
    all?: boolean
    provider?: string
    country?: string
    status?: string
    assignment?: string
    identity_id?: string
    org_id?: string
    kind?: string
    search?: string
  }) =>
    post<AdminProxyBulkTestResponse>('/api/admin/proxies/test', {
      action: 'test',
      ...body,
    }),

  bulkProxyAction: (body: {
    action: 'unassign' | 'enable' | 'disable' | 'retire'
    proxy_ids?: string[]
    all?: boolean
    provider?: string
    country?: string
    status?: string
    assignment?: string
    identity_id?: string
    org_id?: string
    kind?: string
    search?: string
  }) => post<AdminProxyBulkResponse>('/api/admin/proxies/bulk', body),

  testProxy: (proxyId: string) =>
    post<AdminProxyTestResponse>(`/api/admin/proxies/${proxyId}/test`),

  assignProxy: (proxyId: string, profileId: string, channel: 'linkedin' | 'whatsapp' = 'linkedin') =>
    post<{ proxy: AdminProxy; profile_id: string; channel: string }>(
      `/api/admin/proxies/${proxyId}/assign`,
      { profile_id: profileId, channel }
    ),

  unassignProxy: (proxyId: string, reason?: string) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/${proxyId}/unassign`, { reason }),

  disableProxy: (proxyId: string) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/${proxyId}/disable`),

  enableProxy: (proxyId: string) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/${proxyId}/enable`),

  retireProxy: (proxyId: string) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/${proxyId}/retire`),

  rotateProxy: (proxyId: string, password: string) =>
    post<{ proxy: AdminProxy }>(`/api/admin/proxies/${proxyId}/rotate`, { password }),

  provisionFallbackProxy: (profileId: string) =>
    post<{ proxy: AdminProxy; profile_id: string }>(
      '/api/admin/proxies/provision-fallback',
      { profile_id: profileId }
    ),

  extendTrial: (userId: string, days: number) =>
    post<{ ok: boolean; trial_ends_at: string }>(`/api/admin/users/${userId}/extend-trial`, { days }),

  cancelSubscription: (userId: string) =>
    post<{ ok: boolean }>(`/api/admin/users/${userId}/cancel-subscription`),

  deleteUser: (userId: string) =>
    del<{ ok: boolean; deletion_scheduled_at: string }>(`/api/admin/users/${userId}`),

  restoreUser: (userId: string) =>
    post<{ ok: boolean }>(`/api/admin/users/${userId}/restore`),

  verifyEmail: (userId: string) =>
    post<{ ok: boolean }>(`/api/admin/users/${userId}/verify-email`),

  sendPasswordReset: (userId: string) =>
    post<{ ok: boolean }>(`/api/admin/users/${userId}/send-password-reset`),

  impersonate: (userId: string) =>
    post<ImpersonateResponse>(`/api/admin/users/${userId}/impersonate`),

  getUserLinkedInProfiles: (userId: string) =>
    get<{ profiles: AdminLinkedInProfile[] }>(`/api/admin/users/${userId}/linkedin-profiles`),

  getUserCampaigns: (userId: string) =>
    get<{ campaigns: AdminCampaign[] }>(`/api/admin/users/${userId}/campaigns`),

  getUserTasks: (userId: string, status?: string) =>
    get<{ tasks: AdminTask[] }>(`/api/admin/users/${userId}/tasks`, { status }),

  getUserActionLogs: (userId: string) =>
    get<{ logs: AdminActionLog[] }>(`/api/admin/users/${userId}/action-logs`),

  getUserNotes: (userId: string) =>
    get<{ notes: string | null }>(`/api/admin/users/${userId}/notes`),

  updateUserNotes: (userId: string, notes: string | null) =>
    post<{ ok: boolean }>(`/api/admin/users/${userId}/notes`, { notes }),

  getFinanceMetrics: () =>
    get<AdminFinanceMetrics>('/api/admin/finance'),

  getInvoices: (skip = 0, limit = 50, userId?: string) =>
    get<AdminInvoicesResponse>('/api/admin/finance/invoices', {
      skip: skip.toString(),
      limit: limit.toString(),
      user_id: userId,
    }),

  getAuditLogs: (params: {
    admin_user_id?: string
    target_user_id?: string
    action?: string
    skip?: number
    limit?: number
  }) =>
    get<AdminAuditLogsResponse>('/api/admin/audit-logs', {
      admin_user_id: params.admin_user_id,
      target_user_id: params.target_user_id,
      action: params.action,
      skip: params.skip?.toString(),
      limit: params.limit?.toString(),
    }),

  getPlatformMetrics: () =>
    get<AdminPlatformMetrics>('/api/admin/platform'),

  getDaemons: (params?: { status?: string; execution_mode?: string }) =>
    get<DaemonsListResponse>('/api/admin/platform/daemons', params),

  getOrganizations: (params?: { search?: string; skip?: number; limit?: number }) =>
    get<AdminOrganizationsListResponse>('/api/admin/organizations', {
      search: params?.search,
      skip: params?.skip?.toString(),
      limit: params?.limit?.toString(),
    }),

  getOrganization: (orgId: string) =>
    get<AdminOrganizationDetail>(`/api/admin/organizations/${orgId}`),

  overrideOrganizationSeats: (
    orgId: string,
    data: { cloud_seats: number; reason: string; plan?: string }
  ) => patch<AdminOrganizationSummary>(`/api/admin/organizations/${orgId}/seats`, data),
}

export interface AdminOrganizationSummary {
  id: string
  name: string
  owner_user_id: string
  owner_email: string | null
  plan: string
  status: string
  is_personal: boolean
  seat_override: boolean
  cloud_seats: number
  cloud_seats_used: number
  linkedin_account_limit: number
  whatsapp_account_limit: number
  members_count: number
  credentialed_profiles: number
  assigned_profiles: number
  whatsapp_cloud_profiles: number
  whatsapp_only_seats: number
  duo_seats: number
  linkedin_seats: number
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  created_at: string | null
  updated_at: string | null
}

export interface AdminOrganizationMember {
  user_id: string
  email: string
  full_name: string | null
  role: string
  status: string
  joined_at: string | null
}

export interface AdminOrganizationProfile {
  id: string
  linkedin_username: string | null
  phone_number?: string | null
  display_name?: string | null
  channel?: string | null
  cloud_mode?: string | null
  execution_mode: string | null
  assigned_user_id: string | null
  active: boolean
  proxy_assigned: boolean
  proxy_mode: string | null
}

export interface AdminOrganizationProxy {
  id: string
  provider: string | null
  status: string | null
  channel?: string | null
  country: string | null
  subdivision: string | null
  city: string | null
  profile_id: string | null
  whatsapp_profile_id?: string | null
  assigned_user_id: string | null
  massive_status: string | null
  massive_used_bytes: number
  massive_limit_bytes: number | null
  massive_limit_reached: boolean
  proxy_access: boolean | null
  last_test_country: string | null
  country_mismatch: boolean | null
}

export interface AdminOrganizationUsage {
  total_bytes: number
  per_channel: Record<string, number>
  per_workspace_channel?: Record<string, Record<string, number>>
  seats?: Record<string, unknown>
  seat_alerts?: AdminSeatAlert[]
  proxies: number
  limit_reached: number
  access_revoked: number
  country_mismatch: number
}

export interface AdminOrganizationDetail {
  organization: AdminOrganizationSummary
  members: AdminOrganizationMember[]
  profiles: AdminOrganizationProfile[]
  proxies?: AdminOrganizationProxy[]
  usage?: AdminOrganizationUsage
  audit_events: Array<{
    id: string
    event: string
    actor_user_id: string | null
    target_user_id: string | null
    target_email: string | null
    metadata: Record<string, unknown>
    created_at: string | null
  }>
}

export interface AdminOrganizationsListResponse {
  total: number
  skip: number
  limit: number
  organizations: AdminOrganizationSummary[]
}
