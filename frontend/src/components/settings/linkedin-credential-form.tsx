"use client";

import { useState, useEffect, useRef } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/components/ui/use-toast";
import { Icons } from "@/lib/types/components";
import { Cloud, Monitor, Shield } from "lucide-react";
import VncViewer from "./vnc-viewer";
import { useBilling } from "@/lib/contexts/billing-context";
import {
  confirmLinkedInCredentials,
  createLinkedInCredentials,
  deleteLinkedInCredentials,
  updateLinkedInCredentials,
  verifyLinkedInCredentials,
  type CreateLinkedInCredentialsData,
  type LinkedInCredentials,
} from "@/lib/api/dashboard";

const credentialSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type CredentialFormValues = z.infer<typeof credentialSchema>;

interface CredentialFormProps {
  initialData?: LinkedInCredentials;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export default function LinkedInCredentialForm({
  initialData,
  onSuccess,
  onCancel,
}: CredentialFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showChallengeModal, setShowChallengeModal] = useState(false);
  const [challengeCredentialId, setChallengeCredentialId] = useState<number | null>(null);
  const [challengeProfileId, setChallengeProfileId] = useState<string | null>(null);
  const [executionMode, setExecutionMode] = useState<"desktop" | "cloud">(
    initialData?.executionMode ?? "desktop"
  );
  const { toast } = useToast();
  const countdownRef = useRef<NodeJS.Timeout | null>(null);
  const { billingStatus } = useBilling();
  const hasCloudAddon = (billingStatus?.cloud_profiles ?? 0) > 0;

