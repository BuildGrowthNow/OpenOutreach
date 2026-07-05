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
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TrackedLink } from "@/lib/api/dashboard";
import {
  zincDialogContentClassName,
  zincDialogFooterClassName,
  zincDialogHeaderClassName,
  zincInputClassName,
  zincSectionClassName,
  zincTabsListClassName,
  zincTabsTriggerClassName,
} from "@/lib/modal-styles";

const formSchema = z.object({
  original_url: z.string().url("Must be a valid URL").min(1, "URL is required"),
  campaign_id: z.string().optional(),
  is_active: z.boolean(),
  utm_source: z.string().optional().or(z.literal("")),
  utm_medium: z.string().optional().or(z.literal("")),
  utm_campaign: z.string().optional().or(z.literal("")),
  utm_term: z.string().optional().or(z.literal("")),
  utm_content: z.string().optional().or(z.literal("")),
});

type FormValues = z.infer<typeof formSchema>;

interface LinkFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  link?: TrackedLink | null;
  campaignId?: string;
  onSubmit: (data: Partial<TrackedLink>) => void;
  isEditing?: boolean;
}

export function LinkForm({
  open,
  onOpenChange,
  link,
  campaignId,
  onSubmit,
  isEditing = false,
}: LinkFormProps) {
  const [loading, setLoading] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      original_url: "",
      campaign_id: "",
      is_active: true,
      utm_source: "",
      utm_medium: "",
      utm_campaign: "",
      utm_term: "",
      utm_content: "",
    },
  });

  useEffect(() => {
    if (link) {
      form.reset({
        original_url: link.original_url,
        campaign_id: link.campaign?.id ?? campaignId ?? "",
        is_active: link.is_active ?? true,
        utm_source: link.utm_source ?? "",
        utm_medium: link.utm_medium ?? "",
        utm_campaign: link.utm_campaign ?? "",
        utm_term: link.utm_term ?? "",
        utm_content: link.utm_content ?? "",
      });
    } else {
      form.reset({
        original_url: "",
        campaign_id: campaignId ?? "",
        is_active: true,
        utm_source: "",
        utm_medium: "",
        utm_campaign: "",
        utm_term: "",
        utm_content: "",
      });
    }
  }, [link, campaignId, form, open]);

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={`${zincDialogContentClassName} max-h-[90vh] overflow-hidden p-0 sm:max-w-[760px]`}
      >
        <DialogHeader
          className={`${zincDialogHeaderClassName} px-6 pt-6 sm:px-8 sm:pt-8`}
        >
          <DialogTitle>
            {isEditing ? "Edit Tracked Link" : "Create Tracked Link"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update your tracked link settings and UTM parameters."
              : "Create a new tracked link to measure campaign effectiveness."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(handleSubmit)}
            className="flex max-h-[calc(90vh-92px)] flex-col"
          >
            <Tabs
              defaultValue="link"
              className="flex-1 overflow-hidden px-6 py-6 sm:px-8 sm:py-8"
            >
              <TabsList
                className={`${zincTabsListClassName} grid grid-cols-1 gap-1 md:grid-cols-2`}
              >
                <TabsTrigger className={zincTabsTriggerClassName} value="link">
                  Link Settings
                </TabsTrigger>
                <TabsTrigger className={zincTabsTriggerClassName} value="utm">
                  UTM Parameters
                </TabsTrigger>
              </TabsList>

              <div className="mt-6 max-h-[calc(90vh-250px)] overflow-y-auto pr-1">
                <TabsContent
                  value="link"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <FormField
                    control={form.control}
                    name="original_url"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Original URL</FormLabel>
                        <FormControl>
                          <Input
                            className={zincInputClassName}
                            placeholder="https://example.com/landing-page"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          The destination URL where visitors will be directed
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <div className="flex items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                    <div className="space-y-0.5">
                      <FormLabel className="text-base">Active</FormLabel>
                      <FormDescription>
                        When enabled, this link will redirect and track clicks
                      </FormDescription>
                    </div>
                    <FormControl>
                      <FormField
                        control={form.control}
                        name="is_active"
                        render={({ field }) => (
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        )}
                      />
                    </FormControl>
                  </div>
                </TabsContent>

                <TabsContent
                  value="utm"
                  className={`${zincSectionClassName} space-y-4`}
                >
                  <div className="space-y-3">
                    <FormLabel className="text-sm font-medium">
                      UTM Parameters
                    </FormLabel>
                    <FormDescription className="mb-3 text-xs text-zinc-400">
                      Add UTM parameters to track campaign performance
                      (optional)
                    </FormDescription>

                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="utm_source"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>UTM Source</FormLabel>
                            <FormControl>
                              <Input
                                className={zincInputClassName}
                                placeholder="linkedin"
                                {...field}
                              />
                            </FormControl>
                            <FormDescription>
                              Where the traffic comes from
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="utm_medium"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>UTM Medium</FormLabel>
                            <FormControl>
                              <Input
                                className={zincInputClassName}
                                placeholder="social"
                                {...field}
                              />
                            </FormControl>
                            <FormDescription>
                              The marketing medium
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="utm_campaign"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>UTM Campaign</FormLabel>
                            <FormControl>
                              <Input
                                className={zincInputClassName}
                                placeholder="campaign-name"
                                {...field}
                              />
                            </FormControl>
                            <FormDescription>
                              The specific campaign name
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="utm_term"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>UTM Term</FormLabel>
                            <FormControl>
                              <Input
                                className={zincInputClassName}
                                placeholder="keyword"
                                {...field}
                              />
                            </FormControl>
                            <FormDescription>
                              Used for paid search
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="utm_content"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>UTM Content</FormLabel>
                            <FormControl>
                              <Input
                                className={zincInputClassName}
                                placeholder="content-variation"
                                {...field}
                              />
                            </FormControl>
                            <FormDescription>
                              Used for A/B testing
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
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
                    ? "Update Link"
                    : "Create Link"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
