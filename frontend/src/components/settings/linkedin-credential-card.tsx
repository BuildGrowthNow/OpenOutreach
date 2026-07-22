"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Icons } from "@/lib/types/components";
import { AlertCircle, Shield } from "lucide-react";
import {
  type LinkedInCredentials,
  confirmLinkedInCredentials,
  verifyLinkedInCredentials,
  deleteLinkedInCredentials,
  getLinkedInCredentialsHealth,
  getLinkedInCredentialsLogs,
  type LinkedInCredentialsHealth,
  type LinkedInCredentialsLogsResponse,
} from "@/lib/api/dashboard";
import { useToast } from "@/components/ui/use-toast";
import LinkedInCredentialForm from "./linkedin-credential-form";
import VncViewer from "./vnc-viewer";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface LinkedInCredentialCardProps {
  credential: LinkedInCredentials;
  onRefresh: () => void;
}

interface HealthStatusWithDetails {
  errorDetails?: { message?: string; code?: string };
  details?: { errorMessage?: string; reason?: string };
  healthScore?: number;
  daysUntilExpiry?: number | null;
  daysSinceRotation?: number;
  verificationFailures?: number;
  lastVerified?: string | null;
  lastUsed?: string | null;
}

function formatTimestamp(value?: string | null): string | null {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date.toLocaleString();
}

function getDisplayUsername(username?: string | null): string {
  const trimmed = username?.trim();
  if (!trimmed) {
    return "Profile not available";
  }
  return trimmed.startsWith("@") ? trimmed : `@${trimmed}`;
}

function getStatusColor(status: LinkedInCredentials["status"]): string {
  switch (status) {
    case "active":
      return "bg-emerald-500";
    case "stored":
      return "bg-sky-500";
    case "tested":
      return "bg-blue-500";
    case "invalid":
      return "bg-red-500";
    case "expired":
      return "bg-amber-500";
    case "locked":
      return "bg-zinc-500";
    case "backup":
      return "bg-violet-500";
    default:
      return "bg-zinc-500";
  }
}

function getStatusLabel(status: LinkedInCredentials["status"]): string {
  switch (status) {
    case "stored":
      return "Stored";
    case "tested":
      return "Tested";
    case "active":
      return "Active";
    case "invalid":
      return "Invalid";
    case "expired":
      return "Expired";
    case "locked":
      return "Locked";
    case "backup":
      return "Backup";
    default:
      return status;
  }
}

