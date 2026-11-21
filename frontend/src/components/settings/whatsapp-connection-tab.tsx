"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
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
  getWhatsAppProfile,
  resetQr,
  type WhatsAppCloudMode,
  type WhatsAppProfile,
} from "@/lib/api/whatsapp";
import {
  getLinkedInProfiles,
  type LinkedInProfile,
} from "@/lib/api/dashboard";
import { useBilling } from "@/lib/contexts/billing-context";
import { Cloud, MessageCircle, Monitor, Phone, Trash2, RefreshCw } from "lucide-react";

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
        const profile = await getWhatsAppProfile(profileId);
        if (!profile) return; // 404 or auth error — keep polling
        if (profile.status === "connected") {
          onConnected();
          stopPolling();
          return;
        }
        if (profile.qrDataUrl) {
          setQrSrc(profile.qrDataUrl);
        } else {
          // QR not ready yet — extend deadline so we keep waiting
          deadlineRef.current = Math.max(deadlineRef.current, Date.now() + 30_000);
        }
      } catch {
        // transient error - keep polling
      }
    };

    void doPoll();
    intervalRef.current = setInterval(doPoll, 2000);
  }, [profileId, onConnected]);

  useEffect(() => {
    startPolling();
    return stopPolling;
  }, [startPolling]);

  const handleRefresh = async () => {
    setResetting(true);
    try {
      await resetQr(profileId);
    } catch {
      // best-effort - daemon will regenerate anyway
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
      <Image
        src={qrSrc}
        alt="WhatsApp QR code"
        width={192}
        height={192}
        unoptimized
        className="h-48 w-48 rounded border object-contain"
      />
    </div>
  );
}

