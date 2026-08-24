"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/lib/auth-store";
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
  listWhatsAppProfiles,
  createWhatsAppProfile,
  deleteWhatsAppProfile,
  getQrUrl,
  resetQr,
  type WhatsAppProfile,
} from "@/lib/api/whatsapp";
import { MessageCircle, Phone, Trash2, RefreshCw } from "lucide-react";
import { LimitCheckWrapper } from "@/components/billing/limit-check-wrapper";

const STATUS_LABELS: Record<string, string> = {
  connected: "Connected",
  disconnected: "Disconnected",
  banned: "Banned",
};

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive"> = {
  connected: "default",
  disconnected: "secondary",
  banned: "destructive",
};

function QrPoller({ profileId, onConnected }: { profileId: string; onConnected: () => void }) {
  const [qrSrc, setQrSrc] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const [resetting, setResetting] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const deadlineRef = useRef(Date.now() + 120_000);
  const token = useAuthStore((state) => state.token);

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const startPolling = useCallback(() => {
    stopPolling();
    deadlineRef.current = Date.now() + 120_000;
    setTimedOut(false);
    setQrSrc(null);

    const doPoll = async () => {
      if (Date.now() > deadlineRef.current) {
        setTimedOut(true);
        stopPolling();
        return;
      }
      try {
        const url = getQrUrl(profileId);
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch(`${url}?t=${Date.now()}`, { headers });
        if (res.status === 202) {
          deadlineRef.current = Math.max(deadlineRef.current, Date.now() + 30_000);
          return;
        }
        if (res.ok) {
          const contentType = res.headers.get("content-type") ?? "";
          if (contentType.includes("image")) {
            const blob = await res.blob();
            setQrSrc(URL.createObjectURL(blob));
          } else {
            onConnected();
            stopPolling();
          }
        }
        if (res.status === 404) stopPolling();
      } catch {
        // transient error — keep polling
      }
    };

    void doPoll();
    intervalRef.current = setInterval(doPoll, 2000);
  }, [profileId, onConnected, token]);

  useEffect(() => {
    startPolling();
    return stopPolling;
  }, [startPolling]);

  const handleRefresh = async () => {
    setResetting(true);
    try {
      await resetQr(profileId);
    } catch {
      // best-effort — daemon will regenerate anyway
    } finally {
      setResetting(false);
    }
    startPolling();
  };

  if (timedOut) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">QR code expired.</p>
        <Button variant="outline" size="sm" onClick={() => void handleRefresh()} disabled={resetting}>
          {resetting ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
          Refresh QR
        </Button>
      </div>
    );
  }

  if (!qrSrc) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <RefreshCw className="h-4 w-4 animate-spin" />
        Generating QR code…
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Open WhatsApp on your phone → Linked Devices → Link a device, then scan:
      </p>
      <img
        src={qrSrc}
        alt="WhatsApp QR code"
        className="h-48 w-48 rounded border object-contain"
      />
    </div>
  );
}

function ProfileCard({
  profile,
  onDelete,
  onRefresh,
}: {
  profile: WhatsAppProfile;
  onDelete: (id: string) => void;
  onRefresh?: () => void;
}) {
  const [showQr, setShowQr] = useState(profile.status === "disconnected");
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteWhatsAppProfile(profile.id);
      onDelete(profile.id);
    } catch {
      setDeleting(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Phone className="h-4 w-4 text-green-500" />
            <CardTitle className="text-base">
              {profile.phoneNumber || profile.displayName || "New WhatsApp number"}
            </CardTitle>
            <Badge variant={STATUS_VARIANTS[profile.status] ?? "secondary"}>
              {STATUS_LABELS[profile.status] ?? profile.status}
            </Badge>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleDelete}
            disabled={deleting}
            className="h-8 w-8 text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
        {profile.displayName && profile.phoneNumber && (
          <CardDescription>{profile.displayName}</CardDescription>
        )}
      </CardHeader>

      {profile.status === "disconnected" && (
        <CardContent>
          {showQr ? (
            <QrPoller profileId={profile.id} onConnected={() => { setShowQr(false); onRefresh?.(); }} />
          ) : (
            <Button variant="outline" size="sm" onClick={() => setShowQr(true)}>
              Show QR code
            </Button>
          )}
        </CardContent>
      )}

      {profile.status === "connected" && profile.lastSeen && (
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Last seen {new Date(profile.lastSeen).toLocaleString()}
          </p>
        </CardContent>
      )}
    </Card>
  );
}

export function WhatsappConnectionTab() {
  const [profiles, setProfiles] = useState<WhatsAppProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listWhatsAppProfiles();
      setProfiles(data);
    } catch {
      setError("Failed to load WhatsApp connections.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async () => {
    setAdding(true);
    try {
      const profile = await createWhatsAppProfile();
      setProfiles((prev) => [...prev, profile]);
    } catch {
      setError("Failed to create WhatsApp connection.");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = (id: string) => {
    setProfiles((prev) => prev.filter((p) => p.id !== id));
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-green-500" />
            <CardTitle>WhatsApp Connections</CardTitle>
          </div>
          <CardDescription>
            Connect WhatsApp numbers to send outreach messages via WhatsApp Web.
            Each number requires a QR scan from your phone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <LimitCheckWrapper limitType="whatsapp_accounts">
            <Button onClick={handleAdd} disabled={adding} size="sm">
              {adding ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Creating…
                </>
              ) : (
                <>
                  <Phone className="mr-2 h-4 w-4" />
                  Connect new number
                </>
              )}
            </Button>
          </LimitCheckWrapper>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : profiles.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No WhatsApp numbers connected yet. Click &ldquo;Connect new number&rdquo; to start.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {profiles.map((p) => (
            <ProfileCard key={p.id} profile={p} onDelete={handleDelete} onRefresh={load} />
          ))}
        </div>
      )}
    </div>
  );
}
