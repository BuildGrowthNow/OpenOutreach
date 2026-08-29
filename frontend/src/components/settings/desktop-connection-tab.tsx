"use client";

import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { getLinkedInProfiles, type LinkedInProfile } from "@/lib/api/dashboard";
import { listMailboxes, type Mailbox } from "@/lib/api/mailboxes";
import { apiClient } from "@/lib/apiClientV2";

type EnrollmentResponse = {
  code: string;
  expires_at: string;
};

export function DesktopConnectionTab() {
  const [linkedin, setLinkedin] = useState<LinkedInProfile[]>([]);
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [selectedLinkedIn, setSelectedLinkedIn] = useState<string[]>([]);
  const [selectedMailboxes, setSelectedMailboxes] = useState<string[]>([]);
  const [code, setCode] = useState<EnrollmentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([getLinkedInProfiles(), listMailboxes()])
      .then(([profiles, boxes]) => {
        setLinkedin(profiles.data?.profiles ?? []);
        setMailboxes(boxes);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Failed to load profiles"))
      .finally(() => setLoading(false));
  }, []);

  const toggle = (value: string, current: string[], update: (values: string[]) => void) => {
    update(current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);
  };

  const createCode = async () => {
    if (!selectedLinkedIn.length && !selectedMailboxes.length) {
      setError("Select at least one LinkedIn profile or mailbox.");
      return;
    }
    setCreating(true);
    setError(null);
    const bindings: Record<string, string[]> = {};
    if (selectedLinkedIn.length) bindings.linkedin = selectedLinkedIn;
    if (selectedMailboxes.length) bindings.email = selectedMailboxes;
    const response = await apiClient.post<EnrollmentResponse>("/daemon/v2/enrollment-codes", {
      profile_ids: [...selectedLinkedIn, ...selectedMailboxes],
      channels: Object.keys(bindings),
      channel_profile_ids: bindings,
      device_name: "Lengrowth desktop",
    });
    setCreating(false);
    if (!response.data) {
      setError(response.error ?? "Could not create an enrollment code");
      return;
    }
    setCode(response.data);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Connect this desktop</CardTitle>
        <CardDescription>
          Choose the accounts this desktop may run. The one-time code expires after ten minutes and is shown only here.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        {loading ? <p className="text-sm text-muted-foreground">Loading owned profiles…</p> : (
          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-3">
              <Label>LinkedIn profiles</Label>
              {linkedin.length ? linkedin.map((profile) => {
                const id = String(profile.id);
                return <label key={id} className="flex items-center gap-2 text-sm">
                  <Checkbox checked={selectedLinkedIn.includes(id)} onCheckedChange={() => toggle(id, selectedLinkedIn, setSelectedLinkedIn)} />
                  {profile.linkedinUsername || id}
                </label>;
              }) : <p className="text-sm text-muted-foreground">No LinkedIn profiles connected.</p>}
            </div>
            <div className="space-y-3">
              <Label>Email mailboxes</Label>
              {mailboxes.length ? mailboxes.map((mailbox) => <label key={mailbox.id} className="flex items-center gap-2 text-sm">
                <Checkbox checked={selectedMailboxes.includes(mailbox.id)} onCheckedChange={() => toggle(mailbox.id, selectedMailboxes, setSelectedMailboxes)} />
                {mailbox.fromAddress || mailbox.username}
              </label>) : <p className="text-sm text-muted-foreground">No mailboxes connected.</p>}
            </div>
          </div>
        )}
        <Button onClick={() => void createCode()} disabled={loading || creating}>
          {creating ? "Creating code…" : "Create desktop code"}
        </Button>
        {code && <div className="rounded-lg border bg-muted/30 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Enter this code in the desktop app</p>
          <p className="my-2 font-mono text-2xl tracking-[0.25em]">{code.code}</p>
          <p className="text-xs text-muted-foreground">Expires {new Date(code.expires_at).toLocaleTimeString()}</p>
        </div>}
      </CardContent>
    </Card>
  );
}
