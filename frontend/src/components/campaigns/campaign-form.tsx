"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Icons } from "@/lib/types/components";
import { Campaign, CampaignTemplate } from "@/lib/types/components";
import type { LinkedInSetupStatus } from "@/lib/api/dashboard";
import {
  getLinkedInSetupStatus,
  getCampaignTemplates,
} from "@/lib/api/dashboard";
import {
  zincDialogContentClassName,
  zincDialogFooterClassName,
  zincDialogHeaderClassName,
  zincInputClassName,
  zincSectionClassName,
  zincSelectContentClassName,
  zincSelectTriggerClassName,
  zincTabsListClassName,
  zincTabsTriggerClassName,
  zincTextareaClassName,
} from "@/lib/modal-styles";

const formSchema = z.object({
  name: z
    .string()
    .min(3, "Name must be at least 3 characters")
    .max(100, "Name is too long"),
  description: z.string().max(500, "Description is too long").optional(),
  productDocs: z
    .string()
    .url("Must be a valid URL")
    .optional()
    .or(z.literal("")),
  campaignObjective: z.string().max(200, "Objective is too long").optional(),
  bookingLink: z
    .string()
    .url("Must be a valid URL")
    .optional()
    .or(z.literal("")),
  isFreemium: z.boolean(),
  ghostModeEnabled: z.boolean(),
  velocity: z.number().min(1).max(100),
  cooldownMinutes: z.number().min(1).max(1440),
  status: z.enum(["draft", "active", "paused"]),
});

type FormValues = z.infer<typeof formSchema>;

interface CampaignFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  campaign?: Campaign | null;
  onSubmit: (data: Partial<Campaign>) => void;
  isEditing?: boolean;
}

