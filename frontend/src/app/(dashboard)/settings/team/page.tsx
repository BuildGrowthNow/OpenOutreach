"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Breadcrumb } from "@/components/layout/breadcrumb";
import { Icons } from "@/lib/types/components";
import { useAuthStore } from "@/lib/authStoreV2";
import { useBilling } from "@/lib/contexts/billing-context";
import {
  getSeatSummary,
  listOrgAuditEvents,
  listOrgProfiles,
  listPendingInvites,
  listTeamMembers,
  revokeTeamInvite,
  type OrgAuditEvent,
  type OrgProfile,
  type SeatSummary,
  type TeamInvite,
  type TeamMember,
} from "@/lib/api/team";
import { InviteMemberForm } from "@/components/team/invite-member-form";
import { TeamMembersCard } from "@/components/team/team-members-card";
import { SeatAssignmentCard } from "@/components/team/seat-assignment-card";

function TeamLoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export default function TeamSettingsPage() {
  const { user } = useAuthStore();
  const { billingStatus, loading: billingLoading, refetch: refetchBilling } = useBilling();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [invites, setInvites] = useState<TeamInvite[]>([]);
  const [profiles, setProfiles] = useState<OrgProfile[]>([]);
  const [seats, setSeats] = useState<SeatSummary | null>(null);
  const [auditEvents, setAuditEvents] = useState<OrgAuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The auth store updates immediately after accepting an invite or switching
  // workspaces; the billing context can lag by up to a minute. Prefer the auth
  // org and only take the billing role when both point at the same workspace.
  const orgId = user?.org_id || billingStatus?.org_id || "";
  const billingOrgMatches = Boolean(orgId && billingStatus?.org_id === orgId);
  const role =
    (billingOrgMatches ? billingStatus?.org_role : user?.org_role) ||
    user?.org_role ||
    billingStatus?.org_role ||
    "member";
  const enabled = billingStatus?.team_workspaces_enabled === true;
  const canManage = role === "owner" || role === "admin";
  const canChangeRoles = role === "owner";
  const isMember = role === "member";

  const load = useCallback(async () => {
    if (!orgId || !enabled) {
      setLoading(false);
      setHasLoaded(true);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const profileResponse = await listOrgProfiles(orgId);
      if (profileResponse.error) setError(profileResponse.error);
      setProfiles(profileResponse.data ?? []);

      const seatResponse = await getSeatSummary(orgId);
      if (!seatResponse.error) setSeats(seatResponse.data ?? null);

      if (canManage) {
        const [memberResponse, inviteResponse, auditResponse] = await Promise.all([
          listTeamMembers(orgId),
          listPendingInvites(orgId),
          listOrgAuditEvents(orgId),
        ]);
        if (memberResponse.error) setError(memberResponse.error);
        setMembers(memberResponse.data ?? []);
        setInvites(inviteResponse.data ?? []);
        setAuditEvents((auditResponse.data ?? []).slice(0, 10));
      } else {
        setMembers([]);
        setInvites([]);
        setAuditEvents([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load team settings");
    } finally {
      setLoading(false);
      setHasLoaded(true);
    }
  }, [orgId, enabled, canManage]);

  useEffect(() => {
    void load();
  }, [load]);

  const seatUsage = useMemo(() => {
    if (!seats) return null;
    if (seats.cloud_seat_limit === null || seats.cloud_seat_limit <= 0) return null;
    const breakdown = [
      seats.linkedin_seats ? `${seats.linkedin_seats} LinkedIn` : null,
      seats.duo_seats ? `${seats.duo_seats} Duo` : null,
      seats.whatsapp_only_seats
        ? `${seats.whatsapp_only_seats} WhatsApp-only`
        : null,
    ]
      .filter(Boolean)
      .join(" · ");
    return `${seats.cloud_seats_used ?? 0} of ${seats.cloud_seat_limit} cloud seats used${
      breakdown ? ` (${breakdown})` : ""
    }`;
  }, [seats]);

  const handleRevokeInvite = async (inviteId: string) => {
    const response = await revokeTeamInvite(orgId, inviteId);
    if (response.error) {
      window.alert(response.error);
      return;
    }
    await load();
  };

  const isInitialLoading = loading && !hasLoaded;
  if (isInitialLoading || (billingLoading && !billingStatus)) {
    return <TeamLoadingSkeleton />;
  }

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Settings", href: "/settings" },
          { label: "Team", href: "/settings/team", isActive: true },
        ]}
      />

      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">Team</h1>
          <p className="text-muted-foreground">
            Share one billing relationship and assign cloud seats to your members.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="capitalize">{role}</Badge>
          <Badge variant="secondary" className="capitalize">{billingStatus?.plan || "plan"}</Badge>
          {seatUsage && <Badge>{seatUsage}</Badge>}
        </div>
      </div>

      {!enabled && (
        <Alert>
          <Icons.Info className="h-4 w-4" />
          <AlertDescription>
            Team workspaces are disabled. You are using your personal workspace and personal billing.
            Existing organization data is retained.
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {enabled && (
        <>
          {canManage && orgId && (
            <InviteMemberForm
              orgId={orgId}
              canInviteAdmins={canChangeRoles}
              onInvited={() => void load()}
            />
          )}

          {canManage && (
            <TeamMembersCard
              orgId={orgId}
              members={members}
              currentUserId={user?.id || ""}
              canManage={canManage}
              canChangeRoles={canChangeRoles}
              onChanged={() => {
                void load();
                void refetchBilling();
              }}
            />
          )}

          {invites.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Pending invites</CardTitle>
                <CardDescription>Invites expire automatically and can only be used once.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {invites.map((invite) => (
                  <div key={invite.id} className="flex items-center justify-between gap-2 rounded-md border border-border/60 p-2 text-sm">
                    <span className="truncate">{invite.email}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground capitalize">
                        {invite.role} · expires {new Date(invite.expires_at).toLocaleDateString()}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleRevokeInvite(invite.id)}
                      >
                        Revoke
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {isMember && (
            <Card>
              <CardHeader>
                <CardTitle>Your assigned profiles</CardTitle>
                <CardDescription>
                  These are the only LinkedIn profiles and campaigns visible in this workspace.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {profiles.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No profiles are assigned to you yet. Ask a workspace owner or admin.
                  </p>
                )}
                {profiles.map((profile) => (
                  <div key={profile.profile_id} className="flex items-center justify-between rounded-md border border-border/60 p-3 text-sm">
                    <span className="truncate font-medium">
                      {profile.linkedin_username || profile.profile_id}
                    </span>
                    <div className="flex items-center gap-2">
                      <Badge variant={profile.active ? "default" : "secondary"}>
                        {profile.active ? "Active" : "Paused"}
                      </Badge>
                      {profile.proxy_assigned && (
                        <Badge variant="outline">
                          {profile.proxy_mode === "managed" ? "Managed proxy" : "BYO proxy"}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {canManage && (
            <SeatAssignmentCard
              orgId={orgId}
              members={members}
              profiles={profiles}
              canManage={canManage}
              onChanged={() => {
                void load();
                void refetchBilling();
              }}
            />
          )}

          {canManage && auditEvents.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Recent organization activity</CardTitle>
                <CardDescription>Every invite, role, and seat mutation is audited.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {auditEvents.map((event) => (
                  <div key={event.id} className="flex items-center justify-between gap-3 border-b border-border/40 pb-2 last:border-0">
                    <span className="font-mono text-xs">{event.event}</span>
                    <span className="truncate text-xs text-muted-foreground">
                      {event.target_email || event.target_user_id || "—"}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {event.created_at ? new Date(event.created_at).toLocaleString() : ""}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
