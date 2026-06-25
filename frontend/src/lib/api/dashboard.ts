'use client'

import { get, post, patch, del, ApiResponse } from '../api'

// JWT Authentication API
export interface JwtTokens {
  access: string
  refresh: string
  user: {
    id: number
    email?: string
    username?: string
    is_staff?: boolean
    is_superuser?: boolean
  }
}

export interface AuthStatus {
  status: 'authenticated' | 'anonymous'
  message: string
  user?: {
    id: number
    username: string
    email?: string
    is_authenticated: boolean
    is_staff?: boolean
    is_superuser?: boolean
    last_login?: string
    date_joined?: string
  }
}

// JWT Authentication API Functions
export async function login(password: string): Promise<ApiResponse<JwtTokens>> {
  return post('/api/auth/login', { password })
}

export async function refreshAccessToken(refreshToken: string): Promise<ApiResponse<{ access: string }>> {
  return post('/api/auth/refresh', { refresh: refreshToken })
}

export async function verifyToken(accessToken: string): Promise<ApiResponse<{ valid: boolean }>> {
  return post('/api/auth/verify', { token: accessToken })
}

export async function getAuthStatus(): Promise<ApiResponse<AuthStatus>> {
  return get('/api/auth/status')
}

export async function logout(): Promise<ApiResponse<{ status: string; message: string }>> {
  return del('/api/auth/logout')
}

export async function requestPasswordReset(email: string): Promise<ApiResponse<{ status: string; message: string }>> {
  return post('/api/auth/password-reset/request', { email })
}

export async function confirmPasswordReset(token: string, password: string): Promise<ApiResponse<{ status: string; message: string }>> {
  return post('/api/auth/password-reset/confirm', { token, password })
}

export async function updatePassword(currentPassword: string, newPassword: string): Promise<ApiResponse<{ status: string; message: string }>> {
  return post('/api/auth/update-password', { current_password: currentPassword, new_password: newPassword })
}
import {
  Campaign,
  Lead,
  Message,
  HealthStatus,
  Pagination,
  LinkMetrics,
  LinkedInProfileHealthResponse
} from '@/lib/types/components'

// RateLimits type is no longer exported from components.ts
// Use Settings.rate_limits from this file for the new canonical shape

// Campaign API
export async function getCampaigns(
  status?: string,
  page?: number,
  limit?: number
): Promise<ApiResponse<{ data: Campaign[]; pagination: Pagination }>> {
  const params: Record<string, string> = {}
  if (status) params.status = status
  if (page) params.page = page.toString()
  if (limit) params.limit = limit.toString()
  return get('/api/campaigns', params)
}

export async function getCampaign(id: string): Promise<ApiResponse<Campaign>> {
  return get(`/api/campaigns/${id}`)
}

// Ghost Mode API
export interface GhostSimulationLog {
  id: number
  action_type: string
  target_name: string
  target_url: string
  result_data: Record<string, unknown>
  rating: number | null
  score: number | null
  started_at: string
  completed_at: string
  simulated_action: Record<string, unknown>
}

export interface GhostSimulationResponse {
  success: boolean
  campaign_id: number
  total: number
  simulations: GhostSimulationLog[]
}

export async function getGhostModeSimulations(campaignId: string): Promise<ApiResponse<GhostSimulationResponse>> {
  return get(`/api/campaigns/${campaignId}/ghost-mode/simulations`)
}

export async function startGhostMode(campaignId: string): Promise<ApiResponse<{
  success: boolean
  ghost_campaign_id: number
  message: string
  created: boolean
}>> {
  return post(`/api/campaigns/${campaignId}/ghost-mode/action`, { action: 'start' })
}

export async function stopGhostMode(campaignId: string): Promise<ApiResponse<{
  success: boolean
  message: string
}>> {
  return post(`/api/campaigns/${campaignId}/ghost-mode/action`, { action: 'stop' })
}

// Targeted polling - only fetch campaign status for performance
export async function getCampaignStatus(id: string): Promise<ApiResponse<{ status: string }>> {
  return get(`/api/campaigns/${id}/status`)
}

export async function createCampaign(data: Partial<Campaign>): Promise<ApiResponse<Campaign>> {
  return post('/api/campaigns', data)
}

export async function updateCampaign(
  id: string,
  data: Partial<Campaign>
): Promise<ApiResponse<Campaign>> {
  return patch(`/api/campaigns/${id}`, data)
}

export async function deleteCampaign(id: string): Promise<ApiResponse<{ success: boolean }>> {
  return del(`/api/campaigns/${id}`)
}

