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
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Icons } from "@/lib/types/components";
import { Campaign } from "@/lib/types/components";
import type { LinkedInSetupStatus } from "@/lib/api/dashboard";
import { getLinkedInSetupStatus } from "@/lib/api/dashboard";
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
  description: z.string().optional(),
  productPitch: z
    .string()
    .optional()
    .refine((v) => !v || v.length >= 300, {
      message: "Product pitch must be at least 300 characters",
    }),
  campaignObjective: z.string().optional(),
  bookingLink: z
    .string()
    .url("Must be a valid URL")
    .optional()
    .or(z.literal("")),
  searchKeywords: z.string().optional(),
  icpTitles: z.string().optional(),
  followUpStrategy: z.string().optional(),
  targetDegrees: z.array(z.number()).min(1, "Select at least one connection degree"),
  isFreemium: z.boolean(),
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

function parseIcpTitles(raw: string | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function formatIcpTitles(titles: string[] | undefined): string {
  if (!titles || titles.length === 0) return "";
  return titles.join(", ");
}

function parseSearchKeywords(raw: string | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function formatSearchKeywords(keywords: string[] | undefined): string {
  if (!keywords || keywords.length === 0) return "";
  return keywords.join(", ");
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

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      description: undefined,
      productPitch: undefined,
      campaignObjective: undefined,
      bookingLink: undefined,
      searchKeywords: undefined,
      icpTitles: undefined,
      followUpStrategy: undefined,
      targetDegrees: [2, 3],
      isFreemium: false,
      velocity: 10,
      cooldownMinutes: 60,
      status: "draft",
    },
  });

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

  useEffect(() => {
    if (campaign) {
      form.reset({
        name: campaign.name,
        description: campaign.description || undefined,
        productPitch: campaign.productPitch || undefined,
        campaignObjective: campaign.campaignObjective || undefined,
        bookingLink: campaign.bookingLink || undefined,
        searchKeywords: formatSearchKeywords(campaign.searchKeywords),
        icpTitles: formatIcpTitles(campaign.icpTitles),
        followUpStrategy: campaign.followUpStrategy || undefined,
        targetDegrees: campaign.targetDegrees || [2, 3],
        isFreemium: campaign.isFreemium,
        velocity: campaign.velocity,
        cooldownMinutes: campaign.cooldownMinutes,
        status: campaign.status as "draft" | "active" | "paused",
      });
    } else {
      form.reset({
        name: "",
        description: undefined,
        productPitch: undefined,
        campaignObjective: undefined,
        bookingLink: undefined,
        searchKeywords: undefined,
        icpTitles: undefined,
        followUpStrategy: undefined,
        targetDegrees: [2, 3],
        isFreemium: false,
        velocity: 10,
        cooldownMinutes: 60,
        status: "draft",
      });
    }
  }, [campaign, form]);

  const handleSubmit = async (values: FormValues) => {
    setLoading(true);
    try {
      const { searchKeywords, icpTitles, targetDegrees, ...rest } = values;
      const payload: Partial<Campaign> = {
        ...rest,
        searchKeywords: parseSearchKeywords(searchKeywords),
        icpTitles: parseIcpTitles(icpTitles),
        targetDegrees,
      };

      await onSubmit(payload);
      form.reset();
      onOpenChange(false);
    } catch (error) {
      console.error("Error submitting form:", error);
    } finally {
      setLoading(false);
    }
  };

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

  const productPitchValue = form.watch("productPitch") || "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={`${zincDialogContentClassName} flex max-h-[90vh] flex-col overflow-hidden p-0 sm:max-w-[860px]`}
      >
        <DialogHeader
          className={`${zincDialogHeaderClassName} flex-shrink-0 px-6 pt-6 sm:px-8 sm:pt-8`}
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
            className="flex flex-1 flex-col overflow-hidden"
          >
            <Tabs
              defaultValue="basic"
              className="flex flex-1 flex-col overflow-hidden px-6 sm:px-8"
            >
              <TabsList
                className={`${zincTabsListClassName} mb-4 grid flex-shrink-0 grid-cols-2 gap-1 md:grid-cols-5`}
              >
                <TabsTrigger className={zincTabsTriggerClassName} value="basic">
                  Campaign Info
                </TabsTrigger>
                <TabsTrigger
                  className={zincTabsTriggerClassName}
                  value="targeting"
                >
                  Targeting
                </TabsTrigger>
                <TabsTrigger
                  className={zincTabsTriggerClassName}
                  value="strategy"
                >
                  Follow-Up
                </TabsTrigger>
                <TabsTrigger
                  className={zincTabsTriggerClassName}
                  value="settings"
                >
                  Settings
                </TabsTrigger>
              </TabsList>

              <div className="flex-1 overflow-y-auto pr-2 pb-4">
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
                            placeholder="Describe what this campaign is about, your target market, goals..."
                            className={`${zincTextareaClassName} min-h-[120px] resize-y`}
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Detailed description of the campaign (no character
                          limit)
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
                          <Textarea
                            className={`${zincTextareaClassName} min-h-[80px] resize-y`}
                            placeholder="What are you trying to achieve? e.g., Book demos for LenGrowth by demonstrating value as a growth operating system"
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
                        <FormDescription>
                          Meeting booking link (shared by the agent when
                          appropriate)
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </TabsContent>

                <TabsContent
                  value="targeting"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="searchKeywords"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>LinkedIn Search Keywords</FormLabel>
                        <FormControl>
                          <Textarea
                            className={`${zincTextareaClassName} min-h-[100px] resize-y`}
                            placeholder="growth hacker, startup founder, B2B marketing, SaaS CEO..."
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Comma-separated LinkedIn search terms. Lengrowth uses these to find and discover matching leads on LinkedIn.
                          {field.value && (
                            <span className="ml-1 text-zinc-300">
                              ({parseSearchKeywords(field.value).length} keywords)
                            </span>
                          )}
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="icpTitles"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>ICP - Job Titles & Roles</FormLabel>
                        <FormControl>
                          <Textarea
                            className={`${zincTextareaClassName} min-h-[100px] resize-y`}
                            placeholder="Founder, CEO, Head of Growth, Marketing Manager, Growth Strategist, CTO..."
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Comma-separated list of target job titles and roles for qualification.
                          The AI uses these to filter and qualify the leads found by search keywords.
                          {field.value && (
                            <span className="ml-1 text-zinc-300">
                              ({parseIcpTitles(field.value).length} titles)
                            </span>
                          )}
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="targetDegrees"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Target Connection Degrees</FormLabel>
                        <FormDescription className="mb-2">
                          Which connection degrees should this campaign target?
                        </FormDescription>
                        <div className="flex flex-col gap-3">
                          {[
                            { value: 1, label: "1st degree", desc: "Already connected — message directly" },
                            { value: 2, label: "2nd degree", desc: "Connect first, then message" },
                            { value: 3, label: "3rd degree", desc: "Connect first, then message" },
                          ].map((item) => (
                            <label
                              key={item.value}
                              className="flex items-center gap-3 rounded-lg border border-zinc-800/80 bg-zinc-900/50 px-4 py-3 cursor-pointer hover:bg-zinc-800/50 transition-colors"
                            >
                              <Checkbox
                                checked={field.value?.includes(item.value)}
                                onCheckedChange={(checked) => {
                                  const current = field.value || [];
                                  if (checked) {
                                    field.onChange([...current, item.value].sort());
                                  } else {
                                    field.onChange(current.filter((d) => d !== item.value));
                                  }
                                }}
                              />
                              <div className="flex flex-col">
                                <span className="text-sm font-medium text-zinc-100">{item.label}</span>
                                <span className="text-xs text-zinc-400">{item.desc}</span>
                              </div>
                            </label>
                          ))}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="productPitch"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Product Pitch</FormLabel>
                        <FormControl>
                          <Textarea
                            className={`${zincTextareaClassName} min-h-[160px] resize-y`}
                            placeholder={`Describe your product/service: what it does, who it's for, and why it matters.\n\nExample:\nLenGrowth is a growth operating system that helps teams turn ideas into actual progress. It gets the context of your business, shows you what really matters today, and gives you the path to growth with the best wins first.\n\nWe help with: figuring out what to do next for your growth, turning good ideas into tasks people actually finish, keeping work visible so it does not get lost...`}
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          <span
                            className={
                              productPitchValue.length > 0 &&
                              productPitchValue.length < 300
                                ? "text-red-400"
                                : ""
                            }
                          >
                            {productPitchValue.length}/300 min characters
                          </span>
                          {" - "}
                          This is what the agent uses to understand your product
                          and talk about it with leads.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </TabsContent>

                <TabsContent
                  value="strategy"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="followUpStrategy"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Follow-Up Strategy</FormLabel>
                        <FormControl>
                          <Textarea
                            className={`${zincTextareaClassName} min-h-[200px] resize-y`}
                            placeholder={`Describe how the agent should approach follow-up conversations.\n\nExample:\n1. Discovery Mode (Default):\n   - Ask about their current growth process\n   - Understand their biggest growth challenges\n   - Learn about their current tools and systems\n\n2. Pitch Mode (When signal detected):\n   - Connect their specific challenges to our capabilities\n   - Focus on strategic alignment and execution\n   - Suggest a demo or strategy session using the booking link\n\n3. Key Differentiators:\n   - Full stack platform (not just analytics)\n   - Hybrid execution with AI AND human options\n   - Designed for both founders and teams`}
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Instructions for how the agent should behave in
                          follow-up conversations. Include discovery questions,
                          when to pitch, and key differentiators.
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
                            Maximum connections per day
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

                </TabsContent>

              </div>
            </Tabs>

            <DialogFooter className={`${zincDialogFooterClassName} flex-shrink-0`}>
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
