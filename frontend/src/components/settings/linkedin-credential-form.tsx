"use client";

import { useState, useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
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
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Icons } from "@/lib/types/components";
import {
  createLinkedInCredentials,
  updateLinkedInCredentials,
  verifyLinkedInCredentials,
  deleteLinkedInCredentials,
  type LinkedInCredentials,
  type LinkedInProfile,
  getLinkedInProfiles,
  type CreateLinkedInCredentialsData,
} from "@/lib/api/dashboard";

const credentialSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  username: z
    .string()
    .min(2, "Username must be at least 2 characters")
    .optional(),
  linkedin_profile_id: z.string().optional(),
  // Optional cookie input: either li_at value or full Playwright storage_state JSON
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
  const { toast } = useToast();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [linkedinProfiles, setLinkedinProfiles] = useState<LinkedInProfile[]>(
    [],
  );
  const [loadingProfiles, setLoadingProfiles] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const loadProfiles = async () => {
    try {
      setLoadingProfiles(true);
      const response = await getLinkedInProfiles();
      if (response.data && response.data.profiles) {
        setLinkedinProfiles(response.data.profiles);
      }
    } catch (err) {
      console.error("Failed to load LinkedIn profiles:", err);
    } finally {
      setLoadingProfiles(false);
    }
  };

  // Load LinkedIn profiles on mount (for create mode only)
  useEffect(() => {
    if (!initialData) {
      const loadProfilesEffect = async () => {
        setLoadingProfiles(true);
        try {
          const response = await getLinkedInProfiles();
          if (response.data && response.data.profiles) {
            setLinkedinProfiles(response.data.profiles);
          }
        } catch (err) {
          console.error("Failed to load LinkedIn profiles:", err);
        } finally {
          setLoadingProfiles(false);
        }
      };
      loadProfilesEffect();
    }
  }, [initialData]);

  const form = useForm<CredentialFormValues>({
    resolver: zodResolver(credentialSchema),
    defaultValues: {
      email: initialData?.public_email.replace(/\*\*\*/g, "") || "",
      password: "",
      username: initialData?.username || "",
      linkedin_profile_id: "",
      cookie_data: "",
    },
  });

  const onSubmit = async (values: CredentialFormValues) => {
    try {
      setIsSubmitting(true);
      setError(null);
      setSuccess(false);

      const profileId = form.getValues("linkedin_profile_id") || null;

      const formData: CreateLinkedInCredentialsData = {
        email: values.email,
        password: values.password,
        username: values.username || form.getValues("email").split("@")[0],
      };

      if (profileId) {
        formData.linkedin_profile_id = parseInt(profileId, 10);
      }

      let response;
      if (initialData) {
        // Update existing credential
        response = await updateLinkedInCredentials(initialData.id, formData);
      } else {
        // Create new credential
        response = await createLinkedInCredentials(formData);
      }

      if (response.data) {
        setSuccess(true);
        if (onSuccess) onSuccess();
      } else {
        setError(response.error || "Failed to save credentials");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert>
          <Icons.CheckCircle className="h-4 w-4" />
          <AlertDescription>
            {initialData
              ? "Credentials updated successfully!"
              : "Credentials created successfully!"}
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <div className="space-y-4">
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>LinkedIn Email</FormLabel>
                      <FormControl>
                        <div className="flex">
                          <div className="flex items-center justify-center px-3 border border-r-0 rounded-l-md bg-zinc-900 dark:bg-zinc-800">
                            <Icons.Mail className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                          </div>
                          <Input
                            placeholder="name@linkedin.com"
                            type="email"
                            {...field}
                            className="rounded-l-none"
                          />
                        </div>
                      </FormControl>
                      <FormDescription>
                        The email address for your LinkedIn account
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
                          <div className="flex items-center justify-center px-3 border border-r-0 rounded-l-md bg-zinc-900 dark:bg-zinc-800">
                            <Icons.Lock className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                          </div>
                          <Input
                            placeholder="••••••••"
                            type={showPassword ? "text" : "password"}
                            {...field}
                            className="rounded-l-none"
                          />
                        </div>
                      </FormControl>
                      <FormDescription>
                        Your LinkedIn password (stored encrypted with AES-256)
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Display Username</FormLabel>
                      <FormControl>
                        <div className="flex">
                          <div className="flex items-center justify-center px-3 border border-r-0 rounded-l-md bg-zinc-900 dark:bg-zinc-800">
                            <span className="text-zinc-500 dark:text-zinc-400">
                              @
                            </span>
                          </div>
                          <Input
                            placeholder="linkedin-username"
                            {...field}
                            className="rounded-l-none"
                          />
                        </div>
                      </FormControl>
                      <FormDescription>
                        Your LinkedIn username for display purposes
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {!initialData && (
                  <FormField
                    control={form.control}
                    name="linkedin_profile_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>LinkedIn Profile</FormLabel>
                        <FormControl>
                          <Select
                            onValueChange={(value: string | null) => {
                              if (value) field.onChange(value);
                            }}
                            defaultValue={field.value}
                          >
                            <SelectTrigger className="ring-1 ring-zinc-800 dark:ring-zinc-700">
                              <SelectValue placeholder="Select a LinkedIn profile" />
                            </SelectTrigger>
                            <SelectContent>
                              {loadingProfiles ? (
                                <SelectItem value="loading" disabled>
                                  Loading profiles...
                                </SelectItem>
                              ) : linkedinProfiles.length === 0 ? (
                                <SelectItem value="no-profiles" disabled>
                                  No LinkedIn profiles available. Please create
                                  one first.
                                </SelectItem>
                              ) : (
                                linkedinProfiles.map((profile) => (
                                  <SelectItem
                                    key={profile.id}
                                    value={profile.id.toString()}
                                  >
                                    {profile.linkedin_username} -{" "}
                                    {profile.active ? "Active" : "Inactive"}
                                  </SelectItem>
                                ))
                              )}
                            </SelectContent>
                          </Select>
                        </FormControl>
                        <FormDescription>
                          Choose the LinkedIn profile this credential belongs to
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
              </div>

              <div className="border-t pt-6">
                <div className="flex justify-end space-x-4">
                  {onCancel && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={onCancel}
                      disabled={isSubmitting}
                    >
                      Cancel
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={isSubmitting}
                  >
                    {showPassword ? (
                      <>
                        <Icons.EyeOff className="h-4 w-4 mr-2" />
                        Hide Password
                      </>
                    ) : (
                      <>
                        <Icons.Eye className="h-4 w-4 mr-2" />
                        Show Password
                      </>
                    )}
                  </Button>
                  <Button type="submit" disabled={isSubmitting || isTesting}>
                    {isTesting ? (
                      <>
                        <Icons.RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        Testing...
                      </>
                    ) : isSubmitting ? (
                      <>
                        <Icons.RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : initialData ? (
                      <>
                        <Icons.CheckCircle className="h-4 w-4 mr-2" />
                        Update Credentials
                      </>
                    ) : (
                      <>
                        <Icons.Save className="h-4 w-4 mr-2" />
                        Add Credentials
                      </>
                    )}
                  </Button>

                  {/* Test credentials button (create + verify flow) */}
                  {!initialData && (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={isSubmitting || isTesting}
                      onClick={async () => {
                        // Test current form values without closing form
                        setIsTesting(true);
                        setError(null);
                        try {
                          const values = form.getValues();
                          const formData: CreateLinkedInCredentialsData = {
                            email: values.email,
                            password: values.password,
                            username:
                              values.username || values.email.split("@")[0],
                          };
                          // Create credential row first
                          const createResp =
                            await createLinkedInCredentials(formData);
                          if (!createResp.data)
                            throw new Error(
                              createResp.error ||
                                "Failed to create credentials for test",
                            );

                          const credId = createResp.data.id;
                          // Run verification - backend will handle missing profile by associating one if needed
                          const verifyResp =
                            await verifyLinkedInCredentials(credId);

                          if (verifyResp.data && verifyResp.data.success) {
                            toast({
                              title: "Credentials verified",
                              description:
                                verifyResp.data.message ||
                                "Credentials appear valid",
                            });
                            if (onSuccess) onSuccess();
                          } else {
                            const errMsg =
                              verifyResp.error || "Verification failed";
                            toast({
                              title: "Verification failed",
                              description: errMsg,
                              variant: "destructive",
                            });
                            // Clean up failed credential (soft-deactivate)
                            try {
                              await deleteLinkedInCredentials(credId);
                            } catch (e) {
                              /* ignore */
                            }
                          }
                        } catch (err) {
                          toast({
                            title: "Error",
                            description:
                              err instanceof Error
                                ? err.message
                                : "Test failed",
                            variant: "destructive",
                          });
                        } finally {
                          setIsTesting(false);
                        }
                      }}
                    >
                      <Icons.Activity className="h-4 w-4 mr-2" />
                      Test Credentials
                    </Button>
                  )}
                </div>
              </div>
            </form>
          </Form>
        </div>

        <div className="space-y-4">
          <Card>
            <CardContent className="pt-6">
              <h3 className="font-semibold flex items-center">
                <Icons.Lock className="h-4 w-4 text-blue-600 mr-2" />
                Security Information
              </h3>
              <div className="space-y-3 text-sm dark:text-zinc-400 mt-4">
                <div className="flex items-start">
                  <Icons.CheckCircle className="h-3 w-3 text-green-500/80 mt-0.5 mr-2" />
                  <span className="text-zinc-500 dark:text-zinc-400">
                    Passwords are encrypted with AES-256 at rest
                  </span>
                </div>
                <div className="flex items-start">
                  <Icons.CheckCircle className="h-3 w-3 text-green-500/80 mt-0.5 mr-2" />
                  <span className="text-zinc-500 dark:text-zinc-400">
                    Your credentials are never logged
                  </span>
                </div>
                <div className="flex items-start">
                  <Icons.CheckCircle className="h-3 w-3 text-green-500/80 mt-0.5 mr-2" />
                  <span className="text-zinc-500 dark:text-zinc-400">
                    Email is masked in display (e.g., j***@domain.com)
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <h3 className="font-semibold flex items-center dark:text-zinc-200">
                <Icons.AlertCircle className="h-4 w-4 text-yellow-500 mr-2 dark:text-yellow-500" />
                What to Know
              </h3>
              <ul className="text-sm space-y-2 dark:text-zinc-400 mt-4">
                <li className="flex items-start">
                  <Icons.Info className="h-3 w-3 text-blue-500/80 mt-0.5 mr-2" />
                  <span className="text-zinc-500 dark:text-zinc-400">
                    Use a dedicated LinkedIn account for outreach campaigns
                  </span>
                </li>
                <li className="flex items-start">
                  <Icons.Info className="h-3 w-3 text-blue-500/80 mt-0.5 mr-2" />
                  <span className="text-zinc-500 dark:text-zinc-400">
                    Credentials are validated before first use
                  </span>
                </li>
                <li className="flex items-start">
                  <Icons.Info className="h-3 w-3 text-blue-500/80 mt-0.5 mr-2" />
                  <span className="text-zinc-500 dark:text-zinc-400">
                    Rotate credentials regularly for security
                  </span>
                </li>
                {!initialData && linkedinProfiles.length === 0 && (
                  <li className="flex items-start">
                    <Icons.AlertTriangle className="h-3 w-3 text-orange-500/80 mt-0.5 mr-2" />
                    <span className="text-zinc-500 dark:text-zinc-400">
                      You need to create a LinkedIn profile first to use
                      credentials
                    </span>
                  </li>
                )}
              </ul>
            </CardContent>
          </Card>

          {!initialData && (
            <div className="pt-4">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                {showAdvanced ? "Hide advanced" : "Advanced (optional)"}
              </Button>

              {showAdvanced && (
                <Card>
                  <CardContent className="pt-6">
                    <FormField
                      control={form.control}
                      name="cookie_data"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>
                            Optional: Paste Cookie (li_at or storage_state)
                          </FormLabel>
                          <FormControl>
                            <Textarea
                              placeholder="Paste li_at cookie value or full Playwright storage_state JSON"
                              {...field}
                              rows={4}
                            />
                          </FormControl>
                          <FormDescription>
                            Paste a li_at cookie value or the full Playwright
                            storage_state JSON. This will be stored encrypted.
                          </FormDescription>
                        </FormItem>
                      )}
                    />

                    <div className="flex justify-end mt-2">
                      <Button
                        variant="outline"
                        onClick={async () => {
                          setIsTesting(true);
                          setError(null);
                          try {
                            const profileId =
                              form.getValues("linkedin_profile_id") || null;
                            if (!profileId) {
                              toast({
                                title: "Select a LinkedIn profile first",
                                variant: "destructive",
                              });
                              return;
                            }

                            const cookieValue = form.getValues("cookie_data");
                            if (!cookieValue || !cookieValue.trim()) {
                              toast({
                                title:
                                  "Paste a cookie or storage_state JSON first",
                                variant: "destructive",
                              });
                              return;
                            }

                            const resp = await fetch(
                              `/api/linkedin-profiles/${profileId}/cookies/`,
                              {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                  cookie_data: cookieValue,
                                }),
                              },
                            );
                            const data = await resp.json();
                            if (resp.ok && data.success) {
                              toast({
                                title: "Cookie saved",
                                description: data.message || "Cookie saved",
                              });
                              form.setValue("cookie_data", "");
                              if (onSuccess) onSuccess();
                            } else {
                              toast({
                                title: "Error saving cookie",
                                description:
                                  data.error || data.message || "Failed",
                                variant: "destructive",
                              });
                            }
                          } catch (err) {
                            toast({
                              title: "Network error",
                              description:
                                err instanceof Error
                                  ? err.message
                                  : String(err),
                              variant: "destructive",
                            });
                          } finally {
                            setIsTesting(false);
                          }
                        }}
                      >
                        Upload Cookie
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
