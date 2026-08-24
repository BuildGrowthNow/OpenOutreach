"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Icons } from "@/lib/types/components";
import { updateSettings, type Settings } from "@/lib/api/dashboard";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const waSettingsSchema = z.object({
  dailyLimit: z.number().int().min(0).max(500),
  enableActiveHours: z.boolean(),
  activeStartHour: z.number().int().min(0).max(23),
  activeEndHour: z.number().int().min(0).max(23),
  activeDays: z.string(),
});

type WaSettingsForm = z.infer<typeof waSettingsSchema>;

interface WarmupStatus {
  warmupAgeDays?: number;
  warmupEffectiveLimit?: number;
  warmupDone?: boolean;
  warmupTotalDays?: number;
}

interface Props {
  initialData: NonNullable<Settings["whatsapp"]> & WarmupStatus;
  onSuccess: () => void;
}

function WarmupCard({ data }: { data: WarmupStatus & { dailyLimit?: number } }) {
  const ageDays = data.warmupAgeDays ?? 0;
  const totalDays = data.warmupTotalDays ?? 30;
  const effectiveLimit = data.warmupEffectiveLimit ?? data.dailyLimit ?? 20;
  const done = data.warmupDone ?? false;
  const pct = done ? 100 : Math.round((ageDays / totalDays) * 100);

  return (
    <div className="rounded-lg border p-4 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Warmup status</span>
        {done ? (
          <span className="text-xs font-medium text-emerald-500">Complete</span>
        ) : (
          <span className="text-xs text-muted-foreground">Day {ageDays} of {totalDays}</span>
        )}
      </div>
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        {done
          ? `Sending at full ceiling of ${data.dailyLimit ?? effectiveLimit} messages/day.`
          : `Sending ${effectiveLimit} messages/day today - ceiling reached on day ${totalDays}.`
        }
      </p>
    </div>
  );
}

function parseDays(raw: string): number[] {
  return raw
    .split(",")
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => n >= 1 && n <= 7);
}

function formatDays(days: number[]): string {
  return [...new Set(days)].sort((a, b) => a - b).join(",");
}

export default function WhatsappSettingsForm({ initialData, onSuccess }: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const form = useForm<WaSettingsForm>({
    resolver: zodResolver(waSettingsSchema),
    defaultValues: {
      dailyLimit: initialData.dailyLimit ?? 20,
      enableActiveHours: initialData.enableActiveHours ?? false,
      activeStartHour: initialData.activeStartHour ?? 8,
      activeEndHour: initialData.activeEndHour ?? 21,
      activeDays: initialData.activeDays ?? "1,2,3,4,5,6,7",
    },
  });

  const enableActiveHours = form.watch("enableActiveHours");
  const activeDaysValue = form.watch("activeDays");
  const selectedDays = parseDays(activeDaysValue);

  const toggleDay = (day: number) => {
    const current = parseDays(form.getValues("activeDays"));
    const next = current.includes(day)
      ? current.filter((d) => d !== day)
      : [...current, day];
    form.setValue("activeDays", formatDays(next.length ? next : [day]), {
      shouldValidate: true,
    });
  };

  const onSubmit = async (values: WaSettingsForm) => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const res = await updateSettings({
        whatsapp: {
          dailyLimit: values.dailyLimit,
          enableActiveHours: values.enableActiveHours,
          activeStartHour: values.activeStartHour,
          activeEndHour: values.activeEndHour,
          activeDays: values.activeDays,
        },
      });
      if (res.error) throw new Error(res.error);
      setSuccess(true);
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>WhatsApp Rate Limits &amp; Active Hours</CardTitle>
        <CardDescription>
          Control how many WhatsApp messages are sent per day and when the automation is allowed to run.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <WarmupCard data={initialData} />

            <FormField
              control={form.control}
              name="dailyLimit"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Daily limit ceiling</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      min={0}
                      max={500}
                      {...field}
                      onChange={(e) => field.onChange(parseInt(e.target.value, 10) || 0)}
                    />
                  </FormControl>
                  <FormDescription>
                    Maximum messages/day once warmup completes (day 30+). During warmup the actual
                    limit ramps up automatically - this field is the post-warmup ceiling.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="enableActiveHours"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel>WhatsApp-specific active hours</FormLabel>
                    <FormDescription>
                      Restrict WhatsApp messages to a custom time window, independent of LinkedIn active hours.
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />

            {enableActiveHours && (
              <div className="space-y-4 rounded-lg border p-4">
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="activeStartHour"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Start hour (0–23)</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min={0}
                            max={23}
                            {...field}
                            onChange={(e) => field.onChange(parseInt(e.target.value, 10) || 0)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="activeEndHour"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>End hour (0–23)</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min={0}
                            max={23}
                            {...field}
                            onChange={(e) => field.onChange(parseInt(e.target.value, 10) || 0)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="activeDays"
                  render={() => (
                    <FormItem>
                      <FormLabel>Active days</FormLabel>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {DAY_LABELS.map((label, i) => {
                          const day = i + 1;
                          const active = selectedDays.includes(day);
                          return (
                            <button
                              key={day}
                              type="button"
                              onClick={() => toggleDay(day)}
                              className={`rounded-md px-3 py-1 text-sm font-medium border transition-colors ${
                                active
                                  ? "bg-primary text-primary-foreground border-primary"
                                  : "border-border text-muted-foreground hover:bg-muted"
                              }`}
                            >
                              {label}
                            </button>
                          );
                        })}
                      </div>
                      <FormDescription>
                        WhatsApp messages only send on selected days.
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            )}

            {error && (
              <Alert variant="destructive">
                <Icons.AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert>
                <Icons.CheckCircle className="h-4 w-4" />
                <AlertDescription>WhatsApp settings saved.</AlertDescription>
              </Alert>
            )}

            <Button type="submit" disabled={saving}>
              {saving && <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
              Save WhatsApp settings
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