// Campaign Analytics API
export interface CampaignAnalyticsResponse {
  period: string
  campaign_id: string
  stats: {
    connections_sent: number
    connections_accepted: number
    connection_accept_rate: number
    messages_sent: number
    messages_replied: number
    responses: number
    response_rate: number
    conversions: number
    conversion_rate: number
    errors: number
    rate_limit_warnings: number
    daily_connections?: number
    daily_messages?: number
    last_7_days?: {
      connections_sent?: number
      connections_accepted?: number
    }
    last_30_days?: {
      connections_accepted?: number
      conversions?: number
    }
    connection_success_rate?: number
    avg_time_to_accept?: string
    total_connection_attempts?: number
    failed_connections?: number
    avg_response_time?: string
    message_open_rate?: number
    total_messages_sent?: number
    positive_responses?: number
    avg_conversion_time?: string
    qualified_leads?: number
    hot_leads?: number
    deals_closed?: number
    profile_views?: number
    link_clicks?: number
    document_downloads?: number
    meeting_bookings?: number
    responses_under_1h?: number
    responses_1_24h?: number
    responses_1_7d?: number
    responses_over_7d?: number
    peak_day?: string
    peak_hour?: string
    timezone_optimization?: string
    high_quality_conversions?: number
    medium_quality_conversions?: number
    low_quality_conversions?: number
    best_performing_source?: string
    best_roi_source?: string
    avg_cost_per_conversion?: number
    best_performing_time?: string
    best_performing_day?: string
  }
  daily_breakdown: Array<{
    date: string
    connections_sent: number
    connections_accepted: number
    messages_sent: number
    messages_replied: number
  }>
  pipeline: {
    qualified: number
    ready_to_connect: number
    pending: number
    connected: number
    completed: number
    failed: number
    no_email: number
  }
}

export async function getCampaignAnalytics(
  id: string,
  period?: string
): Promise<ApiResponse<CampaignAnalyticsResponse>> {
  const params: Record<string, string> = {}
  if (period) params.period = period
  return get(`/api/campaigns/${id}/analytics`, params)
}

// Campaign Leads API
export interface LeadFilters {
  status?: string
  search?: string
  total_count?: number
}

export async function getCampaignLeads(
  id: string,
  status?: string,
  search?: string,
  page?: number,
  limit?: number
): Promise<ApiResponse<{ data: Lead[]; pagination: Pagination; filters: LeadFilters }>> {
  const params: Record<string, string> = {}
  if (status) params.status = status
  if (search) params.search = search
  if (page) params.page = page.toString()
  if (limit) params.limit = limit.toString()
  return get(`/api/campaigns/${id}/leads`, params)
}

// Campaign Messages API
export async function getCampaignMessages(
  id: string,
  page?: number,
  limit?: number
): Promise<ApiResponse<{ data: Message[]; pagination: Pagination }>> {
  const params: Record<string, string> = {}
  if (page) params.page = page.toString()
  if (limit) params.limit = limit.toString()
  return get(`/api/campaigns/${id}/messages`, params)
}

// Leads API
export async function getLeads(
  status?: string,
  search?: string,
  disqualified?: boolean,
  page?: number,
  limit?: number
): Promise<ApiResponse<{ data: Lead[]; pagination: Pagination }>> {
  const params: Record<string, string | boolean> = {}
  if (status) params.status = status
  if (search) params.search = search
  if (disqualified !== undefined) params.disqualified = disqualified
  if (page) params.page = page.toString()
  if (limit) params.limit = limit.toString()
  return get('/api/leads', params as Record<string, string>)
}

export async function getLead(id: string): Promise<ApiResponse<Lead>> {
  return get(`/api/leads/${id}`)
}

export async function createLead(
  data: Partial<Lead>
): Promise<ApiResponse<Lead>> {
  return post('/api/leads', data)
}

export async function updateLead(
  id: string,
  data: Partial<Lead>
): Promise<ApiResponse<Lead>> {
  return patch(`/api/leads/${id}`, data)
}

export interface LeadProfile {
  first_name?: string
  last_name?: string
  headline?: string
  summary?: string
  location?: string
  experience?: Array<{
    company?: string
    title?: string
    duration?: string
  }>
  education?: Array<{
    school?: string
    degree?: string
    year?: string
  }>
}

export async function reScrapeLeadProfile(id: string): Promise<ApiResponse<{ success: boolean; profile: LeadProfile }>> {
  return post(`/api/leads/${id}/profile`)
}

