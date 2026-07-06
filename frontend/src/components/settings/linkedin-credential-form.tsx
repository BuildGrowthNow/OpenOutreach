"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { Icons } from "@/lib/types/components";
import { post } from "@/lib/api";
import {
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
  cookie_data: z.string().optional(),
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
  const [isTesting, setIsTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showOptionalCookie, setShowOptionalCookie] = useState(false);
  const { toast } = useToast();

  const form = useForm<CredentialFormValues>({
    resolver: zodResolver(credentialSchema),
    defaultValues: {
      email: initialData?.publicEmail.replace(/\*\*\*/g, "") || "",
      password: "",
      cookie_data: "",
    },
  });

  const uploadCookie = async (profileId: number, cookieData: string) => {
    const data = await post<{ success?: boolean; message?: string }>(
      `/api/linkedin-profiles/${profileId}/cookies/`,
      { cookie_data: cookieData },
    );
    return data.data?.message || "Cookie saved";
  };

  const ensureProfileId = async (
    credentialId: number,
    fallbackProfileId?: number | null,
  ) => {
    if (fallbackProfileId) {
      return fallbackProfileId;
    }

    const verifyResp = await verifyLinkedInCredentials(credentialId);
    const verifyData = verifyResp.data as
      | {
          success?: boolean;
          details?: { message?: string };
          credentials: LinkedInCredentials;
        }
      | undefined;

    if (!verifyData?.success) {
      throw new Error(
        verifyResp.error ||
          verifyData?.details?.message ||
          "Verification failed while preparing cookie upload",
      );
    }

    return verifyData.credentials.linkedinProfileId ?? null;
  };

  const submitCredential = async (
    values: CredentialFormValues,
    {
      verifyAfterSave,
      onCreated,
    }: { verifyAfterSave: boolean; onCreated?: (credentialId: number) => void },
  ) => {
    const cookieData = values.cookie_data?.trim() || "";
    const formData: CreateLinkedInCredentialsData = {
      email: values.email,
      password: values.password,
    };

    let credentialId = initialData?.id ?? null;
    let profileId = initialData?.linkedinProfileId ?? null;
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
    profileId = response.data.credentials.linkedinProfileId ?? profileId;

    if (!initialData) {
      onCreated?.(credentialId);
    }

    if (verifyAfterSave) {
      profileId = await ensureProfileId(credentialId, profileId);
    }

    if (cookieData) {
      profileId = await ensureProfileId(credentialId, profileId);
      if (!profileId) {
        throw new Error(
          "Cookie could not be saved because no LinkedIn profile is linked yet",
        );
      }
      const cookieMessage = await uploadCookie(profileId, cookieData);
      form.setValue("cookie_data", "");
      toast({
        title: "Cookie saved",
        description: cookieMessage,
      });
    }

    return { credentialId, profileId };
  };

  const onSubmit = async (values: CredentialFormValues) => {
    try {
      setIsSubmitting(true);
      setError(null);
      setSuccess(false);

      await submitCredential(values, { verifyAfterSave: false });

      toast({
        title: initialData ? "Credentials updated" : "Credentials saved",
        description: initialData
          ? "Successfully updated. Click 'Verify' on the credential card to test the connection."
          : "Successfully saved. Click 'Verify' on the credential card to test the connection.",
      });

      setSuccess(true);
      if (onSuccess) onSuccess();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTestCredentials = async () => {
    setIsTesting(true);
    setError(null);

    let createdCredentialId: number | null = null;

    try {
      const values = form.getValues();
      const { credentialId } = await submitCredential(values, {
        verifyAfterSave: true,
        onCreated: (id) => {
          createdCredentialId = id;
        },
      });
      createdCredentialId = initialData ? null : credentialId;

      toast({
        title: "Credentials verified",
        description: "Credentials appear valid",
      });

      if (onSuccess) onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Test failed";

      // Check if this is a checkpoint error
      if (message.includes("checkpoint") || message.includes("challenge") || message.includes("additional verification")) {
        toast({
          title: "LinkedIn Challenge Detected",
          description: "Please complete the LinkedIn verification challenge. Check the Setup Status section to open the browser viewer.",
          variant: "default",
        });

        // Still call onSuccess to refresh and show the credential with locked status
        if (onSuccess) onSuccess();
      } else {
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
      setIsTesting(false);
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
            {initialData
              ? "Credentials updated successfully. The modal will close automatically."
              : "Credentials saved successfully. The modal will close automatically."}
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
                      Add the LinkedIn email and password used to sign in. The
                      account profile and display details are discovered after
                      login.
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
                                aria-label={
                                  showPassword
                                    ? "Hide password"
                                    : "Show password"
                                }
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

                  <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-2">
                    <button
                      type="button"
                      onClick={() => setShowOptionalCookie((open) => !open)}
                      className="flex w-full items-center justify-between rounded-lg px-3 py-3 text-left transition hover:bg-zinc-800/40"
                    >
                      <div className="space-y-1 pr-4">
                        <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
                          <Icons.Info className="h-4 w-4 text-zinc-400" />
                          Optional session cookie
                        </div>
                        <p className="text-sm text-zinc-400">
                          Optional fallback if normal email/password login has
                          trouble, or if you want to reuse a session that is
                          already logged in.
                        </p>
                      </div>
                      <Icons.ChevronDown
                        className={`h-4 w-4 shrink-0 text-zinc-400 transition-transform ${showOptionalCookie ? "rotate-180" : "rotate-0"}`}
                      />
                    </button>

                    {showOptionalCookie ? (
                      <div className="mt-2 border-t border-zinc-800/80 px-3 pb-3 pt-4">
                        <div className="max-h-64 space-y-4 overflow-y-auto pr-2">
                          <div className="rounded-lg border border-amber-800/80 bg-amber-950/60 p-4">
                            <p className="text-sm font-medium text-amber-100">
                              ⚠️ Important: Export ALL cookies with a browser extension
                            </p>
                            <p className="mt-1 text-sm text-amber-200/80">
                              LinkedIn's Voyager API requires the full cookie set including the HttpOnly <code className="rounded bg-amber-900/40 px-1 py-0.5">li_at</code> cookie.
                              Browser extensions can export HttpOnly cookies; browser console scripts cannot.
                            </p>
                          </div>

                          <div className="rounded-lg border border-zinc-800/80 bg-zinc-950/60 p-4">
                            <p className="text-sm font-medium text-zinc-100">
                              When to use cookies
                            </p>
                            <p className="mt-1 text-sm text-zinc-400">
                              Most users should start with only LinkedIn email
                              and password. Use cookies only if LinkedIn blocks
                              the normal login flow, asks for repeated
                              challenges, or you want to reuse an existing
                              logged-in browser session.
                            </p>
                          </div>

                          <div className="space-y-3 rounded-lg border border-zinc-800/80 bg-zinc-950/60 p-4">
                            <div>
                              <h4 className="text-sm font-medium text-zinc-100">
                                How to Export Cookies
                              </h4>
                              <p className="mt-1 text-sm text-zinc-400">
                                Use a browser extension to export ALL LinkedIn cookies including HttpOnly cookies.
                              </p>
                            </div>
                            <ol className="list-decimal space-y-2 pl-5 text-sm text-zinc-300">
                              <li>
                                Install a cookie exporter extension:
                                <ul className="ml-4 mt-1 list-disc space-y-1 text-zinc-400">
                                  <li>
                                    <a
                                      href="https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg"
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="underline hover:text-zinc-200"
                                    >
                                      EditThisCookie
                                    </a> (Chrome/Edge - 3M+ users)
                                  </li>
                                  <li>
                                    <a
                                      href="https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm"
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="underline hover:text-zinc-200"
                                    >
                                      Cookie-Editor
                                    </a> (Chrome/Edge/Firefox - open source)
                                  </li>
                                </ul>
                              </li>
                              <li>
                                Log into LinkedIn at{" "}
                                <a
                                  href="https://www.linkedin.com/feed/"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="underline hover:text-zinc-200"
                                >
                                  linkedin.com/feed/
                                </a>
                              </li>
                              <li>
                                Click the extension icon in your browser toolbar
                              </li>
                              <li>
                                Click "Export" → "JSON" (EditThisCookie) or the export icon (Cookie-Editor)
                              </li>
                              <li>
                                Verify the exported JSON includes <code className="rounded bg-zinc-800 px-1 py-0.5 text-xs">li_at</code> cookie
                              </li>
                              <li>
                                Paste the full JSON array below (starts with <code className="rounded bg-zinc-800 px-1 py-0.5 text-xs">[</code>)
                              </li>
                            </ol>
                          </div>

                          <div className="space-y-3 rounded-lg border border-zinc-800/80 bg-zinc-950/60 p-4">
                            <h4 className="text-sm font-medium text-zinc-100">
                              ⚠️ Security Note
                            </h4>
                            <p className="text-sm text-zinc-400">
                              Browser extensions can access all site data. Only install extensions from trusted publishers with good reviews.
                              Both recommended extensions are well-established with millions of users or open source code.
                            </p>
                          </div>

                          <FormField
                            control={form.control}
                            name="cookie_data"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Cookie JSON Array</FormLabel>
                                <FormControl>
                                  <Textarea
                                    placeholder='Paste the JSON array from EditThisCookie/Cookie-Editor: [{"name":"li_at","value":"...","domain":".linkedin.com",...},{...}]'
                                    {...field}
                                    rows={6}
                                    className="border-zinc-800 bg-zinc-950/70 font-mono text-xs"
                                  />
                                </FormControl>
                                <FormDescription>
                                  Must include the <code className="rounded bg-zinc-800 px-1 py-0.5 text-xs">li_at</code> cookie. Paste the complete JSON array from your extension (starts with <code className="rounded bg-zinc-800 px-1 py-0.5 text-xs">[</code>).
                                  Stored encrypted and used for API authentication.
                                </FormDescription>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                      </div>
                    ) : null}
                  </div>
                </CardContent>
              </Card>

              <div className="flex flex-wrap items-center justify-end gap-3 border-t border-zinc-800/80 pt-6">
                <div className="flex flex-wrap items-center gap-3">
                  {onCancel ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={onCancel}
                      disabled={isSubmitting || isTesting}
                      className="border-zinc-800 bg-zinc-950 text-zinc-100 hover:bg-zinc-900"
                    >
                      Cancel
                    </Button>
                  ) : null}

                  {!initialData ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={isSubmitting || isTesting}
                      onClick={handleTestCredentials}
                      className="border-zinc-800 bg-zinc-950 text-zinc-100 hover:bg-zinc-900"
                    >
                      {isTesting ? (
                        <>
                          <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                          Testing & Saving...
                        </>
                      ) : (
                        <>
                          <Icons.Activity className="mr-2 h-4 w-4" />
                          Test & Add
                        </>
                      )}
                    </Button>
                  ) : null}

                  <Button type="submit" disabled={isSubmitting || isTesting}>
                    {isSubmitting ? (
                      <>
                        <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : initialData ? (
                      <>
                        <Icons.Save className="mr-2 h-4 w-4" />
                        Save Changes
                      </>
                    ) : (
                      <>
                        <Icons.Save className="mr-2 h-4 w-4" />
                        Save Without Testing
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
                      <span>Passwords and cookies are encrypted at rest.</span>
                    </div>
                    <div className="flex items-start">
                      <Icons.CheckCircle className="mr-2 mt-0.5 h-3 w-3 text-green-500/80" />
                      <span>Credential values are not shown back in full.</span>
                    </div>
                    <div className="flex items-start">
                      <Icons.CheckCircle className="mr-2 mt-0.5 h-3 w-3 text-green-500/80" />
                      <span>
                        The modal only stores the data needed to log in.
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-zinc-800/80 bg-zinc-950/50 shadow-none">
                <CardContent className="pt-6">
                  <h3 className="flex items-center text-sm font-semibold text-zinc-100">
                    <Icons.AlertCircle className="mr-2 h-4 w-4 text-zinc-400" />
                    What to know
                  </h3>
                  <ul className="mt-4 space-y-3 text-sm text-zinc-400">
                    <li className="flex items-start">
                      <Icons.Info className="mr-2 mt-0.5 h-3 w-3 text-blue-400/80" />
                      <span>
                        Use the same LinkedIn account you want the daemon to run
                        under.
                      </span>
                    </li>
                    <li className="flex items-start">
                      <Icons.Info className="mr-2 mt-0.5 h-3 w-3 text-blue-400/80" />
                      <span>
                        Profile details are discovered automatically after a
                        successful login or verification.
                      </span>
                    </li>
                    <li className="flex items-start">
                      <Icons.AlertCircle className="mr-2 mt-0.5 h-3 w-3 text-amber-400/80" />
                      <span>
                        If uploading cookies, export <strong>ALL</strong> cookies (not just li_at) — the Voyager API needs the full set.
                      </span>
                    </li>
                    <li className="flex items-start">
                      <Icons.Info className="mr-2 mt-0.5 h-3 w-3 text-blue-400/80" />
                      <span>
                        Recommended: use EditThisCookie or Cookie-Editor extension for the most complete export.
                      </span>
                    </li>
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>
        </form>
      </Form>
    </div>
  );
}
