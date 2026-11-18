"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createTeamInvite, type TeamInvite } from "@/lib/api/team";

interface InviteMemberFormProps {
  orgId: string;
  canInviteAdmins: boolean;
  onInvited: () => void;
}

export function InviteMemberForm({ orgId, canInviteAdmins, onInvited }: InviteMemberFormProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "member">("member");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<TeamInvite | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setCreated(null);
    try {
      const response = await createTeamInvite(orgId, email.trim(), role);
      if (response.error) {
        setError(response.error);
        return;
      }
      setEmail("");
      if (response.data) setCreated(response.data);
      onInvited();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invite a member</CardTitle>
        <CardDescription>
          They join this workspace and inherit the owner&apos;s plan. Assign cloud profiles after they accept.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="invite-email">Email</Label>
            <Input
              id="invite-email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="teammate@company.com"
            />
          </div>
          <div className="w-full space-y-1.5 sm:w-40">
            <Label>Role</Label>
            <Select value={role} onValueChange={(value) => setRole(value as "admin" | "member")}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="member">Member</SelectItem>
                {canInviteAdmins && <SelectItem value="admin">Admin</SelectItem>}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" disabled={loading || !email.trim()}>
            {loading ? "Sending…" : "Send invite"}
          </Button>
        </form>
        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        {created && (
          <div className="mt-3 rounded-md border border-border/60 bg-muted/40 p-3 text-sm">
            <p>
              Invitation created for <strong>{created.email}</strong>.
              {created.email_sent ? " An email was sent." : " Email delivery is not configured."}
            </p>
            {created.debug_invite_url && (
              <p className="mt-1 break-all text-xs text-muted-foreground">
                Dev invite link: {created.debug_invite_url}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
