"use client";

import { ApiResponse } from "../api";
import { apiClient } from "../apiClientV2";
import { normalizeState, normalizeOutcome } from "../utils/normalize-state";

// Strip leading /api prefix since apiClient already prepends /api
const stripApi = (path: string) => path.replace(/^\/api/, '');
const get = <T>(path: string, params?: Record<string, string>) => {
  const base = stripApi(path);
  const url = params && Object.keys(params).length
    ? `${base}?${new URLSearchParams(params).toString()}`
    : base;
  return apiClient.get<T>(url);
};
const post = <T>(path: string, data?: unknown) => apiClient.post<T>(stripApi(path), data);
const patch = <T>(path: string, data?: unknown) => apiClient.patch<T>(stripApi(path), data);
const del = <T>(path: string) => apiClient.delete<T>(stripApi(path));

// JWT Authentication API
export interface JwtTokens {
  access: string;
  refresh: string;
  user: {
    id: number;
    email?: string;
    username?: string;
    is_staff?: boolean;
    is_superuser?: boolean;
  };
}

export interface AuthStatus {
  status: "authenticated" | "anonymous";
  message: string;
  user?: {
    id: number;
    username: string;
    email?: string;
    is_authenticated: boolean;
    is_staff?: boolean;
    is_superuser?: boolean;
    last_login?: string;
    date_joined?: string;
  };
}

// JWT Authentication API Functions
export async function login(password: string): Promise<ApiResponse<JwtTokens>> {
  return post("/api/auth/login", { password });
}

export async function refreshAccessToken(
  refreshToken: string,
): Promise<ApiResponse<{ access: string }>> {
  return post("/api/auth/refresh", { refresh: refreshToken });
}

export async function verifyToken(
  accessToken: string,
): Promise<ApiResponse<{ valid: boolean }>> {
  return post("/api/auth/verify", { token: accessToken });
}

export async function getAuthStatus(): Promise<ApiResponse<AuthStatus>> {
  return get("/api/auth/status");
}

export async function logout(): Promise<
  ApiResponse<{ status: string; message: string }>
> {
  return del("/api/auth/logout");
}

export async function requestPasswordReset(
  email: string,
): Promise<ApiResponse<{ status: string; message: string }>> {
  return post("/api/auth/password-reset/request", { email });
}

export async function confirmPasswordReset(
  token: string,
  password: string,
): Promise<ApiResponse<{ status: string; message: string }>> {
  return post("/api/auth/password-reset/confirm", { token, password });
}

