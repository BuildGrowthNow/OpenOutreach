"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Logo } from "@/components/ui/logo";
import { Icons } from "@/lib/types/components";
import { useAuthStore } from "@/lib/authStoreV2";
import { useBilling } from "@/lib/contexts/billing-context";
import { acceptTeamInvite, previewTeamInvite, type InvitePreview } from "@/lib/api/team";

export default function AcceptTeamInvitePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const { isAuthenticated, isInitialized, initialize } = useAuthStore();
  const { refetch: refetchBilling } = useBilling();
  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("This invitation link is missing its token.");
      setLoading(false);
      return;
    }
    let cancelled = false;
    void previewTeamInvite(token)
      .then((response) => {
        if (cancelled) return;
        if (response.error) setError(response.error);
        else setPreview(response.data ?? null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!isInitialized) void initialize();
  }, [isInitialized, initialize]);

  const handleAccept = async () => {
    setAccepting(true);
    setError(null);
    try {
      const response = await acceptTeamInvite(token);
      if (response.error) {
        setError(response.error);
        return;
      }
      await initialize();
      // Refresh the workspace billing context before the dashboard mounts so
      // team pages do not briefly query the old personal organization.
      await refetchBilling();
      router.push("/dashboard");
    } finally {
      setAccepting(false);
    }
  };

  const returnUrl = `/team/accept?token=${encodeURIComponent(token)}`;

  return (
    <div className="dark min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-3">
          <Logo variant="dark" iconSize={36} className="text-lg" />
          <CardTitle>Join workspace</CardTitle>
          <CardDescription>
            Accept this invitation to see the LinkedIn profiles and campaigns assigned to you.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading && (
            <div className="space-y-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-64" />
            </div>
          )}

          {preview && (
            <div className="rounded-lg border border-border/60 p-4 text-sm">
              <p className="text-base font-semibold">{preview.org_name}</p>
              <p className="text-muted-foreground">{preview.email}</p>
              <div className="mt-2 flex items-center gap-2">
                <Badge variant="secondary" className="capitalize">{preview.role}</Badge>
                <span className="text-xs text-muted-foreground">
                  Expires {new Date(preview.expires_at).toLocaleString()}
                </span>
              </div>
            </div>
          )}

          {error && (
            <Alert variant="destructive">
              <Icons.AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {preview && isAuthenticated && (
            <Button className="w-full" onClick={() => void handleAccept()} disabled={accepting}>
              {accepting ? "Joining…" : "Accept invitation"}
            </Button>
          )}

          {preview && !isAuthenticated && isInitialized && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Sign in with <strong>{preview.email}</strong> to accept. If you do not have an account,
                create one with this email.
              </p>
              <Button asChild className="w-full">
                <Link href={`/login?returnUrl=${encodeURIComponent(returnUrl)}`}>Sign in</Link>
              </Button>
              <Button asChild variant="outline" className="w-full">
                <Link
                  href={`/signup?invite_token=${encodeURIComponent(token)}&email=${encodeURIComponent(preview.email)}`}
                >
                  Create account
                </Link>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