  useEffect(() => {
    if (isSubmitting) {
      setCountdown(60);
      countdownRef.current = setInterval(() => {
        setCountdown((c) => (c > 0 ? c - 1 : 0));
      }, 1000);
    } else {
      setCountdown(0);
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
    }
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [isSubmitting]);

  const form = useForm<CredentialFormValues>({
    resolver: zodResolver(credentialSchema),
    defaultValues: {
      email: initialData?.publicEmail.replace(/\*\*\*/g, "") || "",
      password: "",
    },
  });

  const onSubmit = async (values: CredentialFormValues) => {
    let createdCredentialId: number | null = null;

    try {
      setIsSubmitting(true);
      setError(null);
      setSuccess(false);

      // 1. Save credentials
      const formData: CreateLinkedInCredentialsData = {
        email: values.email,
        password: values.password,
        execution_mode: executionMode,
      };

      let credentialId = initialData?.id ?? null;
      let response;

      if (initialData) {
        response = await updateLinkedInCredentials(initialData.id, formData);
      } else {
        response = await createLinkedInCredentials(formData);
      }

      if (!response.data) {
        throw new Error(response.error || "Failed to save credentials");
      }

      credentialId = response.data.id;
      if (!initialData) createdCredentialId = credentialId;

      // 2. Verify immediately — desktop mode: just mark stored, daemon does real login
      const verifyResp = await verifyLinkedInCredentials(credentialId, {
        testLogin: executionMode !== "desktop",
      });
      const verifyData = verifyResp.data as {
        success?: boolean;
        error?: string;
        details?: { errorType?: string; message?: string };
        credentials?: LinkedInCredentials;
      } | undefined;

      if (verifyData?.success) {
        toast({
          title: "Credentials verified",
          description: "LinkedIn credentials are valid and active",
        });
        setSuccess(true);
        if (onSuccess) onSuccess();
        return;
      }

      // 3. Check if challenge — open VNC modal
      const errorType = verifyData?.details?.errorType;
      if (errorType === "awaiting_challenge") {
        setChallengeCredentialId(credentialId);
        // Get profile ID from the credentials response
        const profileId = verifyData?.credentials?.linkedinProfileId?.toString() || null;
        setChallengeProfileId(profileId);
        setShowChallengeModal(true);
        return;
      }

      // 4. Other failure
      throw new Error(
        verifyData?.error ||
          verifyData?.details?.message ||
          verifyResp.error ||
          "Verification failed",
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Verification failed";
      const isNetworkError = message.includes("fetch") || message.includes("network") || message.includes("timeout") || message.includes("CORS");

      if (isNetworkError) {
        setError("Verification is taking longer than expected. Check the credential card status — it may still complete.");
        toast({
          title: "Connection issue",
          description: "The verification may still be in progress. Check the credential card status in a moment.",
          variant: "default",
        });
        if (onSuccess) onSuccess();
      } else {
        setError(message);
        toast({
          title: "Verification failed",
          description: message,
          variant: "destructive",
        });

        if (createdCredentialId) {
          try {
            await deleteLinkedInCredentials(createdCredentialId);
          } catch {
            // Ignore cleanup failures.
          }
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmChallenge = async () => {
    if (!challengeCredentialId) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const resp = await confirmLinkedInCredentials(challengeCredentialId);
      const data = resp.data as {
        success?: boolean;
        error?: string;
        details?: { errorType?: string; message?: string };
      } | undefined;

      if (data?.success) {
        setShowChallengeModal(false);
        toast({
          title: "Credentials verified",
          description: "LinkedIn challenge completed successfully",
        });
        setSuccess(true);
        if (onSuccess) onSuccess();
      } else {
        const errType = data?.details?.errorType;
        if (errType === "challenge_incomplete") {
          toast({
            title: "Not done yet",
            description: "Complete the challenge in the browser viewer first, then click Confirm again.",
            variant: "default",
          });
        } else {
          setShowChallengeModal(false);
          setError(data?.error || resp.error || "Challenge confirmation failed");
        }
      }
    } catch (err) {
      setShowChallengeModal(false);
      setError(err instanceof Error ? err.message : "Challenge confirmation failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {error ? (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {success ? (
        <Alert className="border-emerald-800/80 bg-emerald-950/70 text-emerald-100">
          <Icons.CheckCircle className="h-4 w-4 text-emerald-400" />
          <AlertDescription>
            Account verified successfully. Lengrowth will use this account.
          </AlertDescription>
        </Alert>
      ) : null}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(280px,1fr)]">
            <div className="space-y-6">
              <Card className="border-zinc-800/80 bg-zinc-950/50 shadow-none">
                <CardContent className="space-y-5 pt-6">
                  <div className="space-y-1">
                    <h3 className="text-base font-semibold text-zinc-100">
                      LinkedIn login
                    </h3>
                    <p className="text-sm text-zinc-400">
                      Enter the LinkedIn email and password. If LinkedIn asks for
                      a verification code, you&apos;ll see the browser and can enter
                      it directly.
                    </p>
                  </div>

                  <Separator className="bg-zinc-800/80" />

                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>LinkedIn Email</FormLabel>
                        <FormControl>
                          <div className="flex">
                            <div className="flex items-center justify-center rounded-l-md border border-r-0 border-zinc-800 bg-zinc-900 px-3">
                              <Icons.Mail className="h-4 w-4 text-zinc-400" />
                            </div>
                            <Input
                              placeholder="name@company.com"
                              type="email"
                              {...field}
                              className="rounded-l-none border-zinc-800 bg-zinc-950/70"
                            />
                          </div>
                        </FormControl>
                        <FormDescription>
                          The email address you use to log into LinkedIn.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Password</FormLabel>
                        <FormControl>
                          <div className="flex">
                            <div className="flex items-center justify-center rounded-l-md border border-r-0 border-zinc-800 bg-zinc-900 px-3">
                              <Icons.Lock className="h-4 w-4 text-zinc-400" />
                            </div>
                            <div className="relative flex-1">
                              <Input
                                placeholder="••••••••"
                                type={showPassword ? "text" : "password"}
                                {...field}
                                className="rounded-l-none border-zinc-800 bg-zinc-950/70 pr-11"
                              />
                              <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute inset-y-0 right-0 flex items-center px-3 text-zinc-400 transition hover:text-zinc-100"
                                aria-label={showPassword ? "Hide password" : "Show password"}
                              >
                                {showPassword ? (
                                  <Icons.EyeOff className="h-4 w-4" />
                                ) : (
                                  <Icons.Eye className="h-4 w-4" />
                                )}
                              </button>
                            </div>
                          </div>
                        </FormControl>
                        <FormDescription>
                          Stored encrypted at rest and used for LinkedIn login.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              {hasCloudAddon && (
                <Card className="border-zinc-800/80 bg-zinc-950/50 shadow-none">
                  <CardContent className="pt-6">
                    <h3 className="mb-3 text-sm font-semibold text-zinc-100">Execution Mode</h3>
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => setExecutionMode("desktop")}
                        className={`flex flex-1 items-center gap-2 rounded-lg border px-4 py-3 text-sm transition-colors ${
                          executionMode === "desktop"
                            ? "border-blue-500/60 bg-blue-500/10 text-blue-300"
                            : "border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700"
                        }`}
                      >
                        <Monitor className="h-4 w-4 shrink-0" />
                        <div className="text-left">
                          <div className="font-medium">Desktop</div>
                          <div className="text-xs opacity-70">Your computer · Free</div>
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={() => setExecutionMode("cloud")}
                        className={`flex flex-1 items-center gap-2 rounded-lg border px-4 py-3 text-sm transition-colors ${
                          executionMode === "cloud"
                            ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-300"
                            : "border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700"
                        }`}
                      >
                        <Cloud className="h-4 w-4 shrink-0" />
                        <div className="text-left">
                          <div className="font-medium">Cloud</div>
                          <div className="text-xs opacity-70">Managed by Lengrowth · $299/mo</div>
                        </div>
                      </button>
                    </div>
                  </CardContent>
                </Card>
              )}

              <div className="flex flex-wrap items-center justify-end gap-3 border-t border-zinc-800/80 pt-6">
                <div className="flex flex-wrap items-center gap-3">
                  {onCancel ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={onCancel}
                      disabled={isSubmitting}
                      className="border-zinc-800 bg-zinc-950 text-zinc-100 hover:bg-zinc-900"
                    >
                      Cancel
                    </Button>
                  ) : null}

                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <>
                        <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                        Validating{countdown > 0 ? ` in ${countdown}s` : ""}...
                      </>
                    ) : (
                      <>
                        <Icons.Activity className="mr-2 h-4 w-4" />
                        {initialData ? "Save & Verify" : "Add & Verify"}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
              <Card className="border-zinc-800/80 bg-zinc-950/50 shadow-none">
                <CardContent className="pt-6">
                  <h3 className="flex items-center text-sm font-semibold text-zinc-100">
                    <Icons.Lock className="mr-2 h-4 w-4 text-zinc-400" />
                    Security
                  </h3>
                  <div className="mt-4 space-y-3 text-sm text-zinc-400">
                    <div className="flex items-start">
                      <Icons.CheckCircle className="mr-2 mt-0.5 h-3 w-3 text-green-500/80" />
                      <span>Password is encrypted at rest.</span>
                    </div>
                    <div className="flex items-start">
                      <Icons.CheckCircle className="mr-2 mt-0.5 h-3 w-3 text-green-500/80" />
                      <span>Credential values are not shown back in full.</span>
                    </div>
                    <div className="flex items-start">
                      <Icons.CheckCircle className="mr-2 mt-0.5 h-3 w-3 text-green-500/80" />
                      <span>Your login session is kept securely on Lengrowth — never stored in your browser.</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-zinc-800/80 bg-zinc-950/50 shadow-none">
                <CardContent className="pt-6">
                  <h3 className="flex items-center text-sm font-semibold text-zinc-100">
                    <Icons.Info className="mr-2 h-4 w-4 text-zinc-400" />
                    How it works
                  </h3>
                  <ul className="mt-4 space-y-3 text-sm text-zinc-400">
                    <li className="flex items-start">
                      <Icons.CheckCircle className="mr-2 mt-0.5 h-3 w-3 text-blue-400/80" />
                      <span>
                        Lengrowth logs into LinkedIn on your behalf using the details you provide.
                      </span>
                    </li>
                    <li className="flex items-start">
                      <Icons.CheckCircle className="mr-2 mt-0.5 h-3 w-3 text-blue-400/80" />
                      <span>
                        If LinkedIn sends a verification code, a live browser
                        viewer opens so you can enter it.
                      </span>
                    </li>
                    <li className="flex items-start">
                      <Icons.CheckCircle className="mr-2 mt-0.5 h-3 w-3 text-blue-400/80" />
                      <span>
                        Once verified, Lengrowth handles everything automatically — your personal browser is never touched.
                      </span>
                    </li>
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>
        </form>
      </Form>

      <Dialog open={showChallengeModal} onOpenChange={setShowChallengeModal}>
        {executionMode === "cloud" ? (
          <DialogContent className="max-w-[95vw] h-[90vh] border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl flex flex-col p-0">
            <DialogHeader className="p-6 pb-4 border-b border-zinc-800">
              <DialogTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-amber-500" />
                Complete LinkedIn Verification
              </DialogTitle>
              <DialogDescription className="space-y-2">
                <p>LinkedIn sent a verification code to your email. Complete it below:</p>
                <ol className="list-decimal list-inside space-y-1 text-sm">
                  <li>Check your email for the LinkedIn verification code</li>
                  <li>Enter the code in the browser viewer below</li>
                  <li>Once you see the LinkedIn feed, click &quot;Confirm Login&quot;</li>
                </ol>
              </DialogDescription>
            </DialogHeader>
            <div className="flex-1 overflow-hidden min-h-0">
              <VncViewer
                profileId={challengeProfileId || undefined}
                embedded
              />
            </div>
            <div className="flex items-center justify-between gap-2 p-4 border-t border-zinc-800 bg-zinc-950/80">
              <p className="text-sm text-zinc-400">
                Enter the code, wait for the feed to load, then confirm
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setShowChallengeModal(false)}
                  className="border-zinc-700 hover:bg-zinc-900"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleConfirmChallenge}
                  disabled={isSubmitting}
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {isSubmitting ? (
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
        ) : (
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
              <Alert className="border-amber-500/40 bg-amber-500/10">
                <AlertDescription className="text-amber-300 text-sm">
                  The desktop app opened LinkedIn in your browser to complete the challenge.
                  Check your default browser or LinkedIn app to finish verification.
                </AlertDescription>
              </Alert>
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
                Cancel
              </Button>
              <Button
                onClick={handleConfirmChallenge}
                disabled={isSubmitting}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                {isSubmitting ? (
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
        )}
      </Dialog>
    </div>
  );
}
