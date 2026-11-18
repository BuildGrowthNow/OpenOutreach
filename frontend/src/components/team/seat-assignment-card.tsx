"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  assignSeat,
  removeSeat,
  unassignSeat,
  type OrgProfile,
  type TeamMember,
} from "@/lib/api/team";

interface SeatAssignmentCardProps {
  orgId: string;
  members: TeamMember[];
  profiles: OrgProfile[];
  canManage: boolean;
  onChanged: () => void;
}

export function SeatAssignmentCard({
  orgId,
  members,
  profiles,
  canManage,
  onChanged,
}: SeatAssignmentCardProps) {
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const handleAssign = async (profile: OrgProfile) => {
    const userId = selected[profile.profile_id];
    if (!userId) return;
    setBusy(profile.profile_id);
    try {
      const response = await assignSeat(orgId, profile.profile_id, userId);
      if (response.error) {
        window.alert(response.error);
        return;
      }
      onChanged();
    } finally {
      setBusy(null);
    }
  };

  const handleUnassign = async (profile: OrgProfile, remove: boolean) => {
    const label = remove ? "Remove" : "Unassign";
    if (!window.confirm(`${label} this seat? The profile pauses and keeps its proxy assigned.`)) {
      return;
    }
    setBusy(profile.profile_id);
    try {
      const response = remove
        ? await removeSeat(orgId, profile.profile_id)
        : await unassignSeat(orgId, profile.profile_id);
      if (response.error) {
        window.alert(response.error);
        return;
      }
      onChanged();
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cloud seats</CardTitle>
        <CardDescription>
          Assign a cloud LinkedIn profile to one member. Removing a seat pauses the profile and keeps its proxy.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {profiles.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No cloud profiles in this workspace yet.
          </p>
        )}
        {profiles.map((profile) => {
          const assigned = members.find((member) => member.user_id === profile.assigned_user_id);
          const value = selected[profile.profile_id] ?? profile.assigned_user_id ?? "";
          return (
            <div
              key={profile.profile_id}
              className="flex flex-col gap-3 rounded-lg border border-border/60 p-3 lg:flex-row lg:items-center lg:justify-between"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate text-sm font-medium">
                    {profile.linkedin_username || profile.profile_id}
                  </span>
                  <Badge variant={profile.active ? "default" : "secondary"}>
                    {profile.active ? "Active" : "Paused"}
                  </Badge>
                  {profile.proxy_assigned && (
                    <Badge variant="outline">Managed proxy</Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {assigned ? `Assigned to ${assigned.email}` : "Unassigned"}
                </p>
              </div>
              {canManage && (
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <select
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={value}
                    onChange={(event) =>
                      setSelected((current) => ({
                        ...current,
                        [profile.profile_id]: event.target.value,
                      }))
                    }
                  >
                    <option value="">Select member…</option>
                    {members.map((member) => (
                      <option key={member.user_id} value={member.user_id}>
                        {member.full_name || member.email}
                      </option>
                    ))}
                  </select>
                  <Button
                    size="sm"
                    disabled={busy === profile.profile_id || !value || value === profile.assigned_user_id}
                    onClick={() => void handleAssign(profile)}
                  >
                    Assign
                  </Button>
                  {profile.assigned_user_id && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy === profile.profile_id}
                        onClick={() => void handleUnassign(profile, false)}
                      >
                        Unassign
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={busy === profile.profile_id}
                        onClick={() => void handleUnassign(profile, true)}
                      >
                        Remove seat
                      </Button>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
