"use client";

import { useState, useEffect } from "react";
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
  CampaignTemplate,
  CampaignTemplateCreateData,
} from "@/lib/types/components";
import {
  zincDialogContentClassName,
  zincDialogFooterClassName,
  zincDialogHeaderClassName,
  zincInputClassName,
  zincSectionClassName,
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
  product_pitch: z
    .string()
    .optional()
    .refine((v) => !v || v.length >= 300, {
      message: "Product pitch must be at least 300 characters",
    }),
  campaign_objective: z.string().optional(),
  booking_link: z
    .string()
    .url("Must be a valid URL")
    .optional()
    .or(z.literal("")),
  icp_titles: z.string().optional(),
  follow_up_strategy: z.string().optional(),
  ghost_mode_enabled: z.boolean(),
  velocity: z.number().min(1).max(100),
  cooldown_minutes: z.number().min(1).max(1440),
  is_public: z.boolean(),
});

type FormValues = z.infer<typeof formSchema>;

interface TemplateFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template?: CampaignTemplate | null;
  onSubmit: (data: CampaignTemplateCreateData) => void;
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

export function TemplateForm({
  open,
  onOpenChange,
  template,
  onSubmit,
  isEditing = false,
}: TemplateFormProps) {
  const [loading, setLoading] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      description: undefined,
      product_pitch: undefined,
      campaign_objective: undefined,
      booking_link: undefined,
      icp_titles: undefined,
      follow_up_strategy: undefined,
      ghost_mode_enabled: false,
      velocity: 20,
      cooldown_minutes: 0,
      is_public: false,
    },
  });

  useEffect(() => {
    if (template) {
      form.reset({
        name: template.name,
        description: template.description || undefined,
        product_pitch: template.product_pitch || undefined,
        campaign_objective: template.campaign_objective || undefined,
        booking_link: template.booking_link || undefined,
        icp_titles: formatIcpTitles(template.icp_titles),
        follow_up_strategy: template.follow_up_strategy || undefined,
        ghost_mode_enabled: template.ghost_mode_enabled,
        velocity: template.velocity,
        cooldown_minutes: template.cooldown_minutes,
        is_public: template.is_public,
      });
    } else {
      form.reset({
        name: "",
        description: undefined,
        product_pitch: undefined,
        campaign_objective: undefined,
        booking_link: undefined,
        icp_titles: undefined,
        follow_up_strategy: undefined,
        ghost_mode_enabled: false,
        velocity: 20,
        cooldown_minutes: 0,
        is_public: false,
      });
    }
  }, [template, form]);

  const handleSubmit = async (values: FormValues) => {
    setLoading(true);
    try {
      const payload: CampaignTemplateCreateData = {
        ...values,
        icp_titles: parseIcpTitles(values.icp_titles),
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

  const productPitchValue = form.watch("product_pitch") || "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={`${zincDialogContentClassName} max-h-[90vh] overflow-hidden p-0 sm:max-w-[860px]`}
      >
        <DialogHeader
          className={`${zincDialogHeaderClassName} px-6 pt-6 sm:px-8 sm:pt-8`}
        >
          <DialogTitle>
            {isEditing ? "Edit Template" : "Create New Template"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update your campaign template details and settings."
              : "Create a new campaign template for reuse across multiple campaigns."}
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
                className={`${zincTabsListClassName} grid grid-cols-2 gap-1 md:grid-cols-5`}
              >
                <TabsTrigger className={zincTabsTriggerClassName} value="basic">
                  Basic Info
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
                <TabsTrigger
                  className={zincTabsTriggerClassName}
                  value="visibility"
                >
                  Visibility
                </TabsTrigger>
              </TabsList>

              <div className="mt-6 max-h-[calc(90vh-250px)] overflow-y-auto pr-1">
                <TabsContent
                  value="basic"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Template Name</FormLabel>
                        <FormControl>
                          <Input
                            className={zincInputClassName}
                            placeholder="Enter template name"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          A descriptive name for your template
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
                            placeholder="Describe what this template is for..."
                            className={`${zincTextareaClassName} min-h-[100px] resize-y`}
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Description of the template (no character limit)
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="campaign_objective"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Campaign Objective</FormLabel>
                        <FormControl>
                          <Textarea
                            className={`${zincTextareaClassName} min-h-[80px] resize-y`}
                            placeholder="What are you trying to achieve?"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          The primary goal for campaigns using this template
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="booking_link"
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
                  value="targeting"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="icp_titles"
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
                          Comma-separated list of target job titles and roles.
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
                    name="product_pitch"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Product Pitch</FormLabel>
                        <FormControl>
                          <Textarea
                            className={`${zincTextareaClassName} min-h-[160px] resize-y`}
                            placeholder="Describe your product/service: what it does, who it's for, and why it matters..."
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
                          What the agent uses to understand and pitch your
                          product.
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
                    name="follow_up_strategy"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Follow-Up Strategy</FormLabel>
                        <FormControl>
                          <Textarea
                            className={`${zincTextareaClassName} min-h-[200px] resize-y`}
                            placeholder={`Describe how the agent should approach follow-up conversations.\n\nExample:\n1. Discovery Mode (Default): Ask about their current process\n2. Pitch Mode (When signal detected): Connect challenges to capabilities\n3. Key Differentiators: List what makes your product unique`}
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Instructions for the agent&apos;s follow-up
                          conversation behavior.
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
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="velocity"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Daily Velocity</FormLabel>
                          <FormControl>
                            <Input
                              className={zincInputClassName}
                              type="number"
                              min="1"
                              max="100"
                              placeholder="20"
                              {...field}
                              onChange={(e) =>
                                field.onChange(parseInt(e.target.value, 10))
                              }
                            />
                          </FormControl>
                          <FormDescription>
                            Max daily connections
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="cooldown_minutes"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Cooldown (minutes)</FormLabel>
                          <FormControl>
                            <Input
                              className={zincInputClassName}
                              type="number"
                              min="0"
                              max="1440"
                              placeholder="0"
                              {...field}
                              onChange={(e) =>
                                field.onChange(parseInt(e.target.value, 10))
                              }
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
                    name="ghost_mode_enabled"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">
                            Ghost Mode Enabled
                          </FormLabel>
                          <FormDescription>
                            Enable ghost mode for campaigns using this template
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
                  value="visibility"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="is_public"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">
                            Public Template
                          </FormLabel>
                          <FormDescription>
                            Make this template available to all team members
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
                    ? "Update Template"
                    : "Create Template"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