export async function updatePassword(
  currentPassword: string,
  newPassword: string,
): Promise<ApiResponse<{ status: string; message: string }>> {
  return post("/api/auth/update-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
import {
  Campaign,
  Lead,
  Message,
  HealthStatus,
  Pagination,
  LinkMetrics,
  LinkedInProfileHealthResponse,
} from "@/lib/types/components";

// Re-export types for convenience
export type {
  Campaign,
  Lead,
  Message,
  HealthStatus,
  Pagination,
  LinkMetrics,
  LinkedInProfileHealthResponse,
};

// Campaign API
export async function getCampaigns(
  status?: string,
  page?: number,
  limit?: number,
): Promise<ApiResponse<{ data: Campaign[]; pagination: Pagination }>> {
  const params: Record<string, string> = {};
  if (status) params.status = status;
  if (page) params.page = page.toString();
  if (limit) params.limit = limit.toString();
  return get("/api/campaigns", params);
}

export async function getCampaign(id: string): Promise<ApiResponse<Campaign>> {
  return get(`/api/campaigns/${id}`);
}

// Ghost Mode API
export interface GhostSimulationLog {
  id: number;
  action_type: string;
  target_name: string;
  target_url: string;
  result_data: Record<string, unknown>;
  rating: number | null;
  score: number | null;
  started_at: string;
  completed_at: string;
  simulated_action: Record<string, unknown>;
}

export interface GhostSimulationResponse {
  success: boolean;
  campaign_id: number;
  total: number;
  simulations: GhostSimulationLog[];
}

export async function getGhostModeSimulations(
  campaignId: string,
): Promise<ApiResponse<GhostSimulationResponse>> {
  return get(`/api/campaigns/${campaignId}/ghost-mode/simulations`);
}

export async function startGhostMode(campaignId: string): Promise<
  ApiResponse<{
    success: boolean;
    ghost_campaign_id: number;
    message: string;
    created: boolean;
  }>
> {
  return post(`/api/campaigns/${campaignId}/ghost-mode/action`, {
    action: "start",
  });
}

export async function stopGhostMode(campaignId: string): Promise<
  ApiResponse<{
    success: boolean;
    message: string;
  }>
> {
  return post(`/api/campaigns/${campaignId}/ghost-mode/action`, {
    action: "stop",
  });
}

// Targeted polling - only fetch campaign status for performance
export async function getCampaignStatus(
  id: string,
): Promise<ApiResponse<{ status: string; is_paused: boolean; nextActionAt: string | null }>> {
  return get(`/api/campaigns/${id}/status`);
}

export async function createCampaign(
  data: Partial<Campaign>,
): Promise<ApiResponse<Campaign>> {
  return post("/api/campaigns", data);
}

export async function updateCampaign(
  id: string,
  data: Partial<Campaign>,
): Promise<ApiResponse<Campaign>> {
  return patch(`/api/campaigns/${id}`, data);
}

export async function deleteCampaign(
  id: string,
): Promise<ApiResponse<{ success: boolean }>> {
  return del(`/api/campaigns/${id}`);
}

export async function clearCampaignErrors(
  id: string,
): Promise<ApiResponse<null>> {
  return del(`/api/campaigns/${id}/errors`);
}

export interface AnalyticsOverviewResponse {
  period: string;
  stats: {
    connectionsSent: number;
    connectionsAccepted: number;
    connectionAcceptRate: number;
    messagesSent: number;
    messagesReplied: number;
    responseRate: number;
    conversions: number;
    conversionRate: number;
    waConnectionsSent?: number;
    waMessagesSent?: number;
  };
  totals: {
    leads: number;
    qualified: number;
    readyToConnect: number;
    connected: number;
    pending: number;
    failed: number;
    noEmail: number;
    connectionAcceptRate: number;
    responseRate: number;
    conversionRate: number;
  };
  pipeline: {
    qualified: number;
    ready_to_connect: number;
    pending: number;
    connected: number;
    completed: number;
    failed: number;
    no_email: number;
  };
  campaigns: Campaign[];
}

export async function getAnalyticsOverview(
  campaignId?: string,
  period?: string,
): Promise<ApiResponse<AnalyticsOverviewResponse>> {
  const params: Record<string, string> = {};
  if (campaignId && campaignId !== "all") params.campaign_id = campaignId;
  if (period) params.period = period;
  return get("/api/analytics/overview", params);
}

// Campaign Analytics API
export interface CampaignAnalyticsResponse {
  period: string;
  campaign_id: string;
  stats: {
    connections_sent: number;
    connections_accepted: number;
    connection_accept_rate: number;
    messages_sent: number;
    messages_replied: number;
    responses: number;
    response_rate: number;
    conversions: number;
    conversion_rate: number;
    errors: number;
    rate_limit_warnings: number;
    daily_connections?: number;
    daily_messages?: number;
    last_7_days?: {
      connections_sent?: number;
      connections_accepted?: number;
    };
    last_30_days?: {
      connections_accepted?: number;
      conversions?: number;
    };
    connection_success_rate?: number;
    avg_time_to_accept?: string;
    total_connection_attempts?: number;
    failed_connections?: number;
    avg_response_time?: string;
    message_open_rate?: number;
    total_messages_sent?: number;
    positive_responses?: number;
    avg_conversion_time?: string;
    qualified_leads?: number;
    hot_leads?: number;
    deals_closed?: number;
    profile_views?: number;
    link_clicks?: number;
    document_downloads?: number;
    meeting_bookings?: number;
    responses_under_1h?: number;
    responses_1_24h?: number;
    responses_1_7d?: number;
    responses_over_7d?: number;
    peak_day?: string;
    peak_hour?: string;
    timezone_optimization?: string;
    high_quality_conversions?: number;
    medium_quality_conversions?: number;
    low_quality_conversions?: number;
    best_performing_source?: string;
    best_roi_source?: string;
    avg_cost_per_conversion?: number;
    best_performing_time?: string;
    best_performing_day?: string;
  };
  daily_breakdown: Array<{
    date: string;
    connections_sent: number;
    connections_accepted: number;
    messages_sent: number;
    messages_replied: number;
  }>;
  pipeline: {
    qualified: number;
    ready_to_connect: number;
    pending: number;
    connected: number;
    completed: number;
    failed: number;
    no_email: number;
  };
}

export async function getCampaignAnalytics(
  id: string,
  period?: string,
): Promise<ApiResponse<CampaignAnalyticsResponse>> {
  const params: Record<string, string> = {};
  if (period) params.period = period;
  return get(`/api/campaigns/${id}/analytics`, params);
}

// Campaign Leads API
export interface LeadFilters {
  status?: string;
  search?: string;
  total_count?: number;
}

export async function getCampaignLeads(
  id: string,
  status?: string,
  search?: string,
  page?: number,
  limit?: number,
): Promise<
  ApiResponse<{ data: Lead[]; pagination: Pagination; filters: LeadFilters; pipelineCounts: Record<string, number> }>
> {
  const params: Record<string, string> = {};
  if (status) params.status = status;
  if (search) params.search = search;
  const resolvedLimit = limit ?? 50;
  if (page && page > 1) params.offset = ((page - 1) * resolvedLimit).toString();
  if (limit) params.limit = limit.toString();

  // API returns { total, limit, offset, results: [{lead, deal}] }
  type RawLeadDeal = {
    lead: { id: string; public_identifier: string; url: string; full_name?: string; company?: string; headline?: string; location?: string; disqualified?: boolean; created_at?: string };
    deal: { id: string; lead_id: string; campaign_id: string; state: string; outcome?: string; reason?: string; creation_date?: string; last_outgoing_at?: string; next_follow_up_at?: string; unanswered_count?: number };
  };
  type RawResponse = { total: number; limit: number; offset: number; results: RawLeadDeal[]; pipelineCounts?: Record<string, number> };

  const raw = await get<RawResponse>(`/api/campaigns/${id}/leads`, params);

  if (!raw.data) {
    return raw as unknown as ApiResponse<{ data: Lead[]; pagination: Pagination; filters: LeadFilters; pipelineCounts: Record<string, number> }>;
  }

  const leads: Lead[] = (raw.data.results || []).map(({ lead, deal }) => {
    const headline = lead.headline || undefined;
    // Prefer structured company field; fall back to headline " at X" parse for legacy leads
    const company = lead.company || (() => {
      const atIdx = headline ? headline.toLowerCase().indexOf(' at ') : -1;
      return atIdx > -1 ? headline!.slice(atIdx + 4).trim() : undefined;
    })();

    return {
      id: lead.id,
      publicIdentifier: lead.public_identifier,
      linkedinUrl: lead.url,
      name: lead.full_name || undefined,
      title: headline,
      company,
      disqualified: lead.disqualified || false,
      state: (normalizeState(deal.state) || 'DISCOVERED') as Lead["state"],
      outcome: normalizeOutcome(deal.outcome) as Lead["outcome"] | undefined,
      creationDate: deal.creation_date || lead.created_at || new Date().toISOString(),
      updateDate: deal.creation_date || lead.created_at || new Date().toISOString(),
      lastOutgoingAt: deal.last_outgoing_at || undefined,
      nextFollowUpAt: deal.next_follow_up_at || undefined,
      unansweredCount: deal.unanswered_count ?? 0,
    };
  });

  return {
    ...raw,
    data: {
      data: leads,
      pagination: { page: Math.floor(raw.data.offset / raw.data.limit) + 1, limit: raw.data.limit, total: raw.data.total, total_pages: Math.ceil(raw.data.total / raw.data.limit) || 1 },
      filters: {},
      pipelineCounts: raw.data.pipelineCounts ?? {},
    },
  };
}

// Campaign Messages API
export async function getCampaignMessages(
  id: string,
  page?: number,
  limit?: number,
): Promise<ApiResponse<{ data: Message[]; pagination: Pagination }>> {
  const params: Record<string, string> = {};
  if (page) params.page = page.toString();
  if (limit) params.limit = limit.toString();
  return get(`/api/campaigns/${id}/messages`, params);
}

// Leads API
export async function getLeads(
  status?: string,
  search?: string,
  disqualified?: boolean,
  page?: number,
  limit?: number,
): Promise<ApiResponse<{ data: Lead[]; pagination: Pagination }>> {
  const params: Record<string, string> = {};
  if (status) params.state = status;
  if (search) params.search = search;
  if (disqualified !== undefined) params.disqualified = disqualified.toString();
  const resolvedLimit = limit ?? 20;
  params.limit = resolvedLimit.toString();
  if (page && page > 1) params.offset = ((page - 1) * resolvedLimit).toString();

  const response = await get<{ data: Lead[]; pagination: { total: number; page: number; limit: number; pages: number } }>("/api/leads", params);

  if (response.data?.data) {
    response.data.data = response.data.data.map((lead: Lead) => ({
      ...lead,
      state: normalizeState(lead.state as string) as Lead["state"],
      outcome: normalizeOutcome(lead.outcome as string) as Lead["outcome"],
    }));
  }

  // Remap backend `pages` → frontend `total_pages`
  if (response.data?.pagination) {
    (response.data.pagination as unknown as Pagination).total_pages = response.data.pagination.pages;
  }

  return response as ApiResponse<{ data: Lead[]; pagination: Pagination }>;
}

export async function getLead(id: string): Promise<ApiResponse<Lead>> {
  type RawLeadDetail = Lead & {
    contact_info?: { email?: string; phone_numbers?: string[] };
    api_email?: string;
  };
  const response = await get<RawLeadDetail>(`/api/leads/${id}`);

  if (response.data) {
    const raw = response.data;
    raw.state = normalizeState(raw.state as string) as Lead["state"];
    raw.outcome = normalizeOutcome(raw.outcome as string) as Lead["outcome"];
    // Map snake_case detail fields to camelCase Lead shape
    if (!raw.contactInfo && (raw.contact_info || raw.api_email)) {
      const ci = raw.contact_info || {};
      const apiEmail = raw.api_email || undefined;
      const overlayEmail = ci.email || undefined;
      raw.contactInfo = {
        email: apiEmail || overlayEmail,
        apiEmail,
        overlayEmail,
        phoneNumbers: ci.phone_numbers || [],
      };
    }
  }

  return response as unknown as ApiResponse<Lead>;
}

export async function updateLead(
  id: string,
  data: Partial<Lead>,
): Promise<ApiResponse<Lead>> {
  return patch(`/api/leads/${id}`, data);
}

export async function importCsvLeads(
  campaignId: string,
  csvText: string,
): Promise<{ added: number; skipped: number; errors: string[] }> {
  const { useAuthStore } = await import('../authStoreV2');
  const token = useAuthStore.getState().accessToken;
  const headers: Record<string, string> = {
    'Content-Type': 'text/csv',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  };
  const res = await fetch(`/api/campaigns/${campaignId}/import-csv`, {
    method: 'POST',
    headers,
    body: csvText,
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`Import failed: ${res.status}`);
  return res.json();
}

export async function exportLeads(campaignId?: string, state?: string): Promise<void> {
  const params: Record<string, string> = {};
  if (campaignId) params.campaign_id = campaignId;
  if (state) params.state = state;
  const qs = Object.keys(params).length ? `?${new URLSearchParams(params)}` : '';
  const { useAuthStore } = await import('../authStoreV2');
  const token = useAuthStore.getState().accessToken;
  const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {};
  const res = await fetch(`/api/leads/export${qs}`, { headers, credentials: 'include' });
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `leads-export-${campaignId || 'all'}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function addLeadToCampaign(
  id: string,
  campaignId: string,
): Promise<
  ApiResponse<{ success: boolean; dealId: number; created: boolean }>
> {
  return post(`/api/leads/${id}/add-to-campaign/`, { campaign_id: campaignId });
}

// Messages API
export async function getMessageStats(
  campaignId?: string,
): Promise<ApiResponse<{ totalSent: number; totalReceived: number; responseRate: number; activeCampaigns: number }>> {
  const params: Record<string, string> = {};
  if (campaignId && campaignId !== 'all') params.campaign_id = campaignId;
  return get('/api/messages/stats', params);
}

export async function getMessages(
  campaign_id?: string,
  deal_id?: string,
  lead_id?: string,
  page?: number,
  limit?: number,
): Promise<ApiResponse<{ data: Message[]; pagination: Pagination }>> {
  const params: Record<string, string> = {};
  if (page) params.page = page.toString();
  if (limit) params.limit = limit.toString();

  // Lead-scoped thread (GET /api/leads/{id}/messages)
  if (lead_id) {
    return get(`/api/leads/${lead_id}/messages`, params);
  }

  // Deal-scoped thread (GET /api/messages/deals/{id}/messages)
  if (deal_id) {
    return get(`/api/messages/deals/${deal_id}/messages`, params);
  }

  // Campaign-scoped list (GET /api/messages?campaign_id=...)
  if (campaign_id) {
    return get("/api/messages", { ...params, campaign_id });
  }

  // All accessible messages
  return get("/api/messages", params);
}

// Send message to lead
export async function sendMessageToLead(
  lead_id: string,
  content: string,
): Promise<ApiResponse<{ success: boolean; message: Message }>> {
  return post(`/api/leads/${lead_id}/messages`, { content, is_outgoing: true });
}

// Tracked Link API
export interface TrackedLink {
  id: string;
  campaign_id?: string;
  campaign?: {
    id: string;
    name: string;
  };
  original_url: string;
  short_code: string;
  is_active: boolean;
  total_clicks: number;
  unique_clicks?: number;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
  last_clicked_at?: string;
  created_at: string;
}

export interface LinkBreakdown {
  by_device?: {
    desktop?: number;
    mobile?: number;
    tablet?: number;
  };
  by_country?: Record<string, number>;
  by_source?: Record<string, number>;
  daily?: Array<{
    date?: string;
    clicks?: number;
  }>;
}

export interface LinkClick {
  id: string;
  ip_address: string;
  user_agent: string;
  referrer: string;
  clicked_at: string;
}

export async function getLinks(
  campaignId?: string,
): Promise<ApiResponse<{ data: TrackedLink[]; count: number }>> {
  const params: Record<string, string> = {};
  if (campaignId) params.campaign_id = campaignId;
  return get("/api/links", params);
}

export async function getLinkAnalytics(id: string): Promise<
  ApiResponse<{
    status: string;
    link: TrackedLink;
    breakdown: LinkBreakdown;
  }>
> {
  return get(`/api/links/${id}/analytics`);
}

export async function createLink(data: Partial<TrackedLink>): Promise<
  ApiResponse<{
    status: string;
    id: number;
    short_code: string;
    url: string;
  }>
> {
  return post("/api/links", data);
}

export async function updateLink(
  id: string,
  data: Partial<TrackedLink>,
): Promise<
  ApiResponse<{
    status: string;
    id: number;
    short_code: string;
    is_active: boolean;
  }>
> {
  return patch(`/api/links/${id}`, data);
}

export async function deleteLink(id: string): Promise<
  ApiResponse<{
    status: string;
    message: string;
  }>
> {
  return del(`/api/links/${id}`);
}

export async function getLinkClicks(linkId: string): Promise<
  ApiResponse<{
    data: LinkClick[];
    count: number;
  }>
> {
  return get(`/api/links/${linkId}/clicks`);
}

// Settings API
export interface Settings {
  llm: {
    provider: string;
    apiKey: string;
    model: string;
    apiBase: string;
    writingStyle: string;
    sayRules: string;
    avoidRules: string;
  };
  rateLimits: {
    dailyConnectionLimit: number;
    dailyFollowUpLimit: number;
    velocity: number;
    enableSmartRateLimiting: boolean;
    aggressivenessPreset: "very_slow" | "slow" | "average" | "aggressive" | "very_aggressive";
  };
  activeHours?: {
    enableActiveHours: boolean;
    activeStartHour: number;
    activeEndHour: number;
    activeTimezone: string;
    activeDays: string;
  };
  linkedinProfile: {
    username: string;
    campaign: string;
  };
  whatsapp?: {
    dailyLimit: number;
    enableActiveHours: boolean;
    activeStartHour: number;
    activeEndHour: number;
    activeDays: string;
  };
}

export async function getSettings(): Promise<ApiResponse<Settings>> {
  return get("/api/settings");
}

export async function updateSettings(
  data: Partial<{
    llm?: Partial<Settings["llm"]>;
    rateLimits?: Partial<Settings["rateLimits"]>;
    activeHours?: Partial<Settings["activeHours"]>;
    linkedinProfile?: Partial<Settings["linkedinProfile"]>;
    whatsapp?: Partial<NonNullable<Settings["whatsapp"]>>;
  }>,
): Promise<ApiResponse<Settings>> {
  return patch("/api/settings", data);
}

export async function getRateLimits(): Promise<
  ApiResponse<Settings["rateLimits"]>
> {
  return get("/api/settings/rate-limits");
}

export interface LinkedinProfileRateLimit {
  profile_id: number;
  profile_username: string;
  base_limit: number;
  effective_limit: number;
  remaining: number;
  use_multiplier: number;
  day_multiplier: number;
  detectability_score: number;
}

export interface DailyUsageResponse {
  daily_connections_sent: number;
  daily_messages_sent: number;
  daily_limit: number; // Base limit (for backward compatibility)
  effective_limit: number; // Context-aware effective limit
  remaining: number; // Total remaining across all profiles
  rate_limit_status: "normal" | "caution" | "warning" | "exceeded";
  warning_message?: string;
  warning_level?: "low" | "medium" | "high";
  last_reset: string;
  reset_frequency: string;
  linkedin_profiles: LinkedinProfileRateLimit[];
}

export async function getDailyUsage(): Promise<
  ApiResponse<DailyUsageResponse>
> {
  return get("/api/settings/daily-usage");
}

// Health API
export async function getHealthStatus(): Promise<ApiResponse<HealthStatus>> {
  return get("/api/health");
}

// State Machine API
export interface StateMachineNode {
  id: string;
  name: string;
  type: string;
  config?: Record<string, unknown>;
  x: number;
  y: number;
  description?: string;
}

export interface StateMachineTransition {
  id: string;
  source_node: string;
  target_node: string;
  label?: string;
  condition_type?: string;
}

export interface StateMachineResponse {
  id: string;
  campaign_id: string;
  name: string;
  description: string;
  is_active: boolean;
  is_valid: boolean;
  validation_errors: string[];
  nodes: StateMachineNode[];
  transitions: StateMachineTransition[];
}

export async function getStateMachine(
  campaignId: string,
): Promise<ApiResponse<StateMachineResponse>> {
  return get(`/api/campaigns/${campaignId}/state-machine`);
}

export async function updateStateMachine(
  campaignId: string,
  data: {
    name: string;
    description: string;
    graph_data: {
      nodes: StateMachineNode[];
      transitions: StateMachineTransition[];
    };
  },
): Promise<ApiResponse<StateMachineResponse>> {
  return post(`/api/campaigns/${campaignId}/state-machine`, data);
}

export async function validateStateMachine(
  campaignId: string,
  data: StateMachineResponse,
): Promise<
  ApiResponse<{
    is_valid: boolean;
    errors: string[];
    warnings: Array<{ type: string; message: string }>;
  }>
> {
  return post(
    `/api/campaigns/${campaignId}/state-machine/validate`,
    data as unknown as Record<string, unknown>,
  );
}

export interface SimulationResult {
  success: boolean;
  simulation: {
    path: Array<{
      node: string;
      name: string;
      type: string;
    }>;
    nodes_visited: number;
    transitions_used: number;
    final_status: string;
    messages_sent: string[];
    completed: boolean;
    steps: number;
    error: string | null;
  };
}

export async function simulateStateMachine(
  campaignId: string,
  dealId: string,
): Promise<ApiResponse<SimulationResult>> {
  return post("/api/state-machine/simulate", {
    campaign_id: campaignId,
    deal_id: dealId,
  });
}

export interface ExecutionResult {
  success: boolean;
  execution: {
    state_machine_id: number;
    current_node_id: number | null;
    current_node_name: string | null;
    status: string;
    steps_executed: number;
    logs: Array<{
      id: number;
      node_id: number | null;
      node_name: string | null;
      action: string;
      result: Record<string, unknown>;
      timestamp: string;
    }>;
    error: string | null;
  };
}

export async function executeStateMachine(
  campaignId: string,
  dealId: string,
): Promise<ApiResponse<ExecutionResult>> {
  return post("/api/state-machine/execute", {
    campaign_id: campaignId,
    deal_id: dealId,
  });
}

export interface SimulationInput {
  input: string;
  startState: string;
  maxSteps: number;
}

export async function simulateStateMachineExecution(
  campaignId: string,
  data: SimulationInput,
): Promise<
  ApiResponse<{
    success: boolean;
    simulation: {
      input: string;
      start_state: string;
      path: Array<{
        node: string;
        name: string;
        type: string;
        timestamp: string;
      }>;
      nodes_visited: number;
      transitions_used: number;
      final_state: string;
      messages_sent: string[];
      completed: boolean;
      steps: number;
      error: string | null;
    };
  }>
> {
  return post(
    `/api/campaigns/${campaignId}/state-machine/simulate`,
    data as unknown as Record<string, unknown>,
  );
}

// LinkedIn Credentials API - Internal representation (with sensitive data)
export interface LinkedInCredentialsInternal {
  id: number;
  username: string;
  email: string;
  password: string;
  publicEmail: string;
  status:
    | "stored"
    | "tested"
    | "active"
    | "invalid"
    | "expired"
    | "locked"
    | "backup";
  isPrimary: boolean;
  isBackup: boolean;
  usageCount: number;
  lastVerified: string | null;
  lastUsed: string | null;
  healthStatus: {
    healthScore: number;
    daysUntilExpiry: number | null;
    verificationFailures: number;
  };
}

// LinkedIn Credentials API - Public representation (without sensitive data)
export interface LinkedInCredentials {
  id: number;
  username: string;
  publicEmail: string;
  status:
    | "stored"
    | "tested"
    | "active"
    | "invalid"
    | "expired"
    | "locked"
    | "backup";
  isPrimary: boolean;
  isBackup: boolean;
  usageCount: number;
  lastVerified?: string | null;
  lastUsed?: string | null;
  healthStatus?: {
    healthScore?: number;
    daysUntilExpiry?: number | null;
    verificationFailures?: number;
    errorDetails?: {
      message?: string;
      errorType?: string;
      details?: Record<string, unknown>;
    };
    details?: {
      errorMessage?: string;
      reason?: string;
    };
  };
  linkedinProfileId?: number | null;
  executionMode?: "desktop" | "cloud";
  linkedinProfileUsername?: string | null;
  daemonIp?: string | null;
}

export interface LinkedInCredentialsHealth {
  credentialsId: number;
  healthStatus: {
    id: number;
    username: string;
    publicEmail: string;
    status: string;
    isPrimary: boolean;
    isBackup: boolean;
    usageCount: number;
    daysSinceRotation: number;
    daysUntilExpiry: number | null;
    verificationFailures: number;
    lastVerified: string | null;
    lastUsed: string | null;
    healthScore: number;
    errorDetails?: {
      message?: string;
      errorType?: string;
      details?: Record<string, unknown>;
    };
  };
}

export interface LinkedInCredentialLog {
  id: number;
  action: string;
  details: Record<string, unknown>;
  ipAddress: string | null;
  createdAt: string;
}

export interface LinkedInCredentialsLogsResponse {
  success: boolean;
  credentialsId: number;
  logs: LinkedInCredentialLog[];
  count: number;
}

export async function getLinkedInCredentials(): Promise<
  ApiResponse<{ credentials: LinkedInCredentials[]; count: number }>
> {
  return get("/api/linkedin-credentials");
}

export interface CreateLinkedInCredentialsData {
  email: string;
  password: string;
  username?: string;
  linkedin_profile_id?: number | null;
  execution_mode?: "desktop" | "cloud";
}

export async function createLinkedInCredentials(
  data: CreateLinkedInCredentialsData,
): Promise<
  ApiResponse<{
    success: boolean;
    id: number;
    message: string;
    credentials: LinkedInCredentials;
  }>
> {
  return post(
    "/api/linkedin-credentials",
    data as unknown as Record<string, unknown>,
  );
}

export interface LinkedInCredentialsUpdate {
  email?: string;
  password?: string;
  username?: string;
}

export async function updateLinkedInCredentials(
  id: number,
  data: LinkedInCredentialsUpdate,
): Promise<
  ApiResponse<{
    success: boolean;
    id: number;
    message: string;
    credentials: LinkedInCredentials;
  }>
> {
  return patch(
    `/api/linkedin-credentials/${id}`,
    data as Record<string, unknown>,
  );
}

export async function deleteLinkedInCredentials(
  id: number,
): Promise<ApiResponse<{ success: boolean; message: string }>> {
  return del(`/api/linkedin-credentials/${id}`);
}

export async function verifyLinkedInCredentials(
  id: number,
  options?: { testLogin?: boolean },
): Promise<
  ApiResponse<{
    success: boolean;
    message: string;
    credentials: LinkedInCredentials;
  }>
> {
  return post(`/api/linkedin-credentials/${id}/verify`, {
    test_login: options?.testLogin ?? true,
  });
}

export async function confirmLinkedInCredentials(id: number): Promise<
  ApiResponse<{
    success: boolean;
    message: string;
    credentials: LinkedInCredentials;
  }>
> {
  return post(`/api/linkedin-credentials/${id}/confirm`, {});
}

export async function rotateLinkedInCredentials(
  id: number,
  data?: { email?: string; password?: string },
): Promise<
  ApiResponse<{
    success: boolean;
    message: string;
    newCredentials: LinkedInCredentials;
    backupCredentials: LinkedInCredentials;
  }>
> {
  return post(`/api/linkedin-credentials/${id}/rotate`, data || {});
}

export async function getLinkedInCredentialsHealth(
  id: number,
): Promise<ApiResponse<LinkedInCredentialsHealth>> {
  return get(`/api/linkedin-credentials/${id}/health`);
}

export async function getLinkedInCredentialsLogs(
  id: number,
): Promise<ApiResponse<LinkedInCredentialsLogsResponse>> {
  return get(`/api/linkedin-credentials/${id}/logs`);
}

// LinkedIn Profiles API
export interface LinkedInProfile {
  id: number;
  linkedinUsername: string;
  active: boolean;
  connectDailyLimit: number;
  followUpDailyLimit: number;
}

export async function getLinkedInProfiles(): Promise<
  ApiResponse<{ profiles: LinkedInProfile[]; count: number }>
> {
  return get("/api/linkedin-profiles/");
}

// LinkedIn Profile Health API
export async function getLinkedInProfileHealth(): Promise<
  ApiResponse<LinkedInProfileHealthResponse>
> {
  return get("/api/linkedin-profiles/health");
}

// VNC Session API
export interface VNCSession {
  profile_id: string;
  websockify_port: number;
  vnc_url: string;
}

export async function getVNCSession(
  profileId: string,
): Promise<ApiResponse<VNCSession>> {
  return get(`/api/vnc/${profileId}`);
}

export async function listVNCSessions(): Promise<
  ApiResponse<{ sessions: Record<string, VNCSession> }>
> {
  return get("/api/vnc/sessions");
}

// Desktop Daemon Status API
export interface DaemonProfileStatus {
  profile_id: string;
  username: string;
  daemon_active: boolean;
  last_seen: string | null;
  version: string | null;
  platform: string | null;
  browser: string | null;
  is_logged_in: boolean;
  requires_verification: boolean;
  verification_type: string | null;
  session_updated_at: string | null;
  status: "online" | "offline" | "stale";
}

export interface DaemonStatusResponse {
  has_daemon: boolean;
  profiles: DaemonProfileStatus[];
}

export async function getDaemonStatus(): Promise<
  ApiResponse<DaemonStatusResponse>
> {
  return get("/api/linkedin-profiles/daemon/status");
}

// LinkedIn Setup API (OAuth/Cookie Guide)
export interface LinkedInCookieInstructions {
  success: boolean;
  instructions: {
    title: string;
    steps: Array<{
      step: number;
      title: string;
      description: string;
      note?: string;
    }>;
    alternative_method: {
      title: string;
      description: string;
      steps: string[];
    };
    security_note: string;
    verification: {
      title: string;
      description: string;
      success: string;
    };
  };
}

export async function getLinkedInCookieInstructions(): Promise<
  ApiResponse<LinkedInCookieInstructions>
> {
  return get("/api/linkedin-setup/cookie-instructions");
}

export interface LinkedInSetupGuide {
  success: boolean;
  guide: {
    introduction: {
      title: string;
      description: string;
    };
    methods: Array<{
      method: string;
      title: string;
      description: string;
      steps: string[];
      pros: string[];
      cons: string[];
    }>;
    prerequisites: {
      title: string;
      items: string[];
    };
    security: {
      title: string;
      items: string[];
    };
    troubleshooting: {
      title: string;
      items: Array<{
        issue: string;
        solution: string;
      }>;
    };
    next_steps: {
      title: string;
      items: string[];
    };
  };
}

export async function getLinkedInSetupGuide(): Promise<
  ApiResponse<LinkedInSetupGuide>
> {
  return get("/api/linkedin-setup/guide");
}

export interface LinkedInSetupStatus {
  success: boolean;
  status: {
    linkedinProfile: {
      exists: boolean;
      count: number;
      requiresAttention: boolean;
    };
    linkedinCredentials: {
      exists: boolean;
      count: number;
      activeCount: number;
      requiresAttention: boolean;
    };
    setupComplete: boolean;
    setupProgress: {
      current: number;
      total: number;
    };
  };
}

export async function getLinkedInSetupStatus(): Promise<
  ApiResponse<LinkedInSetupStatus>
> {
  return get("/api/linkedin-setup/status");
}

// LinkedIn Proxy Configuration API
export interface ProxyConfig {
  profileId: string;
  proxyServer: string | null;
  proxyUsername: string | null;
  proxyPassword: string | null;
  hasProxy: boolean;
}

export interface ProxyTestResult {
  success: boolean;
  message: string;
  statusCode?: number;
  error?: string;
}

export async function getProxyConfig(
  profileId: string,
): Promise<ApiResponse<ProxyConfig>> {
  return get(`/api/linkedin-profiles/${profileId}/proxy`);
}

export async function updateProxyConfig(
  profileId: string,
  proxyServer: string | null,
  proxyUsername?: string | null,
  proxyPassword?: string | null,
): Promise<ApiResponse<{ success: boolean }>> {
  return patch(`/api/linkedin-profiles/${profileId}`, {
    proxy_server: proxyServer,
    proxy_username: proxyUsername,
    proxy_password: proxyPassword,
  });
}

export async function testProxy(
  profileId: string,
  proxyServer: string,
  proxyUsername?: string | null,
  proxyPassword?: string | null,
): Promise<ApiResponse<ProxyTestResult>> {
  return post(`/api/linkedin-profiles/${profileId}/proxy/test`, {
    proxy_server: proxyServer,
    proxy_username: proxyUsername,
    proxy_password: proxyPassword,
  });
}

// Campaign Templates API
import {
  CampaignTemplate,
  CampaignTemplateCreateData,
} from "@/lib/types/components";

export async function getCampaignTemplates(
  publicParam?: string,
  page?: number,
  limit?: number,
): Promise<ApiResponse<{ data: CampaignTemplate[]; pagination: Pagination }>> {
  const params: Record<string, string> = {};
  if (publicParam) params.public = publicParam;
  if (page) params.page = page.toString();
  if (limit) params.limit = limit.toString();
  return get("/api/campaign-templates", params);
}

export async function getCampaignTemplate(
  id: string,
): Promise<ApiResponse<CampaignTemplate>> {
  return get(`/api/campaign-templates/${id}`);
}

export async function createCampaignTemplate(
  data: CampaignTemplateCreateData,
): Promise<ApiResponse<CampaignTemplate>> {
  return post(
    "/api/campaign-templates",
    data as unknown as Record<string, unknown>,
  );
}

export async function updateCampaignTemplate(
  id: string,
  data: Partial<CampaignTemplateCreateData>,
): Promise<ApiResponse<CampaignTemplate>> {
  return patch(
    `/api/campaign-templates/${id}`,
    data as unknown as Record<string, unknown>,
  );
}

export async function deleteCampaignTemplate(
  id: string,
): Promise<ApiResponse<{ success: boolean }>> {
  return del(`/api/campaign-templates/${id}`);
}

export async function cloneCampaignTemplate(
  id: string,
  data?: { name?: string; is_public?: boolean },
): Promise<ApiResponse<CampaignTemplate>> {
  return post(`/api/campaign-templates/${id}/clone`, data || {});
}

export async function createCampaignFromTemplate(
  id: string,
  data: { name?: string; description?: string },
): Promise<ApiResponse<{ id: number; name: string; description: string }>> {
  return post(`/api/campaign-templates/${id}/create-campaign`, data);
}

// MongoDB Profile API
export interface MongoUserProfile {
  id?: string;
  username: string;
  campaign: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  created_at?: string;
  updated_at?: string;
}

export async function getMongoUserProfile(): Promise<
  ApiResponse<MongoUserProfile>
> {
  return get("/api/mongodb/profile/");
}

export async function updateMongoUserProfile(
  data: Partial<MongoUserProfile>,
): Promise<ApiResponse<MongoUserProfile>> {
  return post("/api/mongodb/profile/", data);
}

export async function patchMongoUserProfile(
  data: Partial<MongoUserProfile>,
): Promise<ApiResponse<MongoUserProfile>> {
  return patch("/api/mongodb/profile/update/", data);
}

// Global recent activity feed
export interface RecentActivityEntry {
  id: string;
  type: string;
  status: string;
  error: string | null;
  timestamp: string;
  campaignId: string;
  campaignName: string;
  leadName: string;
  details?: {
    lead_name?: string;
    public_identifier?: string;
    lead_url?: string;
    headline?: string;
    reason?: string;
    message_preview?: string;
    state?: string;
  };
}

export async function getRecentActivity(
  limit = 10,
): Promise<ApiResponse<{ data: RecentActivityEntry[] }>> {
  return get("/api/analytics/activity", { limit: String(limit) });
}

// Campaign activity log
export interface ActivityEntry {
  id: string;
  source: "action" | "task";
  type: string;
  status: string;
  error: string | null;
  durationMs: number | null;
  timestamp: string;
  details?: {
    lead_name?: string;
    public_identifier?: string;
    lead_url?: string;
    headline?: string;
    reason?: string;
    message_preview?: string;
    state?: string;
  };
}

export interface NextTask {
  id: number;
  taskType: string;
  scheduledAt: string;
  etaSeconds: number;
}

export interface CampaignActivityResponse {
  data: ActivityEntry[];
  nextTask: NextTask | null;
  pendingCount: number;
  pagination: {
    page: number;
    limit: number;
    total: number;
    hasMore: boolean;
  };
}

export async function getCampaignActivity(
  campaignId: number | string,
  page = 1,
  limit = 20,
): Promise<ApiResponse<CampaignActivityResponse>> {
  return get(`/api/campaigns/${campaignId}/activity`, {
    page: String(page),
    limit: String(limit),
  });
}

// Re-export AddToCampaignModal types for convenience
export interface AddToCampaignParams {
  leadId: string;
  campaignId: string;
}

// Update deal state
export async function updateDealState(
  leadId: string,
  campaignId: string,
  state: string
): Promise<ApiResponse<{ success: boolean; message: string }>> {
  return patch(`/api/leads/${leadId}/campaigns/${campaignId}/state`, { state });
}