// Messages API
export async function getMessages(
  campaign_id?: string,
  deal_id?: string,
  lead_id?: string,
  page?: number,
  limit?: number
): Promise<ApiResponse<{ data: Message[]; pagination: Pagination }>> {
  // Use lead_id endpoint if available (most specific)
  if (lead_id) {
    const params: Record<string, string> = {}
    if (page) params.page = page.toString()
    if (limit) params.limit = limit.toString()
    return get(`/api/leads/${lead_id}/messages`, params)
  }
  
  // Use deal_id endpoint if available
  if (deal_id) {
    const params: Record<string, string> = {}
    if (page) params.page = page.toString()
    if (limit) params.limit = limit.toString()
    return get(`/api/deals/${deal_id}/messages`, params)
  }
  
  // Use campaign_id endpoint if available
  if (campaign_id) {
    const params: Record<string, string> = {}
    if (page) params.page = page.toString()
    if (limit) params.limit = limit.toString()
    return get(`/api/campaigns/${campaign_id}/messages`, params)
  }
  
  // Fallback to /api/messages if none specified (backend should handle this)
  const params: Record<string, string> = {}
  if (page) params.page = page.toString()
  if (limit) params.limit = limit.toString()
  return get('/api/messages', params)
}

// Send message to lead
export async function sendMessageToLead(
  lead_id: string,
  content: string
): Promise<ApiResponse<{ success: boolean; message: Message }>> {
  return post(`/api/leads/${lead_id}/messages`, { content, is_outgoing: true })
}

// Lead Notes API
export interface Note {
  id: string
  content: string
  created_by: string
  created_at: string
  updated_at?: string
}

export async function getLeadNotes(
  lead_id: string
): Promise<ApiResponse<{ data: Note[]; pagination: Pagination }>> {
  return get(`/api/leads/${lead_id}/notes`)
}

export async function createLeadNote(
  lead_id: string,
  content: string
): Promise<ApiResponse<Note>> {
  return post(`/api/leads/${lead_id}/notes`, { content })
}

export async function updateLeadNote(
  lead_id: string,
  note_id: string,
  content: string
): Promise<ApiResponse<Note>> {
  return patch(`/api/leads/${lead_id}/notes/${note_id}`, { content })
}

export async function deleteLeadNote(
  lead_id: string,
  note_id: string
): Promise<ApiResponse<{ success: boolean }>> {
  return del(`/api/leads/${lead_id}/notes/${note_id}`)
}

// Links API
export async function getLinks(): Promise<ApiResponse<{ data: LinkMetrics[]; pagination: Pagination }>> {
  return get('/api/links')
}

export interface LinkBreakdown {
  by_device?: {
    desktop?: number
    mobile?: number
    tablet?: number
  }
  by_country?: Record<string, number>
  by_source?: Record<string, number>
  daily?: Array<{
    date?: string
    clicks?: number
  }>
}

export async function getLink(id: string): Promise<ApiResponse<LinkMetrics & { breakdown: LinkBreakdown }>> {
  return get(`/api/links/${id}`)
}

// Settings API
export interface Settings {
  llm: {
    provider: string
    model: string
    api_base: string
  }
  rate_limits: {
    daily_connection_limit: number
    daily_follow_up_limit: number
    velocity: number
    cooldown_minutes: number
  }
  linkedin_profile: {
    username: string
    campaign: string
  }
}

export async function getSettings(): Promise<ApiResponse<Settings>> {
  return get('/api/settings')
}

export async function updateSettings(data: Partial<{ llm?: Partial<Settings['llm']>; rate_limits?: Partial<Settings['rate_limits']>; linkedin_profile?: Partial<Settings['linkedin_profile']> }>): Promise<ApiResponse<Settings>> {
  return patch('/api/settings', data)
}

export async function getRateLimits(): Promise<ApiResponse<Settings['rate_limits']>> {
  return get('/api/settings/rate-limits')
}

export interface LinkedinProfileRateLimit {
  profile_id: number
  profile_username: string
  base_limit: number
  effective_limit: number
  remaining: number
  use_multiplier: number
  day_multiplier: number
  detectability_score: number
}

export interface DailyUsageResponse {
  daily_connections_sent: number
  daily_messages_sent: number
  daily_limit: number  // Base limit (for backward compatibility)
  effective_limit: number  // Context-aware effective limit
  remaining: number  // Total remaining across all profiles
  rate_limit_status: 'normal' | 'caution' | 'warning' | 'exceeded'
  warning_message?: string
  warning_level?: 'low' | 'medium' | 'high'
  last_reset: string
  reset_frequency: string
  linkedin_profiles: LinkedinProfileRateLimit[]
}

