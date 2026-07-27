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
import { Slider } from "@/components/ui/slider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Icons } from "@/lib/types/components";
import { updateSettings } from "@/lib/api/dashboard";
import { Badge } from "@/components/ui/badge";
import { Info } from "lucide-react";

type AggressivenessPreset =
  | "very_slow"
  | "slow"
  | "average"
  | "aggressive"
  | "very_aggressive";

interface BackendRateLimits {
  dailyConnectionLimit: number;
  dailyFollowUpLimit: number;
  velocity: number;
  enableSmartRateLimiting?: boolean;
  aggressivenessPreset?: AggressivenessPreset;
}

const rateLimitSchema = z.object({
  enableSmartRateLimiting: z.boolean(),
  aggressivenessPreset: z.enum([
    "very_slow",
    "slow",
    "average",
    "aggressive",
    "very_aggressive",
  ]),
  dailyConnectionLimit: z.number().min(1).max(200),
  dailyFollowUpLimit: z.number().min(1).max(200),
  velocity: z.number().min(1).max(120),
});

type RateLimitFormValues = z.infer<typeof rateLimitSchema>;

interface RateLimitFormProps {
  initialData: BackendRateLimits;
  onSuccess?: () => void;
}

const PRESETS = {
  very_slow: {
    label: "Very Slow",
    badge: "Safest",
    badgeVariant: "default" as const,
    description: "~10 actions/hour • Best for new accounts or high-risk audiences",
    spacing: "~6 min between actions",
  },
  slow: {
    label: "Slow",
    badge: null,
    badgeVariant: null,
    description: "~15 actions/hour • Cautious pacing for established accounts",
    spacing: "~4 min between actions",
  },
  average: {
    label: "Average",
    badge: "Recommended",
    badgeVariant: "secondary" as const,
    description: "~20 actions/hour • Balanced approach for most users",
    spacing: "~3 min between actions",
  },
  aggressive: {
    label: "Aggressive",
    badge: null,
    badgeVariant: null,
    description: "~40 actions/hour • Fast pacing for warm audiences",
    spacing: "~1-2 min between actions",
  },
  very_aggressive: {
    label: "Very Aggressive",
    badge: "Riskiest",
    badgeVariant: "destructive" as const,
    description: "~60 actions/hour • Maximum speed with highest detection risk",
    spacing: "~30-60 sec between actions",
  },
};

function SingleValueSlider({
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <Slider
      min={min}
      max={max}
      step={step}
      value={[value]}
      onValueChange={(nextValue) =>
        onChange(Array.isArray(nextValue) ? nextValue[0] : nextValue)
      }
      className="flex-1"
    />
  );
}

