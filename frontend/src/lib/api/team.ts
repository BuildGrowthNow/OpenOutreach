import { apiClient } from "../apiClientV2";
import { ApiResponse } from "../api";

export interface OrganizationSummary {
  id: string;
  name: string;
  owner_user_id: string;
  plan: string;
  role: "owner" | "admin" | "member";
  is_personal: boolean;
  is_shared: boolean;
  team_workspaces_enabled: boolean;
  cloud_seat_limit: number | null;
  cloud_seats: number | null;
  linkedin_account_limit: number | null;
  members_count: number;
  assigned_profiles: number;
  created_at: string | null;
}

export interface TeamMember {
  user_id: string;
  email: string;
  full_name: string | null;
  role: "owner" | "admin" | "member";
  status: string;
  invited_at: string | null;
  joined_at: string | null;
}

export interface TeamInvite {
  id: string;
  email: string;
  role: "owner" | "admin" | "member";
  expires_at: string;
  created_at: string;
  email_sent: boolean;
  debug_invite_url?: string | null;
}

export interface InvitePreview {
  org_id: string;
  org_name: string;
  email: string;
  role: "owner" | "admin" | "member";
  expires_at: string;
}

export interface SeatSummary {
  cloud_seat_limit: number | null;
  cloud_seats_used?: number;
  cloud_seats_remaining?: number;
  cloud_profiles: number;
  credentialed_profiles: number;
  desktop_credentialed_profiles?: number;
  assigned_profiles: number;
  unassigned_profiles: number;
  whatsapp_cloud_profiles?: number;
  whatsapp_assigned_profiles?: number;
  whatsapp_only_seats?: number;
  duo_seats?: number;
  linkedin_seats?: number;
  members: number;
}

export interface OrgProfile {
  profile_id: string;
  linkedin_username: string | null;
  phone_number?: string | null;
  channel?: string | null;
  cloud_mode?: string | null;
  assigned_user_id: string | null;
  execution_mode: string | null;
  active: boolean;
  proxy_assigned: boolean;
  proxy_mode: string | null;
}

export interface OrgAuditEvent {
  id: string;
  event: string;
  actor_user_id: string | null;
  target_user_id: string | null;
  target_email: string | null;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export async function listOrganizations(): Promise<ApiResponse<OrganizationSummary[]>> {
  return apiClient.get<OrganizationSummary[]>("/organizations");
}

export async function getCurrentOrganization(): Promise<ApiResponse<OrganizationSummary>> {
  return apiClient.get<OrganizationSummary>("/organizations/current");
}

export async function activateOrganization(
  orgId: string
): Promise<ApiResponse<OrganizationSummary>> {
  return apiClient.post<OrganizationSummary>(`/organizations/${orgId}/activate`, {});
}

export async function updateOrganization(
  orgId: string,
  name: string
): Promise<ApiResponse<OrganizationSummary>> {
  return apiClient.patch<OrganizationSummary>(`/organizations/${orgId}`, { name });
}

export async function listTeamMembers(
  orgId: string
): Promise<ApiResponse<TeamMember[]>> {
  return apiClient.get<TeamMember[]>(`/organizations/${orgId}/members`);
}

export async function listPendingInvites(
  orgId: string
): Promise<ApiResponse<TeamInvite[]>> {
  return apiClient.get<TeamInvite[]>(`/organizations/${orgId}/invites`);
}

export async function createTeamInvite(
  orgId: string,
  email: string,
  role: "admin" | "member"
): Promise<ApiResponse<TeamInvite>> {
  return apiClient.post<TeamInvite>(`/organizations/${orgId}/invites`, {
    email,
    role,
  });
}

export async function revokeTeamInvite(
  orgId: string,
  inviteId: string
): Promise<ApiResponse<null>> {
  return apiClient.delete<null>(`/organizations/${orgId}/invites/${inviteId}`);
}

export async function previewTeamInvite(
  token: string
): Promise<ApiResponse<InvitePreview>> {
  return apiClient.get<InvitePreview>(`/organizations/invites/${encodeURIComponent(token)}`);
}

export async function acceptTeamInvite(
  token: string
): Promise<ApiResponse<OrganizationSummary>> {
  return apiClient.post<OrganizationSummary>(
    `/organizations/invites/${encodeURIComponent(token)}/accept`,
    {}
  );
}

export async function updateMemberRole(
  orgId: string,
  userId: string,
  role: "admin" | "member"
): Promise<ApiResponse<TeamMember>> {
  return apiClient.patch<TeamMember>(
    `/organizations/${orgId}/members/${userId}`,
    { role }
  );
}

export async function removeTeamMember(
  orgId: string,
  userId: string
): Promise<ApiResponse<null>> {
  return apiClient.delete<null>(`/organizations/${orgId}/members/${userId}`);
}

export async function getSeatSummary(
  orgId: string
): Promise<ApiResponse<SeatSummary>> {
  return apiClient.get<SeatSummary>(`/organizations/${orgId}/seats`);
}

export async function assignSeat(
  orgId: string,
  profileId: string,
  assignedUserId: string,
  channel: string = "linkedin"
): Promise<ApiResponse<OrgProfile>> {
  return apiClient.post<OrgProfile>(`/organizations/${orgId}/seats/assign`, {
    profile_id: profileId,
    assigned_user_id: assignedUserId,
    channel,
  });
}

export async function assignDesktopSeat(
  orgId: string,
  profileId: string,
  assignedUserId: string
): Promise<ApiResponse<OrgProfile>> {
  return apiClient.post<OrgProfile>(
    `/organizations/${orgId}/seats/assign-desktop`,
    {
      profile_id: profileId,
      assigned_user_id: assignedUserId,
    }
  );
}

export async function unassignSeat(
  orgId: string,
  profileId: string,
  channel: string = "linkedin"
): Promise<ApiResponse<OrgProfile>> {
  return apiClient.post<OrgProfile>(`/organizations/${orgId}/seats/unassign`, {
    profile_id: profileId,
    channel,
  });
}

export async function removeSeat(
  orgId: string,
  profileId: string,
  channel: string = "linkedin"
): Promise<ApiResponse<OrgProfile>> {
  return apiClient.post<OrgProfile>(`/organizations/${orgId}/seats/remove`, {
    profile_id: profileId,
    channel,
  });
}

export async function listOrgProfiles(
  orgId: string
): Promise<ApiResponse<OrgProfile[]>> {
  return apiClient.get<OrgProfile[]>(`/organizations/${orgId}/profiles`);
}

export async function listOrgAuditEvents(
  orgId: string
): Promise<ApiResponse<OrgAuditEvent[]>> {
  return apiClient.get<OrgAuditEvent[]>(`/organizations/${orgId}/audit`);
}
