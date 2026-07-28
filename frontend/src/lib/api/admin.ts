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

export interface AdminFinanceMetrics {
  total_users: number
  active_subscriptions: number
  trialing_users: number
  mrr: number
  arr: number
  trial_conversion_rate: number
  churn_rate: number
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
}