export async function getDailyUsage(): Promise<ApiResponse<DailyUsageResponse>> {
  return get('/api/settings/daily-usage')
}

// Health API
export async function getHealthStatus(): Promise<ApiResponse<HealthStatus>> {
  return get('/api/health')
}

// State Machine API
export interface StateMachineNode {
  id: string
  name: string
  type: string
  config?: Record<string, unknown>
  x: number
  y: number
  description?: string
}

export interface StateMachineTransition {
  id: string
  source_node: string
  target_node: string
  label?: string
  condition_type?: string
}

export interface StateMachineResponse {
  id: string
  campaign_id: string
  name: string
  description: string
  is_active: boolean
  is_valid: boolean
  validation_errors: string[]
  nodes: StateMachineNode[]
  transitions: StateMachineTransition[]
}

export async function getStateMachine(campaignId: string): Promise<ApiResponse<StateMachineResponse>> {
  return get(`/api/campaigns/${campaignId}/state-machine`)
}

export async function updateStateMachine(
  campaignId: string,
  data: { name: string; description: string; graph_data: { nodes: StateMachineNode[]; transitions: StateMachineTransition[] } }
): Promise<ApiResponse<StateMachineResponse>> {
  return post(`/api/campaigns/${campaignId}/state-machine`, data)
}

export async function validateStateMachine(
  campaignId: string,
  data: StateMachineResponse
): Promise<ApiResponse<{ is_valid: boolean; errors: string[]; warnings: Array<{ type: string; message: string }> }>> {
  return post(`/api/campaigns/${campaignId}/state-machine/validate`, data as unknown as Record<string, unknown>)
}

export interface SimulationResult {
  success: boolean
  simulation: {
    path: Array<{
      node: string
      name: string
      type: string
    }>
    nodes_visited: number
    transitions_used: number
    final_status: string
    messages_sent: string[]
    completed: boolean
    steps: number
    error: string | null
  }
}

export async function simulateStateMachine(
  campaignId: string,
  dealId: string
): Promise<ApiResponse<SimulationResult>> {
  return post('/api/state-machine/simulate', { campaign_id: campaignId, deal_id: dealId })
}


export interface SimulationInput {
  input: string;
  startState: string;
  maxSteps: number;
}

export async function simulateStateMachineExecution(
  campaignId: string,
  data: SimulationInput
): Promise<ApiResponse<{
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
}>> {
  return post(`/api/campaigns/${campaignId}/state-machine/simulate`, data as unknown as Record<string, unknown>)
}

// LinkedIn Credentials API - Internal representation (with sensitive data)
export interface LinkedInCredentialsInternal {
  id: number
  username: string
  email: string
  password: string
  public_email: string
  status: 'active' | 'invalid' | 'expired' | 'locked' | 'backup'
  is_primary: boolean
  is_backup: boolean
  usage_count: number
  last_verified: string | null
  last_used: string | null
  health_status: {
    health_score: number
    days_until_expiry: number | null
    verification_failures: number
  }
}

// LinkedIn Credentials API - Public representation (without sensitive data)
export interface LinkedInCredentials {
  id: number
  username: string
  public_email: string
  status: 'active' | 'invalid' | 'expired' | 'locked' | 'backup'
  is_primary: boolean
  is_backup: boolean
  usage_count: number
  last_verified?: string | null
  last_used?: string | null
  health_status: {
    health_score: number
    days_until_expiry: number | null
    verification_failures: number
  }
  linkedin_profile_id?: number | null
}

export interface LinkedInCredentialsHealth {
  credentials_id: number
  health_status: {
    id: number
    username: string
    public_email: string
    status: string
    is_primary: boolean
    is_backup: boolean
    usage_count: number
    days_since_rotation: number
    days_until_expiry: number | null
    verification_failures: number
    last_verified: string | null
    last_used: string | null
    health_score: number
  }
}

export interface LinkedInCredentialLog {
  id: number
  action: string
  details: Record<string, unknown>
  ip_address: string | null
  created_at: string
}

export interface LinkedInCredentialsLogsResponse {
  success: boolean
  credentials_id: number
  logs: LinkedInCredentialLog[]
  count: number
}

export async function getLinkedInCredentials(): Promise<ApiResponse<{ credentials: LinkedInCredentials[]; count: number }>> {
  return get('/api/linkedin-credentials')
}

export interface CreateLinkedInCredentialsData {
  email: string
  password: string
  username?: string
  linkedin_profile_id?: number | null
}

