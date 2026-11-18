"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { removeTeamMember, updateMemberRole, type TeamMember } from "@/lib/api/team";

interface TeamMembersCardProps {
  orgId: string;
  members: TeamMember[];
  currentUserId: string;
  canManage: boolean;
  canChangeRoles: boolean;
  onChanged: () => void;
}

export function TeamMembersCard({
  orgId,
  members,
  currentUserId,
  canManage,
  canChangeRoles,
  onChanged,
}: TeamMembersCardProps) {
  const handleRole = async (userId: string, role: "admin" | "member") => {
    const response = await updateMemberRole(orgId, userId, role);
    if (response.error) {
      window.alert(response.error);
      return;
    }
    onChanged();
  };

  const handleRemove = async (member: TeamMember) => {
    if (!window.confirm(`Remove ${member.email} from this workspace? Their assigned profiles will pause.`)) {
      return;
    }
    const response = await removeTeamMember(orgId, member.user_id);
    if (response.error) {
      window.alert(response.error);
      return;
    }
    onChanged();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Members</CardTitle>
        <CardDescription>
          Owners and admins manage seats. Members only see profiles assigned to them.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {members.length === 0 && (
          <p className="text-sm text-muted-foreground">No members yet.</p>
        )}
        {members.map((member) => {
          const isOwner = member.role === "owner";
          const isSelf = member.user_id === currentUserId;
          return (
            <div
              key={member.user_id}
              className="flex flex-col gap-3 rounded-lg border border-border/60 p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">
                    {member.full_name || member.email}
                  </span>
                  {isSelf && <Badge variant="outline">You</Badge>}
                  <Badge variant={isOwner ? "default" : "secondary"} className="capitalize">
                    {member.role}
                  </Badge>
                </div>
                <p className="truncate text-xs text-muted-foreground">{member.email}</p>
              </div>
              {canManage && !isOwner && (
                <div className="flex items-center gap-2">
                  {canChangeRoles && (
                    <Select
                      value={member.role}
                      onValueChange={(value) => void handleRole(member.user_id, value as "admin" | "member")}
                    >
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="member">Member</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                  {!isSelf && (
                    <Button variant="outline" size="sm" onClick={() => void handleRemove(member)}>
                      Remove
                    </Button>
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