export default function RateLimitForm({
  initialData,
  onSuccess,
}: RateLimitFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const form = useForm<RateLimitFormValues>({
    resolver: zodResolver(rateLimitSchema),
    defaultValues: {
      enableSmartRateLimiting: initialData?.enableSmartRateLimiting ?? false,
      aggressivenessPreset: initialData?.aggressivenessPreset ?? "average",
      dailyConnectionLimit: initialData?.dailyConnectionLimit ?? 20,
      dailyFollowUpLimit: initialData?.dailyFollowUpLimit ?? 25,
      velocity: initialData?.velocity ?? 20,
    },
  });

  const onSubmit = async (values: RateLimitFormValues) => {
    try {
      setIsSubmitting(true);
      setError(null);
      setSuccess(false);

      const response = await updateSettings({
        rateLimits: {
          enableSmartRateLimiting: values.enableSmartRateLimiting,
          aggressivenessPreset: values.aggressivenessPreset,
          dailyConnectionLimit: values.dailyConnectionLimit,
          dailyFollowUpLimit: values.dailyFollowUpLimit,
          velocity: values.velocity,
        },
      });

      if (response.data) {
        setSuccess(true);
        onSuccess?.();
        setTimeout(() => setSuccess(false), 3000);
        return;
      }

      setError("Failed to update rate limits");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const smartMode = form.watch("enableSmartRateLimiting");
  const preset = form.watch("aggressivenessPreset");
  const connectLimit = form.watch("dailyConnectionLimit");
  const followUpLimit = form.watch("dailyFollowUpLimit");
  const velocity = form.watch("velocity");

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
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
              Rate limits updated successfully.
            </AlertDescription>
          </Alert>
        )}

        {/* Smart Rate Limiting Toggle */}
        <FormField
          control={form.control}
          name="enableSmartRateLimiting"
          render={({ field }) => (
            <FormItem className="flex flex-row items-start justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <FormLabel className="text-base">
                  Smart Rate Limiting
                </FormLabel>
                <FormDescription>
                  Automatically adjust pacing based on time-of-day and engagement patterns to stay within safe limits
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

        {smartMode ? (
          /* SMART MODE: Show Presets */
          <div className="space-y-4">
            <FormField
              control={form.control}
              name="aggressivenessPreset"
              render={({ field }) => (
                <FormItem className="space-y-3">
                  <FormLabel>Aggressiveness Level</FormLabel>
                  <FormControl>
                    <RadioGroup
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      className="space-y-3"
                    >
                      {Object.entries(PRESETS).map(([value, config]) => (
                        <div
                          key={value}
                          className="flex items-center space-x-3 rounded-lg border p-4 hover:bg-accent cursor-pointer"
                          onClick={() => field.onChange(value)}
                        >
                          <RadioGroupItem value={value} id={value} />
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <label
                                htmlFor={value}
                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                              >
                                {config.label}
                              </label>
                              {config.badge && (
                                <Badge variant={config.badgeVariant}>
                                  {config.badge}
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">
                              {config.description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </RadioGroup>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Info Box */}
            <Card className="bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800">
              <CardContent className="pt-6">
                <div className="flex gap-3">
                  <Info className="h-5 w-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                  <div className="space-y-2 text-sm text-blue-900 dark:text-blue-100">
                    <p className="font-medium">Smart mode automatically adjusts pacing based on:</p>
                    <ul className="list-disc list-inside space-y-1 ml-2">
                      <li>Time of day (more actions 9am-6pm, fewer at night)</li>
                      <li>Day of week (reduced activity on weekends)</li>
                      <li>Detectability score (slows down if suspicious patterns detected)</li>
                      <li>Lead engagement (prioritizes hot leads over cold)</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          /* MANUAL MODE: Show Controls */
          <div className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <FormField
                control={form.control}
                name="dailyConnectionLimit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Daily Connection Limit</FormLabel>
                    <div className="space-y-4 rounded-lg border p-4">
                      <FormControl>
                        <div className="flex items-center gap-4">
                          <SingleValueSlider
                            min={1}
                            max={200}
                            value={field.value}
                            onChange={field.onChange}
                          />
                          <Input
                            type="number"
                            min={1}
                            max={200}
                            value={field.value}
                            onChange={(event) =>
                              field.onChange(parseInt(event.target.value, 10) || 0)
                            }
                            className="w-20 text-center"
                          />
                        </div>
                      </FormControl>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Safe: ≤20</span>
                        <span>Moderate: ≤50</span>
                        <span>Aggressive: &gt;50</span>
                      </div>
                    </div>
                    <FormDescription>
                      Maximum new connection requests per day (per LinkedIn profile)
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="dailyFollowUpLimit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Daily Follow-up Limit</FormLabel>
                    <div className="space-y-4 rounded-lg border p-4">
                      <FormControl>
                        <div className="flex items-center gap-4">
                          <SingleValueSlider
                            min={1}
                            max={200}
                            value={field.value}
                            onChange={field.onChange}
                          />
                          <Input
                            type="number"
                            min={1}
                            max={200}
                            value={field.value}
                            onChange={(event) =>
                              field.onChange(parseInt(event.target.value, 10) || 0)
                            }
                            className="w-20 text-center"
                          />
                        </div>
                      </FormControl>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Safe: ≤25</span>
                        <span>Moderate: ≤40</span>
                        <span>Aggressive: &gt;40</span>
                      </div>
                    </div>
                    <FormDescription>
                      Maximum follow-up messages per day (per LinkedIn profile)
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="velocity"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Velocity (actions per hour)</FormLabel>
                  <div className="space-y-4 rounded-lg border p-4">
                    <FormControl>
                      <div className="flex items-center gap-4">
                        <SingleValueSlider
                          min={1}
                          max={120}
                          value={field.value}
                          onChange={field.onChange}
                        />
                        <Input
                          type="number"
                          min={1}
                          max={120}
                          value={field.value}
                          onChange={(event) =>
                            field.onChange(parseInt(event.target.value, 10) || 0)
                          }
                          className="w-20 text-center"
                        />
                      </div>
                    </FormControl>
                    <div className="text-xs text-muted-foreground">
                      {velocity >= 30
                        ? `High-frequency: actions run back-to-back with short gaps (~${Math.round(3600 / velocity)}s between each)`
                        : `Spread evenly: actions are spaced ~${Math.round(60 / velocity)} min apart throughout the day`}
                    </div>
                  </div>
                  <FormDescription>
                    ≥30 actions/hr runs them back-to-back; below 30 spaces them throughout the day
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        )}

        {/* Summary Cards */}
        <div className="grid gap-4 rounded-xl border p-4 md:grid-cols-3">
          <div>
            <p className="text-2xl font-semibold">{connectLimit}</p>
            <p className="text-sm text-muted-foreground">Connections / day</p>
          </div>
          <div>
            <p className="text-2xl font-semibold">{followUpLimit}</p>
            <p className="text-sm text-muted-foreground">Follow-ups / day</p>
          </div>
          <div>
            <p className="text-2xl font-semibold">
              {smartMode ? PRESETS[preset].label : `${velocity}/hr`}
            </p>
            <p className="text-sm text-muted-foreground">
              {smartMode ? "Smart preset" : "Manual velocity"}
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t pt-6">
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              form.reset({
                enableSmartRateLimiting: initialData?.enableSmartRateLimiting ?? false,
                aggressivenessPreset: initialData?.aggressivenessPreset ?? "average",
                dailyConnectionLimit: initialData?.dailyConnectionLimit || 20,
                dailyFollowUpLimit: initialData?.dailyFollowUpLimit || 25,
                velocity: initialData?.velocity || 20,
              })
            }
            disabled={isSubmitting}
          >
            Reset
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Icons.Save className="mr-2 h-4 w-4" />
                Save changes
              </>
            )}
          </Button>
        </div>
      </form>
    </Form>
  );
}