export async function createLinkedInCredentials(
  data: CreateLinkedInCredentialsData
): Promise<ApiResponse<{ success: boolean; id: number; message: string; credentials: LinkedInCredentials }>> {
  return post('/api/linkedin-credentials', data as unknown as Record<string, unknown>)
}

export interface LinkedInCredentialsUpdate {
  email?: string
  password?: string
  username?: string
}

export async function updateLinkedInCredentials(
  id: number,
  data: LinkedInCredentialsUpdate
): Promise<ApiResponse<{ success: boolean; id: number; message: string; credentials: LinkedInCredentials }>> {
  return patch(`/api/linkedin-credentials/${id}`, data as Record<string, unknown>)
}

export async function deleteLinkedInCredentials(id: number): Promise<ApiResponse<{ success: boolean; message: string }>> {
  return del(`/api/linkedin-credentials/${id}`)
}

export async function verifyLinkedInCredentials(id: number): Promise<ApiResponse<{ success: boolean; message: string; credentials: LinkedInCredentials }>> {
  return post(`/api/linkedin-credentials/${id}/verify`, {})
}

export async function rotateLinkedInCredentials(id: number, data?: { email?: string; password?: string }): Promise<ApiResponse<{ success: boolean; message: string; new_credentials: LinkedInCredentials; backup_credentials: LinkedInCredentials }>> {
  return post(`/api/linkedin-credentials/${id}/rotate`, data || {})
}

export async function getLinkedInCredentialsHealth(id: number): Promise<ApiResponse<LinkedInCredentialsHealth>> {
  return get(`/api/linkedin-credentials/${id}/health`)
}

export async function getLinkedInCredentialsLogs(id: number): Promise<ApiResponse<LinkedInCredentialsLogsResponse>> {
  return get(`/api/linkedin-credentials/${id}/logs`)
}

// LinkedIn Profiles API
export interface LinkedInProfile {
  id: number
  linkedin_username: string
  active: boolean
  connect_daily_limit: number
  follow_up_daily_limit: number
}

export async function getLinkedInProfiles(): Promise<ApiResponse<{ profiles: LinkedInProfile[]; count: number }>> {
  return get('/api/linkedin-profiles')
}

// LinkedIn Profile Health API
export async function getLinkedInProfileHealth(): Promise<ApiResponse<LinkedInProfileHealthResponse>> {
  return get('/api/linkedin-profile-health')
}

// Upload campaign leads (CSV)
export async function uploadCampaignLeads(
  campaignId: string,
  file: File
): Promise<ApiResponse<{ imported: number; skipped: number }>> {
  const formData = new FormData()
  formData.append('file', file)
  return post(`/api/campaigns/${campaignId}/leads/upload/`, formData)
}

// LinkedIn Setup API (OAuth/Cookie Guide)
export interface LinkedInCookieInstructions {
  success: boolean
  instructions: {
    title: string
    steps: Array<{
      step: number
      title: string
      description: string
      note?: string
    }>
    alternative_method: {
      title: string
      description: string
      steps: string[]
    }
    security_note: string
    verification: {
      title: string
      description: string
      success: string
    }
  }
}

export async function getLinkedInCookieInstructions(): Promise<ApiResponse<LinkedInCookieInstructions>> {
  return get('/api/linkedin-setup/cookie-instructions')
}

export interface LinkedInSetupGuide {
  success: boolean
  guide: {
    introduction: {
      title: string
      description: string
    }
    methods: Array<{
      method: string
      title: string
      description: string
      steps: string[]
      pros: string[]
      cons: string[]
    }>
    prerequisites: {
      title: string
      items: string[]
    }
    security: {
      title: string
      items: string[]
    }
    troubleshooting: {
      title: string
      items: Array<{
        issue: string
        solution: string
      }>
    }
    next_steps: {
      title: string
      items: string[]
    }
  }
}

export async function getLinkedInSetupGuide(): Promise<ApiResponse<LinkedInSetupGuide>> {
  return get('/api/linkedin-setup/guide')
}

export interface LinkedInSetupStatus {
  success: boolean
  status: {
    linkedin_profile: {
      exists: boolean
      count: number
      requires_attention: boolean
    }
    linkedin_credentials: {
      exists: boolean
      count: number
      active_count: number
      requires_attention: boolean
    }
    setup_complete: boolean
    setup_progress: {
      current: number
      total: number
    }
  }
}

export async function getLinkedInSetupStatus(): Promise<ApiResponse<LinkedInSetupStatus>> {
  return get('/api/linkedin-setup/status')
}

