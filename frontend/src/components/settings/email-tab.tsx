"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Icons } from "@/lib/types/components";
import {
  createMailbox,
  deleteMailbox,
  listMailboxes,
  testMailbox,
  unpauseMailbox,
  updateMailbox,
  type Mailbox,
  type MailboxCreate,
} from "@/lib/api/mailboxes";
import { getSettings, updateSettings } from "@/lib/api/dashboard";

const GMAIL_APP_PASSWORD_URL =
  "https://support.google.com/accounts/answer/185833";

function EditMailboxModal({
  box,
  onUpdated,
}: {
  box: Mailbox;
  onUpdated: (updated: Mailbox) => void;
}) {
  const [open, setOpen] = useState(false);
  const [fromName, setFromName] = useState(box.fromName);
  const [dailyLimit, setDailyLimit] = useState(String(box.dailyLimit));
  const [imapHost, setImapHost] = useState(box.imapHost);
  const [imapPort, setImapPort] = useState(String(box.imapPort));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateMailbox(box.id, {
        fromName,
        dailyLimit: parseInt(dailyLimit) || 40,
        imapHost,
        imapPort: parseInt(imapPort) || 993,
      });
      onUpdated(updated);
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update mailbox");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        <Icons.Settings className="h-4 w-4" />
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit mailbox</DialogTitle>
            <DialogDescription>{box.fromAddress || box.username}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label htmlFor="edit-fromname">Display name</Label>
                <Input
                  id="edit-fromname"
                  value={fromName}
                  onChange={(e) => setFromName(e.target.value)}
                  placeholder="John Smith"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="edit-limit">Daily send limit</Label>
                <Input
                  id="edit-limit"
                  type="number"
                  min={1}
                  max={500}
                  value={dailyLimit}
                  onChange={(e) => setDailyLimit(e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 rounded-md border p-3">
              <div className="col-span-2 space-y-1">
                <Label htmlFor="edit-imap-host">IMAP host</Label>
                <Input
                  id="edit-imap-host"
                  value={imapHost}
                  onChange={(e) => setImapHost(e.target.value)}
                  placeholder="imap.gmail.com"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="edit-imap-port">Port</Label>
                <Input
                  id="edit-imap-port"
                  value={imapPort}
                  onChange={(e) => setImapPort(e.target.value)}
                  placeholder="993"
                />
              </div>
            </div>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function MailboxRow({
  box,
  onDelete,
  onUnpause,
  onUpdated,
}: {
  box: Mailbox;
  onDelete: (id: string) => void;
  onUnpause: (updated: Mailbox) => void;
  onUpdated: (updated: Mailbox) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [unpausing, setUnpausing] = useState(false);

  const handleDelete = async () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    await deleteMailbox(box.id);
    onDelete(box.id);
  };

  const handleUnpause = async () => {
    setUnpausing(true);
    try {
      const updated = await unpauseMailbox(box.id);
      onUnpause(updated);
    } finally {
      setUnpausing(false);
    }
  };

  return (
    <div className={`flex items-center justify-between rounded-lg border p-4 ${box.paused ? "border-destructive/40 bg-destructive/5" : ""}`}>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{box.fromAddress || box.username}</span>
          {box.fromName && (
            <span className="text-sm text-muted-foreground">
              ({box.fromName})
            </span>
          )}
          {box.paused && (
            <Badge variant="destructive" className="text-xs">
              Paused
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span>
            {box.host}:{box.port}
          </span>
          <span>·</span>
          <span>
            {box.sentToday}/{box.dailyLimit} sent today
          </span>
          {!box.paused && (
            <Badge
              variant={box.headroomToday > 0 ? "default" : "secondary"}
              className="text-xs"
            >
              {box.headroomToday > 0 ? `${box.headroomToday} left` : "Capped"}
            </Badge>
          )}
          {box.imapHost && (
            <>
              <span>·</span>
              <span className="flex items-center gap-1">
                <Icons.Inbox className="h-3 w-3" />
                IMAP
              </span>
            </>
          )}
        </div>
        {box.paused && (
          <p className="text-xs text-destructive">
            Auth failure detected. Fix credentials and unpause to resume sends.
          </p>
        )}
      </div>
      <div className="flex items-center gap-2">
        {box.paused && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleUnpause}
            disabled={unpausing}
          >
            {unpausing ? (
              <Icons.RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Icons.Play className="h-4 w-4" />
            )}
            Unpause
          </Button>
        )}
        <EditMailboxModal box={box} onUpdated={onUpdated} />
        <Button
          variant={confirming ? "destructive" : "ghost"}
          size="sm"
          onClick={handleDelete}
          onBlur={() => setConfirming(false)}
        >
          <Icons.Trash2 className="h-4 w-4" />
          {confirming ? "Confirm" : ""}
        </Button>
      </div>
    </div>
  );
}

interface FormState {
  host: string;
  port: string;
  username: string;
  password: string;
  fromName: string;
  dailyLimit: string;
  imapHost: string;
  imapPort: string;
}

const DEFAULT_FORM: FormState = {
  host: "smtp.gmail.com",
  port: "587",
  username: "",
  password: "",
  fromName: "",
  dailyLimit: "40",
  imapHost: "",
  imapPort: "993",
};

function AddMailboxModal({ onAdded }: { onAdded: (box: Mailbox) => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [showPassword, setShowPassword] = useState(false);
  const [showImap, setShowImap] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set =
    (field: keyof FormState) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      setTestResult(null);
      setError(null);
    };

  const isGmail = form.host.includes("gmail");

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const result = await testMailbox(
        form.host,
        parseInt(form.port) || 587,
        form.username,
        form.password,
      );
      setTestResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const data: MailboxCreate = {
        host: form.host,
        port: parseInt(form.port) || 587,
        username: form.username,
        password: form.password,
        fromName: form.fromName,
        dailyLimit: parseInt(form.dailyLimit) || 40,
        imapHost: showImap ? form.imapHost : "",
        imapPort: showImap ? parseInt(form.imapPort) || 993 : 993,
      };
      const box = await createMailbox(data);
      onAdded(box);
      setOpen(false);
      setForm(DEFAULT_FORM);
      setTestResult(null);
      setShowImap(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save mailbox");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <Icons.Plus className="mr-2 h-4 w-4" />
        Add mailbox
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add SMTP mailbox</DialogTitle>
          <DialogDescription>
            Connect any Gmail, Outlook, or custom SMTP inbox for cold outreach.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2 space-y-1">
              <Label htmlFor="mb-host">SMTP host</Label>
              <Input
                id="mb-host"
                value={form.host}
                onChange={set("host")}
                placeholder="smtp.gmail.com"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="mb-port">Port</Label>
              <Input
                id="mb-port"
                value={form.port}
                onChange={set("port")}
                placeholder="587"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="mb-username">Email address</Label>
            <Input
              id="mb-username"
              type="email"
              value={form.username}
              onChange={set("username")}
              placeholder="you@gmail.com"
            />
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <Label htmlFor="mb-password">
                {isGmail ? "App password" : "Password"}
              </Label>
              {isGmail && (
                <a
                  href={GMAIL_APP_PASSWORD_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-muted-foreground hover:text-foreground underline"
                >
                  How to get an app password
                </a>
              )}
            </div>
            <div className="relative">
              <Input
                id="mb-password"
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={set("password")}
                placeholder={isGmail ? "16-char app password" : "password"}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPassword ? (
                  <Icons.EyeOff className="h-4 w-4" />
                ) : (
                  <Icons.Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label htmlFor="mb-fromname">Display name (optional)</Label>
              <Input
                id="mb-fromname"
                value={form.fromName}
                onChange={set("fromName")}
                placeholder="John Smith"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="mb-limit">Daily send limit</Label>
              <Input
                id="mb-limit"
                type="number"
                min={1}
                max={500}
                value={form.dailyLimit}
                onChange={set("dailyLimit")}
              />
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowImap((v) => !v)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <Icons.Inbox className="h-3 w-3" />
            {showImap ? "Hide" : "Add"} IMAP settings (reply detection)
          </button>

          {showImap && (
            <div className="grid grid-cols-3 gap-2 rounded-md border p-3">
              <div className="col-span-2 space-y-1">
                <Label htmlFor="mb-imap-host">IMAP host</Label>
                <Input
                  id="mb-imap-host"
                  value={form.imapHost}
                  onChange={set("imapHost")}
                  placeholder="imap.gmail.com"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="mb-imap-port">Port</Label>
                <Input
                  id="mb-imap-port"
                  value={form.imapPort}
                  onChange={set("imapPort")}
                  placeholder="993"
                />
              </div>
            </div>
          )}

          {testResult && (
            <Alert variant={testResult.ok ? "default" : "destructive"}>
              <AlertDescription className="flex items-center gap-2">
                {testResult.ok ? (
                  <Icons.Check className="h-4 w-4 text-green-500" />
                ) : (
                  <Icons.AlertCircle className="h-4 w-4" />
                )}
                {testResult.message}
              </AlertDescription>
            </Alert>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={handleTest}
            disabled={!form.username || !form.password || testing}
          >
            {testing ? (
              <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Icons.Lock className="mr-2 h-4 w-4" />
            )}
            Test connection
          </Button>
          <Button
            onClick={handleSave}
            disabled={
              !form.username ||
              !form.password ||
              saving ||
              (testResult !== null && !testResult.ok)
            }
          >
            {saving && (
              <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save mailbox
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
}

function SequenceConfigForm() {
  const [day1, setDay1] = useState(3);
  const [day2, setDay2] = useState(7);
  const [velocity, setVelocity] = useState(10);
  const [acceptUnverified, setAcceptUnverified] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void (async () => {
      const res = await getSettings();
      if (res.data?.email) {
        setDay1(res.data.email.followupDay1);
        setDay2(res.data.email.followupDay2);
        if (res.data.email.velocity != null) setVelocity(res.data.email.velocity);
        if (res.data.email.acceptUnverified != null) setAcceptUnverified(res.data.email.acceptUnverified);
      }
    })();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await updateSettings({ email: { followupDay1: day1, followupDay2: day2, velocity, acceptUnverified } });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icons.Clock className="h-5 w-5" />
          Sequence timing &amp; pacing
        </CardTitle>
        <CardDescription>
          Days between each email in the 3-step sequence, and send rate (emails per hour).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-1">
            <Label htmlFor="seq-day1">Follow-up 1 (days after step 0)</Label>
            <Input
              id="seq-day1"
              type="number"
              min={1}
              max={30}
              value={day1}
              onChange={(e) => setDay1(Math.max(1, parseInt(e.target.value) || 1))}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="seq-day2">Follow-up 2 (days after step 0)</Label>
            <Input
              id="seq-day2"
              type="number"
              min={1}
              max={60}
              value={day2}
              onChange={(e) => setDay2(Math.max(1, parseInt(e.target.value) || 1))}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="seq-velocity">Send rate (emails / hour)</Label>
            <Input
              id="seq-velocity"
              type="number"
              min={1}
              max={200}
              value={velocity}
              onChange={(e) => setVelocity(Math.max(1, parseInt(e.target.value) || 1))}
            />
          </div>
        </div>
        <div className="flex items-start gap-3 rounded-md border p-3">
          <input
            id="accept-unverified"
            type="checkbox"
            checked={acceptUnverified}
            onChange={(e) => setAcceptUnverified(e.target.checked)}
            className="mt-0.5 h-4 w-4 cursor-pointer"
          />
          <div className="space-y-0.5">
            <Label htmlFor="accept-unverified" className="cursor-pointer">
              Send to pattern-only addresses
            </Label>
            <p className="text-xs text-muted-foreground">
              When SMTP verification is inconclusive (catch-all domain or port 25 blocked),
              send to the most likely email pattern anyway. Increases reach but may raise bounce rate.
            </p>
          </div>
        </div>
        <Button onClick={handleSave} disabled={saving} size="sm">
          {saving ? (
            <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          ) : saved ? (
            <Icons.Check className="mr-2 h-4 w-4" />
          ) : null}
          {saved ? "Saved" : "Save"}
        </Button>
      </CardContent>
    </Card>
  );
}

export function EmailTab() {
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setMailboxes(await listMailboxes());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load mailboxes");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleAdded = (box: Mailbox) => setMailboxes((prev) => [...prev, box]);
  const handleDeleted = (id: string) =>
    setMailboxes((prev) => prev.filter((b) => b.id !== id));
  const handleUnpaused = (updated: Mailbox) =>
    setMailboxes((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
  const handleUpdated = (updated: Mailbox) =>
    setMailboxes((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));

  return (
    <div className="space-y-6">
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Icons.Mail className="h-5 w-5" />
              Email mailboxes
            </CardTitle>
            <CardDescription>
              Connect SMTP inboxes for cold email outreach. Bring your own
              Gmail, Outlook, or custom SMTP — no extra cost.
            </CardDescription>
          </div>
          <AddMailboxModal onAdded={handleAdded} />
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icons.RefreshCw className="h-4 w-4 animate-spin" />
            Loading mailboxes...
          </div>
        ) : error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : mailboxes.length === 0 ? (
          <div className="rounded-lg border border-dashed p-8 text-center">
            <Icons.Mail className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
            <p className="font-medium">No mailboxes configured</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Email outreach is disabled until you add at least one mailbox.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {mailboxes.map((box) => (
              <MailboxRow key={box.id} box={box} onDelete={handleDeleted} onUnpause={handleUnpaused} onUpdated={handleUpdated} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
    <SequenceConfigForm />
    </div>
  );
}