export function CampaignForm({
  open,
  onOpenChange,
  campaign,
  onSubmit,
  isEditing = false,
}: CampaignFormProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [linkedinSetupStatus, setLinkedinSetupStatus] =
    useState<LinkedInSetupStatus | null>(null);
  const [checkingLinkedin, setCheckingLinkedin] = useState(false);
  const [templates, setTemplates] = useState<CampaignTemplate[]>([]);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [selectedTemplate, setSelectedTemplate] =
    useState<CampaignTemplate | null>(null);
  const [showTemplateList, setShowTemplateList] = useState(!isEditing);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      description: undefined,
      productDocs: undefined,
      campaignObjective: undefined,
      bookingLink: undefined,
      isFreemium: false,
      ghostModeEnabled: false,
      velocity: 10,
      cooldownMinutes: 60,
      status: "draft",
    },
  });

  // Check LinkedIn setup status when form opens (for new campaigns)
  useEffect(() => {
    if (open && !isEditing && !campaign) {
      void (async () => {
        try {
          setCheckingLinkedin(true);
          const response = await getLinkedInSetupStatus();
          if (response.data) {
            setLinkedinSetupStatus(response.data);
          }
        } catch (err) {
          console.error("Error checking LinkedIn setup status:", err);
        } finally {
          setCheckingLinkedin(false);
        }
      })();
    } else {
      setLinkedinSetupStatus(null);
      setCheckingLinkedin(false);
    }
  }, [open, isEditing, campaign]);

  // Fetch templates when opening the form for a new campaign
  useEffect(() => {
    if (!isEditing && !campaign && !templates.length) {
      void (async () => {
        try {
          setTemplateLoading(true);
          const response = await getCampaignTemplates();
          if (response.data && response.data.data) {
            setTemplates(response.data.data);
          }
        } catch (err) {
          console.error("Error fetching templates:", err);
        } finally {
          setTemplateLoading(false);
        }
      })();
    }
  }, [isEditing, campaign, templates.length]);

  // Clone template when selected
  useEffect(() => {
    if (selectedTemplate && !campaign) {
      form.reset({
        name: selectedTemplate.name,
        description: selectedTemplate.description || undefined,
        campaignObjective: selectedTemplate.campaign_objective || undefined,
        ghostModeEnabled: selectedTemplate.ghost_mode_enabled,
        velocity: selectedTemplate.velocity,
        cooldownMinutes: selectedTemplate.cooldown_minutes,
        status: "draft",
        isFreemium: false,
        productDocs: undefined,
        bookingLink: undefined,
      });
    }
  }, [selectedTemplate, campaign, form]);

  useEffect(() => {
    if (campaign) {
      form.reset({
        name: campaign.name,
        description: campaign.description || undefined,
        productDocs: campaign.productDocs || undefined,
        campaignObjective: campaign.campaignObjective || undefined,
        bookingLink: campaign.bookingLink || undefined,
        isFreemium: campaign.isFreemium,
        ghostModeEnabled: campaign.ghostModeEnabled || false,
        velocity: campaign.velocity,
        cooldownMinutes: campaign.cooldownMinutes,
        status: campaign.status as "draft" | "active" | "paused",
      });
    } else {
      form.reset({
        name: "",
        description: undefined,
        productDocs: undefined,
        campaignObjective: undefined,
        bookingLink: undefined,
        isFreemium: false,
        ghostModeEnabled: false,
        velocity: 10,
        cooldownMinutes: 60,
        status: "draft",
      });
    }
  }, [campaign, form]);

  const handleSubmit = async (values: FormValues) => {
    setLoading(true);
    try {
      await onSubmit(values);
      form.reset();
      onOpenChange(false);
    } catch (error) {
      console.error("Error submitting form:", error);
    } finally {
      setLoading(false);
    }
  };

  // Check if LinkedIn is configured before allowing campaign creation
  if (checkingLinkedin) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className={`${zincDialogContentClassName} sm:max-w-[600px]`}
        >
          <DialogHeader className={zincDialogHeaderClassName}>
            <DialogTitle>Checking Setup Status</DialogTitle>
            <DialogDescription>
              Verifying your LinkedIn configuration before creating a campaign.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-center gap-4 py-12 text-zinc-400">
            <Icons.RefreshCw className="h-8 w-8 animate-spin text-zinc-400" />
            <span>Checking setup status...</span>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // If LinkedIn is not configured (no credentials or count is 0), show an informative message
  if (
    !isEditing &&
    !campaign &&
    !linkedinSetupStatus?.status.linkedinCredentials?.count
  ) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className={`${zincDialogContentClassName} sm:max-w-[520px]`}
        >
          <DialogHeader className={zincDialogHeaderClassName}>
            <DialogTitle>LinkedIn Not Configured</DialogTitle>
            <DialogDescription>
              You must set up LinkedIn credentials before creating a campaign.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col items-center justify-center space-y-4 py-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full border border-red-500/30 bg-red-500/10">
              <Icons.AlertCircle className="h-8 w-8 text-red-400" />
            </div>
            <p className="text-sm text-zinc-400">
              You must set up LinkedIn credentials before creating a campaign.
            </p>
            <Button
              variant="outline"
              className="border-zinc-800 bg-zinc-900 text-zinc-100 hover:bg-zinc-800"
              onClick={() => {
                window.location.href = "/settings?tab=linkedin-credentials";
                onOpenChange(false);
              }}
            >
              <Icons.Settings className="h-4 w-4 mr-2" />
              Go to LinkedIn Settings
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={`${zincDialogContentClassName} max-h-[90vh] overflow-hidden p-0 sm:max-w-[860px]`}
      >
        <DialogHeader
          className={`${zincDialogHeaderClassName} px-6 pt-6 sm:px-8 sm:pt-8`}
        >
          <DialogTitle>
            {isEditing ? "Edit Campaign" : "Create New Campaign"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update your campaign details and settings."
              : "Create a new outreach campaign to start connecting with leads."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="flex max-h-[calc(90vh-92px)] flex-col"
          >
            <Tabs
              defaultValue="basic"
              className="flex-1 overflow-hidden px-6 py-6 sm:px-8 sm:py-8"
            >
              <TabsList
                className={`${zincTabsListClassName} grid grid-cols-2 gap-1 md:grid-cols-4`}
              >
                <TabsTrigger className={zincTabsTriggerClassName} value="basic">
                  Basic Info
                </TabsTrigger>
                <TabsTrigger
                  className={zincTabsTriggerClassName}
                  value="settings"
                >
                  Settings
                </TabsTrigger>
                <TabsTrigger
                  className={zincTabsTriggerClassName}
                  value="advanced"
                >
                  Advanced
                </TabsTrigger>
                <TabsTrigger
                  className={zincTabsTriggerClassName}
                  value="templates"
                >
                  Templates
                </TabsTrigger>
              </TabsList>

              <div className="mt-6 max-h-[calc(90vh-260px)] overflow-y-auto pr-1">
                <TabsContent
                  value="basic"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Campaign Name</FormLabel>
                        <FormControl>
                          <Input
                            className={zincInputClassName}
                            placeholder="Enter campaign name"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          A descriptive name for your campaign
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="description"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Description</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="Describe what this campaign is about..."
                            className={`${zincTextareaClassName} resize-none`}
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Optional: Brief description of the campaign
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="campaignObjective"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Campaign Objective</FormLabel>
                        <FormControl>
                          <Input
                            className={zincInputClassName}
                            placeholder="What are you trying to achieve?"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          The primary goal of this campaign
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </TabsContent>

                <TabsContent
                  value="settings"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="status"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Status</FormLabel>
                        <Select
                          onValueChange={(value: string | null) => {
                            if (value) field.onChange(value);
                          }}
                          defaultValue={field.value}
                        >
                          <FormControl>
                            <SelectTrigger
                              className={zincSelectTriggerClassName}
                            >
                              <SelectValue placeholder="Select status" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent className={zincSelectContentClassName}>
                            <SelectItem value="draft">Draft</SelectItem>
                            <SelectItem value="active">Active</SelectItem>
                            <SelectItem value="paused">Paused</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>Set campaign status</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="velocity"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Daily Connection Limit</FormLabel>
                          <FormControl>
                            <Input
                              className={zincInputClassName}
                              type="number"
                              min="1"
                              max="100"
                              placeholder="10"
                              value={field.value}
                              onChange={(e) =>
                                field.onChange(Number(e.target.value))
                              }
                              onBlur={field.onBlur}
                              ref={field.ref}
                            />
                          </FormControl>
                          <FormDescription>
                            Maximum number of connections to send per day
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="cooldownMinutes"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Cooldown (minutes)</FormLabel>
                          <FormControl>
                            <Input
                              className={zincInputClassName}
                              type="number"
                              min="1"
                              max="1440"
                              placeholder="60"
                              value={field.value}
                              onChange={(e) =>
                                field.onChange(Number(e.target.value))
                              }
                              onBlur={field.onBlur}
                              ref={field.ref}
                            />
                          </FormControl>
                          <FormDescription>Between actions</FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <FormField
                    control={form.control}
                    name="isFreemium"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">
                            Freemium Model
                          </FormLabel>
                          <FormDescription>
                            Offers free trial/product
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="ghostModeEnabled"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">
                            Ghost Mode
                          </FormLabel>
                          <FormDescription>
                            Enable ghost mode to test campaign without sending
                            real LinkedIn actions
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </TabsContent>

                <TabsContent
                  value="advanced"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="productDocs"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Product Documentation URL</FormLabel>
                        <FormControl>
                          <Input
                            className={zincInputClassName}
                            placeholder="https://example.com/docs"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Link to product documentation
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="bookingLink"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Booking Link</FormLabel>
                        <FormControl>
                          <Input
                            className={zincInputClassName}
                            placeholder="https://calendly.com/your-link"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>Meeting booking link</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </TabsContent>

                <TabsContent
                  value="templates"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-1">
                        <h4 className="font-medium text-zinc-100">
                          Use Template
                        </h4>
                        <p className="text-sm text-zinc-400">
                          Select a campaign template to clone its configuration
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-zinc-800 bg-zinc-900 text-zinc-100 hover:bg-zinc-800"
                        onClick={() => setShowTemplateList(!showTemplateList)}
                      >
                        Browse Templates
                      </Button>
                    </div>

                    {showTemplateList && (
                      <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 p-6">
                        {templateLoading ? (
                          <div className="py-4 text-center">
                            <Icons.RefreshCw className="mx-auto h-8 w-8 animate-spin text-zinc-400" />
                            <p className="mt-2 text-sm text-zinc-400">
                              Loading templates...
                            </p>
                          </div>
                        ) : templates.length === 0 ? (
                          <div className="py-6 text-center">
                            <p className="text-sm text-zinc-400">
                              No templates found
                            </p>
                            <Button
                              size="sm"
                              variant="outline"
                              className="mt-2 border-zinc-800 bg-zinc-900 text-zinc-100 hover:bg-zinc-800"
                              onClick={() =>
                                router.push("/campaigns/templates")
                              }
                            >
                              Create Template
                            </Button>
                          </div>
                        ) : (
                          <div className="space-y-2 max-h-60 overflow-y-auto">
                            {templates.map((template) => (
                              <div
                                key={template.id}
                                className={`flex cursor-pointer items-center justify-between rounded-xl border p-3 transition-colors ${
                                  selectedTemplate?.id === template.id
                                    ? "border-zinc-600 bg-zinc-900"
                                    : "border-zinc-800 bg-zinc-950/60 hover:bg-zinc-900/70"
                                }`}
                                onClick={() => setSelectedTemplate(template)}
                              >
                                <div className="space-y-1">
                                  <div className="font-medium text-zinc-100">
                                    {template.name}
                                  </div>
                                  <div className="line-clamp-1 text-xs text-zinc-400">
                                    {template.description || "No description"}
                                  </div>
                                </div>
                                {selectedTemplate?.id === template.id && (
                                  <Icons.CheckCircle className="h-5 w-5 text-zinc-100" />
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {selectedTemplate && (
                      <div className="rounded-xl border border-zinc-700 bg-zinc-900/70 p-4">
                        <div className="flex items-center justify-between">
                          <div className="space-y-1">
                            <p className="text-sm font-medium text-zinc-100">
                              Template Selected: {selectedTemplate.name}
                            </p>
                            <p className="text-xs text-zinc-400">
                              Click "Create Campaign" to apply template settings
                            </p>
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                            onClick={() => setSelectedTemplate(null)}
                          >
                            Remove
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </TabsContent>
              </div>
            </Tabs>

            <DialogFooter className={zincDialogFooterClassName}>
              <Button
                type="button"
                variant="outline"
                className="border-zinc-800 bg-zinc-900 text-zinc-100 hover:bg-zinc-800"
                onClick={() => onOpenChange(false)}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading
                  ? "Saving..."
                  : isEditing
                    ? "Update Campaign"
                    : "Create Campaign"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