function executionLabel(profile: WhatsAppProfile): string {
  if (profile.executionMode !== "cloud") {
    return "Desktop · Local IP · No proxy";
  }
  const region = profile.proxyRegionCountry
    ? ` · ${profile.proxyRegionCountry}`
    : "";
  if (profile.cloudMode === "duo_shared") {
    return `Cloud Duo · Shared IP · Managed proxy${region}`;
  }
  if (profile.cloudMode === "duo_separate") {
    return `Cloud Duo · Separate IP · Managed proxy${region}`;
  }
  return `WhatsApp-only cloud · Managed proxy${region}`;
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
        <p className="text-xs text-muted-foreground">
          {executionLabel(profile)}
        </p>
        {profile.executionMode === "cloud" && (
          <p className="text-xs">
            {profile.proxyCountryMismatch ? (
              <span className="text-destructive">Proxy country mismatch</span>
            ) : profile.proxyLastError ? (
              <span className="text-destructive">Proxy issue: {profile.proxyLastError}</span>
            ) : profile.proxyMassiveStatus &&
              ["disabled", "error", "retired", "budget_disabled"].includes(
                profile.proxyMassiveStatus,
              ) ? (
              <span className="text-destructive">
                Proxy {profile.proxyMassiveStatus}
              </span>
            ) : profile.proxyStatus &&
              ["disabled", "error", "retired"].includes(profile.proxyStatus) ? (
              <span className="text-destructive">
                Proxy {profile.proxyStatus}
              </span>
            ) : profile.proxyId ? (
              <span className="text-emerald-600">Managed proxy healthy</span>
            ) : (
              <span className="text-destructive">Proxy required</span>
            )}
          </p>
        )}
      </CardHeader>

      {profile.status === "disconnected" && (
        <CardContent>
          {profile.executionMode === "cloud" && !profile.active ? (
            <p className="text-xs text-muted-foreground">
              This cloud seat is paused. Ask a workspace owner or admin to
              assign it; the proxy stays reserved.
            </p>
          ) : showQr ? (
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
  const { billingStatus } = useBilling();
  const cloudEnabled =
    billingStatus?.whatsapp_cloud_proxy_enabled === true &&
    (billingStatus?.cloud_seat_limit ?? 0) > 0;
  const [executionMode, setExecutionMode] = useState<"desktop" | "cloud">("desktop");
  const [cloudMode, setCloudMode] = useState<Exclude<WhatsAppCloudMode, "desktop">>(
    "duo_shared",
  );
  const [duoProfileId, setDuoProfileId] = useState("");
  const [regionCountry, setRegionCountry] = useState("US");
  const [regionSubdivision, setRegionSubdivision] = useState("");
  const [regionCity, setRegionCity] = useState("");
  const [cloudProfiles, setCloudProfiles] = useState<LinkedInProfile[]>([]);

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

  useEffect(() => {
    if (!cloudEnabled) return;
    void getLinkedInProfiles()
      .then((response) => {
        const eligible = (response.data?.profiles ?? []).filter(
          (profile) =>
            profile.execution_mode === "cloud" &&
            profile.active !== false &&
            profile.proxy_mode === "managed",
        );
        setCloudProfiles(eligible);
      })
      .catch(() => setCloudProfiles([]));
  }, [cloudEnabled]);

  const handleAdd = async () => {
    if (executionMode === "cloud") {
      if (
        (cloudMode === "duo_shared" || cloudMode === "duo_separate") &&
        !duoProfileId
      ) {
        setError("Select the cloud LinkedIn profile this WhatsApp number belongs to.");
        return;
      }
      if (
        (cloudMode === "whatsapp_only" || cloudMode === "duo_separate") &&
        !regionCountry.trim()
      ) {
        setError("Choose the proxy country for this WhatsApp number.");
        return;
      }
    }
    setAdding(true);
    setError(null);
    try {
      const profile = await createWhatsAppProfile(undefined, {
        executionMode,
        cloudMode: executionMode === "cloud" ? cloudMode : "desktop",
        duoLinkedInProfileId:
          executionMode === "cloud" &&
          (cloudMode === "duo_shared" || cloudMode === "duo_separate")
            ? duoProfileId
            : undefined,
        proxyRegionCountry:
          executionMode === "cloud" &&
          (cloudMode === "whatsapp_only" || cloudMode === "duo_separate")
            ? regionCountry
            : undefined,
        proxyRegionSubdivision:
          executionMode === "cloud" &&
          (cloudMode === "whatsapp_only" || cloudMode === "duo_separate")
            ? regionSubdivision || undefined
            : undefined,
        proxyRegionCity:
          executionMode === "cloud" &&
          (cloudMode === "whatsapp_only" || cloudMode === "duo_separate")
            ? regionCity || undefined
            : undefined,
      });
      setProfiles((prev) => [...prev, profile]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create WhatsApp connection.");
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
        <CardContent className="space-y-4">
          {cloudEnabled && (
            <div className="space-y-3 rounded-lg border border-border/60 p-3">
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={executionMode === "desktop" ? "default" : "outline"}
                  onClick={() => setExecutionMode("desktop")}
                >
                  <Monitor className="mr-2 h-4 w-4" />
                  Desktop
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={executionMode === "cloud" ? "default" : "outline"}
                  onClick={() => setExecutionMode("cloud")}
                >
                  <Cloud className="mr-2 h-4 w-4" />
                  Cloud Duo
                </Button>
              </div>
              {executionMode === "cloud" ? (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <label
                      htmlFor="wa-cloud-mode"
                      className="text-xs font-medium text-muted-foreground"
                    >
                      Cloud setup
                    </label>
                    <select
                      id="wa-cloud-mode"
                      value={cloudMode}
                      onChange={(event) =>
                        setCloudMode(
                          event.target.value as Exclude<WhatsAppCloudMode, "desktop">,
                        )
                      }
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                    >
                      <option value="duo_shared">
                        Cloud Duo · Shared IP (use the LinkedIn proxy)
                      </option>
                      <option value="duo_separate">
                        Cloud Duo · Separate IP (own WhatsApp proxy)
                      </option>
                      <option value="whatsapp_only">
                        WhatsApp-only cloud (own seat and proxy)
                      </option>
                    </select>
                  </div>
                  {(cloudMode === "duo_shared" || cloudMode === "duo_separate") && (
                    <div className="space-y-2">
                      <label
                        htmlFor="duo-linkedin-profile"
                        className="text-xs font-medium text-muted-foreground"
                      >
                        Cloud LinkedIn profile
                      </label>
                      <select
                        id="duo-linkedin-profile"
                        value={duoProfileId}
                        onChange={(event) => setDuoProfileId(event.target.value)}
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                      >
                        <option value="">Select a cloud profile…</option>
                        {cloudProfiles.map((profile) => (
                          <option key={profile.id} value={String(profile.id)}>
                            {profile.linkedinUsername}
                          </option>
                        ))}
                      </select>
                      {cloudProfiles.length === 0 && (
                        <p className="text-xs text-destructive">
                          Add a cloud LinkedIn account with a managed proxy first.
                        </p>
                      )}
                    </div>
                  )}
                  {cloudMode === "duo_shared" ? (
                    <p className="text-xs text-muted-foreground">
                      One seat, one shared proxy. The WhatsApp number uses the
                      same client identity and egress IP as the LinkedIn account.
                    </p>
                  ) : cloudMode === "duo_separate" ? (
                    <p className="text-xs text-muted-foreground">
                      One seat, two proxies. WhatsApp gets its own sub-account
                      and usage line while the seat stays shared.
                    </p>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      WhatsApp-only cloud consumes its own seat and managed
                      proxy. No LinkedIn account is required.
                    </p>
                  )}
                  {(cloudMode === "whatsapp_only" || cloudMode === "duo_separate") && (
                    <div className="grid gap-2 sm:grid-cols-3">
                      <div className="space-y-1">
                        <label
                          htmlFor="wa-region-country"
                          className="text-xs font-medium text-muted-foreground"
                        >
                          Country (ISO-2)
                        </label>
                        <input
                          id="wa-region-country"
                          value={regionCountry}
                          onChange={(event) =>
                            setRegionCountry(event.target.value.toUpperCase())
                          }
                          maxLength={2}
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        />
                      </div>
                      <div className="space-y-1">
                        <label
                          htmlFor="wa-region-subdivision"
                          className="text-xs font-medium text-muted-foreground"
                        >
                          State (optional)
                        </label>
                        <input
                          id="wa-region-subdivision"
                          value={regionSubdivision}
                          onChange={(event) =>
                            setRegionSubdivision(event.target.value.toUpperCase())
                          }
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        />
                      </div>
                      <div className="space-y-1">
                        <label
                          htmlFor="wa-region-city"
                          className="text-xs font-medium text-muted-foreground"
                        >
                          City (optional)
                        </label>
                        <input
                          id="wa-region-city"
                          value={regionCity}
                          onChange={(event) => setRegionCity(event.target.value)}
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        />
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Cloud numbers never use the server IP. A missing or unhealthy
                    proxy pauses the session instead of falling back.
                  </p>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Desktop runs on your computer with the local IP and no proxy.
                </p>
              )}
            </div>
          )}
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