export default function LinkedInCredentialCard({
  credential,
  onRefresh,
}: LinkedInCredentialCardProps) {
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showHealthDetails, setShowHealthDetails] = useState(false);
  const [healthData, setHealthData] = useState<
    LinkedInCredentialsHealth["healthStatus"] | null
  >(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [logsData, setLogsData] = useState<
    LinkedInCredentialsLogsResponse["logs"] | null
  >(null);
  const [isLoadingLogs, setIsLoadingLogs] = useState(false);
  const [isLoadingHealth, setIsLoadingHealth] = useState(false);
  const [showChallengeModal, setShowChallengeModal] = useState(false);
  const { toast } = useToast();

  const healthStatus: HealthStatusWithDetails =
    credential.healthStatus && typeof credential.healthStatus === "object"
      ? (credential.healthStatus as HealthStatusWithDetails)
      : {};

  const errorMessage =
    healthStatus.errorDetails?.message ||
    healthStatus.details?.errorMessage ||
    healthStatus.details?.reason ||
    null;

  const handleVerify = async () => {
    try {
      setIsVerifying(true);

      const response = await verifyLinkedInCredentials(credential.id);
      const data = response.data as {
        success?: boolean;
        error?: string;
        details?: { errorType?: string; message?: string };
      } | undefined;

      if (data?.success) {
        toast({
          title: "Success",
          description: "Credentials verified successfully",
        });
        onRefresh();
        setHealthData(null);
        setShowHealthDetails(false);
      } else if (data?.details?.errorType === "awaiting_challenge") {
        setShowChallengeModal(true);
      } else {
        toast({
          title: "Error",
          description: data?.error || response.error || "Failed to verify credentials",
          variant: "destructive",
        });
      }
    } catch (err) {
      toast({
        title: "Error",
        description: err instanceof Error ? err.message : "An unexpected error occurred",
        variant: "destructive",
      });
    } finally {
      setIsVerifying(false);
    }
  };

  const handleDelete = async () => {
    if (
      !confirm(
        "Are you sure you want to delete this credential? This will remove the saved LinkedIn login from this profile.",
      )
    ) {
      return;
    }

    try {
      setIsDeleting(true);
      const response = await deleteLinkedInCredentials(credential.id);

      if (response.data) {
        toast({
          title: "Success",
          description: "Credential deleted successfully",
        });
        onRefresh();
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to delete credential",
          variant: "destructive",
        });
      }
    } catch (err) {
      toast({
        title: "Error",
        description:
          err instanceof Error ? err.message : "An unexpected error occurred",
        variant: "destructive",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggleHealth = async () => {
    if (showHealthDetails) {
      setShowHealthDetails(false);
      return;
    }

    if (healthData) {
      setShowHealthDetails(true);
      return;
    }

    try {
      setIsLoadingHealth(true);
      const response = await getLinkedInCredentialsHealth(credential.id);
      if (response.data) {
        setHealthData(response.data.healthStatus);
        setShowHealthDetails(true);
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to load health details",
          variant: "destructive",
        });
      }
    } catch (err) {
      toast({
        title: "Error",
        description:
          err instanceof Error ? err.message : "Failed to load health details",
        variant: "destructive",
      });
    } finally {
      setIsLoadingHealth(false);
    }
  };

  const handleLoadLogs = async () => {
    try {
      setIsLoadingLogs(true);
      const response = await getLinkedInCredentialsLogs(credential.id);
      if (response.data) {
        setLogsData(response.data.logs);
        setShowLogsDialog(true);
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to load logs",
          variant: "destructive",
        });
      }
    } catch (err) {
      toast({
        title: "Error",
        description: err instanceof Error ? err.message : "Failed to load logs",
        variant: "destructive",
      });
    } finally {
      setIsLoadingLogs(false);
    }
  };

  const displayUsername = getDisplayUsername(credential.username);
  const displayEmail = credential.publicEmail?.trim() || "Email not available";
  const lastVerified = formatTimestamp(
    healthData?.lastVerified ?? credential.lastVerified,
  );
  const lastUsed = formatTimestamp(healthData?.lastUsed ?? credential.lastUsed);
  const statusLabel = getStatusLabel(credential.status);

  return (
    <Card className="border-zinc-800/80 bg-zinc-950/40 shadow-none">
      <CardContent className="pt-6">
        <div className="flex flex-col space-y-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex items-start space-x-4">
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-full ${credential.isPrimary ? "bg-primary text-primary-foreground" : "bg-zinc-800 text-zinc-100"}`}
              >
                <Icons.User className="h-6 w-6" />
              </div>
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-zinc-100">
                    {displayUsername}
                  </span>
                  {credential.isPrimary ? (
                    <span className="rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
                      Primary
                    </span>
                  ) : null}
                  {credential.isBackup ? (
                    <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-xs text-violet-300 border border-violet-500/30">
                      Backup
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-400">
                  <Icons.Mail className="h-3.5 w-3.5" />
                  <span>{displayEmail}</span>
                  <span className="text-zinc-600">•</span>
                  <span
                    className={`h-2 w-2 rounded-full ${getStatusColor(credential.status)}`}
                  />
                  <span className="text-zinc-300">{statusLabel}</span>
                </div>
              </div>
            </div>
            <div className="text-left lg:text-right">
              <div className="text-sm font-medium text-zinc-100">
                {healthStatus.healthScore ?? "—"}/100 Health Score
              </div>
              <div className="mt-1 text-xs text-zinc-400">
                {credential.usageCount} actions used
              </div>
            </div>
          </div>

          {showHealthDetails && healthData ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-zinc-400">Days Until Expiry</span>
                <span className="text-zinc-100">
                  {healthData.daysUntilExpiry !== null
                    ? healthData.daysUntilExpiry
                    : "Unknown"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-zinc-400">Days Since Rotation</span>
                <span className="text-zinc-100">
                  {healthData.daysSinceRotation}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-zinc-400">Verification Failures</span>
                <span
                  className={
                    (healthData.verificationFailures ?? 0) > 0
                      ? "text-red-400"
                      : "text-emerald-400"
                  }
                >
                  {healthData.verificationFailures}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-zinc-400">Last Verified</span>
                <span className="text-zinc-100">
                  {lastVerified ?? "Not available"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-zinc-400">Last Used</span>
                <span className="text-zinc-100">
                  {lastUsed ?? "Not available"}
                </span>
              </div>
            </div>
          ) : null}

          {credential.status === "invalid" ||
          credential.status === "locked" ||
          credential.status === "expired" ? (
            <div className="rounded-xl border border-zinc-700/80 bg-zinc-950/80 p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-4 w-4 text-red-400" />
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-zinc-100">
                      Credential needs attention
                    </div>
                    <span className="rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-xs text-red-300">
                      {statusLabel}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-300">
                    This LinkedIn login is not currently usable. You can
                    re-verify it, edit it, or delete it.
                  </p>
                  {errorMessage ? (
                    <div className="rounded-lg border border-zinc-700/80 bg-zinc-900/80 p-3 text-sm text-zinc-200">
                      {errorMessage}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          <div className="mt-2 flex flex-wrap gap-2">
            {credential.status === "locked" ? (
              <Button
                variant="default"
                size="sm"
                onClick={() => setShowChallengeModal(true)}
                className="bg-amber-500 hover:bg-amber-600 text-zinc-900"
              >
                <Shield className="mr-2 h-3 w-3" />
                Complete Challenge
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={handleVerify}
                disabled={isVerifying}
              >
                {isVerifying ? (
                  <>
                    <Icons.RefreshCw className="mr-2 h-3 w-3 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  <>
                    <Icons.RefreshCw className="mr-2 h-3 w-3" />
                    Verify
                  </>
                )}
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowEditDialog(true)}
              disabled={isVerifying || isDeleting}
            >
              <Icons.Edit className="mr-2 h-3 w-3" />
              Edit
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleToggleHealth}
              disabled={isLoadingHealth}
            >
              <Icons.Activity className="mr-2 h-3 w-3" />
              {isLoadingHealth
                ? "Loading..."
                : showHealthDetails
                  ? "Hide Details"
                  : "View Details"}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleLoadLogs}
              disabled={isLoadingLogs}
            >
              <Icons.FileText className="mr-2 h-3 w-3" />
              {isLoadingLogs ? "Loading..." : "View Logs"}
            </Button>

            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              <Icons.Trash2 className="mr-2 h-3 w-3" />
              Delete
            </Button>
          </div>
        </div>

        <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
          <DialogContent className="max-w-3xl border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl">
            <DialogHeader>
              <DialogTitle>Edit LinkedIn Credential</DialogTitle>
              <DialogDescription>
                Update your LinkedIn account credentials.
              </DialogDescription>
            </DialogHeader>
            <LinkedInCredentialForm
              initialData={credential}
              onSuccess={() => {
                setShowEditDialog(false);
                onRefresh();
                toast({
                  title: "Success",
                  description: "Credential updated successfully",
                });
              }}
              onCancel={() => setShowEditDialog(false)}
            />
          </DialogContent>
        </Dialog>

        <Dialog open={showLogsDialog} onOpenChange={setShowLogsDialog}>
          <DialogContent className="max-h-[80vh] max-w-3xl overflow-y-auto border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl">
            <DialogHeader>
              <DialogTitle>Credential Audit Logs</DialogTitle>
              <DialogDescription>
                History of actions performed on this credential.
              </DialogDescription>
            </DialogHeader>
            <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-2">
              {logsData && logsData.length > 0 ? (
                logsData.map((log) => (
                  <div
                    key={log.id}
                    className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-950/70 p-4"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="font-medium capitalize text-zinc-100">
                        {log.action.replaceAll("_", " ")}
                      </div>
                      <span className="text-xs text-zinc-400">
                        {formatTimestamp(log.createdAt) ?? "Date not available"}
                      </span>
                    </div>
                    {log.details && Object.keys(log.details).length > 0 ? (
                      <div className="rounded-lg border border-zinc-800 bg-zinc-900/80 p-3 text-xs font-mono text-zinc-100">
                        <pre className="whitespace-pre-wrap break-words text-zinc-100">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      </div>
                    ) : null}
                    {log.ipAddress ? (
                      <div className="text-xs text-zinc-400">
                        IP: {log.ipAddress}
                      </div>
                    ) : null}
                  </div>
                ))
              ) : (
                <div className="py-8 text-center text-zinc-400">
                  <Icons.FileText className="mx-auto mb-2 h-10 w-10 opacity-20" />
                  <p>No logs found for this credential</p>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={showChallengeModal} onOpenChange={setShowChallengeModal}>
          {credential.executionMode !== "cloud" ? (
            <DialogContent className="max-w-lg border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-amber-500" />
                  LinkedIn Challenge Detected
                </DialogTitle>
                <DialogDescription>
                  LinkedIn requires additional verification on your computer.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-300">
                  The desktop app opened LinkedIn in your browser to complete the challenge.
                  Check your default browser or LinkedIn app to finish verification.
                </div>
                <ol className="space-y-2 text-sm text-zinc-300">
                  <li className="flex gap-2"><span className="text-zinc-500">1.</span>Complete the CAPTCHA or enter the verification code in your browser.</li>
                  <li className="flex gap-2"><span className="text-zinc-500">2.</span>Wait until you see the LinkedIn feed page.</li>
                  <li className="flex gap-2"><span className="text-zinc-500">3.</span>Come back here and click &quot;Confirm Login&quot;.</li>
                </ol>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => setShowChallengeModal(false)}
                  className="border-zinc-700 hover:bg-zinc-900"
                >
                  Close
                </Button>
                <Button
                  onClick={async () => {
                    setIsVerifying(true);
                    try {
                      const resp = await confirmLinkedInCredentials(credential.id);
                      const data = resp.data as { success?: boolean; error?: string; details?: { errorType?: string } } | undefined;
                      if (data?.success) {
                        setShowChallengeModal(false);
                        toast({ title: "Success", description: "Credentials verified successfully" });
                        onRefresh();
                      } else if (data?.details?.errorType === "challenge_incomplete") {
                        toast({ title: "Not done yet", description: "Complete the challenge first, then click Confirm again." });
                      } else {
                        setShowChallengeModal(false);
                        toast({ title: "Error", description: data?.error || "Confirmation failed", variant: "destructive" });
                      }
                    } catch (err) {
                      setShowChallengeModal(false);
                      toast({ title: "Error", description: err instanceof Error ? err.message : "Confirmation failed", variant: "destructive" });
                    } finally {
                      setIsVerifying(false);
                    }
                  }}
                  disabled={isVerifying}
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {isVerifying ? (
                    <>
                      <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      Checking...
                    </>
                  ) : (
                    <>
                      <Icons.CheckCircle className="mr-2 h-4 w-4" />
                      Confirm Login
                    </>
                  )}
                </Button>
              </div>
            </DialogContent>
          ) : (
            <DialogContent className="max-w-[95vw] h-[90vh] border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl flex flex-col p-0">
              <DialogHeader className="p-6 pb-4 border-b border-zinc-800">
                <DialogTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-amber-500" />
                  Complete LinkedIn Challenge
                </DialogTitle>
                <DialogDescription className="space-y-2">
                  <p>LinkedIn requires additional verification. Follow these steps:</p>
                  <ol className="list-decimal list-inside space-y-1 text-sm">
                    <li>Complete the CAPTCHA or security challenge in the browser viewer below</li>
                    <li>Wait for LinkedIn to redirect you to the feed page</li>
                    <li>Click &quot;Confirm Login&quot; to verify your credentials</li>
                  </ol>
                </DialogDescription>
              </DialogHeader>
              <div className="flex-1 overflow-hidden min-h-0">
                <VncViewer
                  profileId={String(credential.linkedinProfileId || "")}
                  embedded
                />
              </div>
              <div className="flex items-center justify-between gap-2 p-4 border-t border-zinc-800 bg-zinc-950/80">
                <p className="text-sm text-zinc-400">
                  Complete the challenge, then confirm your login
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setShowChallengeModal(false)}
                    className="border-zinc-700 hover:bg-zinc-900"
                  >
                    Close
                  </Button>
                  <Button
                    onClick={async () => {
                      setIsVerifying(true);
                      try {
                        const resp = await confirmLinkedInCredentials(credential.id);
                        const data = resp.data as { success?: boolean; error?: string; details?: { errorType?: string } } | undefined;
                        if (data?.success) {
                          setShowChallengeModal(false);
                          toast({ title: "Success", description: "Credentials verified successfully" });
                          onRefresh();
                        } else if (data?.details?.errorType === "challenge_incomplete") {
                          toast({ title: "Not done yet", description: "Complete the challenge first, then click Confirm again." });
                        } else {
                          setShowChallengeModal(false);
                          toast({ title: "Error", description: data?.error || "Confirmation failed", variant: "destructive" });
                        }
                      } catch (err) {
                        setShowChallengeModal(false);
                        toast({ title: "Error", description: err instanceof Error ? err.message : "Confirmation failed", variant: "destructive" });
                      } finally {
                        setIsVerifying(false);
                      }
                    }}
                    disabled={isVerifying}
                    className="bg-emerald-600 hover:bg-emerald-700"
                  >
                    {isVerifying ? (
                      <>
                        <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                        Checking...
                      </>
                    ) : (
                      <>
                        <Icons.CheckCircle className="mr-2 h-4 w-4" />
                        Confirm Login
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </DialogContent>
          )}
        </Dialog>
      </CardContent>
    </Card>
  );
}
