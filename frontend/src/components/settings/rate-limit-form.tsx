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
import { Icons } from "@/lib/types/components";
import { updateSettings } from "@/lib/api/dashboard";

interface BackendRateLimits {
  daily_connection_limit: number;
  daily_follow_up_limit: number;
  velocity: number;
  cooldown_minutes: number;
}

const rateLimitSchema = z.object({
  dailyConnectionLimit: z.number().min(1).max(100),
  dailyFollowUpLimit: z.number().min(1).max(100),
  velocity: z.number().min(1).max(100),
  cooldownMinutes: z.number().min(0).max(1440),
});

type RateLimitFormValues = z.infer<typeof rateLimitSchema>;

interface RateLimitFormProps {
  initialData: BackendRateLimits;
  onSuccess?: () => void;
}

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
      dailyConnectionLimit: initialData?.daily_connection_limit || 20,
      dailyFollowUpLimit: initialData?.daily_follow_up_limit || 25,
      velocity: initialData?.velocity || 20,
      cooldownMinutes: initialData?.cooldown_minutes || 0,
    },
  });

  const onSubmit = async (values: RateLimitFormValues) => {
    try {
      setIsSubmitting(true);
      setError(null);
      setSuccess(false);

      const response = await updateSettings({
        rate_limits: {
          daily_connection_limit: values.dailyConnectionLimit,
          daily_follow_up_limit: values.dailyFollowUpLimit,
          velocity: values.velocity,
          cooldown_minutes: values.cooldownMinutes,
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

  const connectLimit = form.watch("dailyConnectionLimit");
  const followUpLimit = form.watch("dailyFollowUpLimit");
  const velocity = form.watch("velocity");
  const cooldownMinutes = form.watch("cooldownMinutes");

  const safety = (() => {
    if (connectLimit <= 20 && followUpLimit <= 15) {
      return {
        label: "Very Safe",
        tone: "text-green-500",
        note: "Conservative daily volume with plenty of margin.",
      };
    }
    if (connectLimit <= 30 && followUpLimit <= 25) {
      return {
        label: "Safe",
        tone: "text-emerald-500",
        note: "Good default range for steady outreach.",
      };
    }
    if (connectLimit <= 50 && followUpLimit <= 40) {
      return {
        label: "Moderate",
        tone: "text-yellow-500",
        note: "Higher throughput - keep message quality and spacing tight.",
      };
    }
    if (connectLimit <= 70 && followUpLimit <= 60) {
      return {
        label: "Risky",
        tone: "text-orange-500",
        note: "Aggressive volume can increase account scrutiny.",
      };
    }
    return {
      label: "High Risk",
      tone: "text-red-500",
      note: "Very high volume is more likely to trigger restrictions.",
    };
  })();

  const cadenceLabel =
    cooldownMinutes === 0
      ? "No enforced cooldown"
      : cooldownMinutes < 15
        ? "Fast cadence"
        : cooldownMinutes < 60
          ? "Balanced cadence"
          : "Slow cadence";

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

        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardContent className="pt-6 space-y-2">
              <div className="flex items-center gap-2">
                <Icons.Shield className="h-4 w-4 text-blue-500" />
                <h3 className="font-semibold">Safety assessment</h3>
              </div>
              <p className={`text-lg font-semibold ${safety.tone}`}>
                {safety.label}
              </p>
              <p className="text-sm text-muted-foreground">{safety.note}</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6 space-y-2">
              <div className="flex items-center gap-2">
                <Icons.Clock className="h-4 w-4 text-blue-500" />
                <h3 className="font-semibold">Cadence</h3>
              </div>
              <p className="text-lg font-semibold">{cadenceLabel}</p>
              <p className="text-sm text-muted-foreground">
                Velocity {velocity}/day with {cooldownMinutes} min between
                actions.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6 space-y-2">
              <div className="flex items-center gap-2">
                <Icons.AlertTriangle className="h-4 w-4 text-blue-500" />
                <h3 className="font-semibold">LinkedIn guidelines</h3>
              </div>
              <ul className="space-y-1 text-sm text-muted-foreground">
                <li>20-30 new connections per day is a safer default.</li>
                <li>Spread activity across the day instead of bursting.</li>
                <li>Lower limits matter less if message quality is poor.</li>
              </ul>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <FormField
            control={form.control}
            name="dailyConnectionLimit"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Daily connection limit</FormLabel>
                <div className="space-y-4 rounded-lg border p-4">
                  <FormControl>
                    <div className="flex items-center gap-4">
                      <SingleValueSlider
                        min={1}
                        max={100}
                        value={field.value}
                        onChange={field.onChange}
                      />
                      <Input
                        type="number"
                        min={1}
                        max={100}
                        value={field.value}
                        onChange={(event) =>
                          field.onChange(parseInt(event.target.value, 10) || 0)
                        }
                        className="w-20 text-center"
                      />
                    </div>
                  </FormControl>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Safe up to 20</span>
                    <span>Moderate up to 50</span>
                    <span>Above 50 is aggressive</span>
                  </div>
                </div>
                <FormDescription>
                  Maximum new connection requests per day.
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
                <FormLabel>Daily follow-up limit</FormLabel>
                <div className="space-y-4 rounded-lg border p-4">
                  <FormControl>
                    <div className="flex items-center gap-4">
                      <SingleValueSlider
                        min={1}
                        max={100}
                        value={field.value}
                        onChange={field.onChange}
                      />
                      <Input
                        type="number"
                        min={1}
                        max={100}
                        value={field.value}
                        onChange={(event) =>
                          field.onChange(parseInt(event.target.value, 10) || 0)
                        }
                        className="w-20 text-center"
                      />
                    </div>
                  </FormControl>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Safer up to 15</span>
                    <span>Moderate up to 40</span>
                    <span>Above 40 is aggressive</span>
                  </div>
                </div>
                <FormDescription>
                  Maximum follow-up messages per day.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="velocity"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Velocity</FormLabel>
                <div className="space-y-4 rounded-lg border p-4">
                  <FormControl>
                    <div className="flex items-center gap-4">
                      <SingleValueSlider
                        min={1}
                        max={100}
                        value={field.value}
                        onChange={field.onChange}
                      />
                      <Input
                        type="number"
                        min={1}
                        max={100}
                        value={field.value}
                        onChange={(event) =>
                          field.onChange(parseInt(event.target.value, 10) || 0)
                        }
                        className="w-20 text-center"
                      />
                    </div>
                  </FormControl>
                </div>
                <FormDescription>
                  Target maximum actions per day across the planner.
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
                <FormLabel>Cooldown between actions (minutes)</FormLabel>
                <div className="space-y-4 rounded-lg border p-4">
                  <FormControl>
                    <div className="flex items-center gap-4">
                      <SingleValueSlider
                        min={0}
                        max={180}
                        value={Math.min(field.value, 180)}
                        onChange={field.onChange}
                      />
                      <Input
                        type="number"
                        min={0}
                        max={1440}
                        value={field.value}
                        onChange={(event) =>
                          field.onChange(parseInt(event.target.value, 10) || 0)
                        }
                        className="w-20 text-center"
                      />
                    </div>
                  </FormControl>
                </div>
                <FormDescription>
                  Minimum pause between actions. Set to 0 to let the scheduler
                  decide freely.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-4 rounded-xl border p-4 md:grid-cols-4">
          <div>
            <p className="text-2xl font-semibold">{connectLimit}</p>
            <p className="text-sm text-muted-foreground">Connections / day</p>
          </div>
          <div>
            <p className="text-2xl font-semibold">{followUpLimit}</p>
            <p className="text-sm text-muted-foreground">Follow-ups / day</p>
          </div>
          <div>
            <p className="text-2xl font-semibold">{velocity}</p>
            <p className="text-sm text-muted-foreground">Velocity target</p>
          </div>
          <div>
            <p className="text-2xl font-semibold">{cooldownMinutes}m</p>
            <p className="text-sm text-muted-foreground">Cooldown</p>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t pt-6">
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              form.reset({
                dailyConnectionLimit: initialData?.daily_connection_limit || 20,
                dailyFollowUpLimit: initialData?.daily_follow_up_limit || 25,
                velocity: initialData?.velocity || 20,
                cooldownMinutes: initialData?.cooldown_minutes || 0,
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
                Save rate limits
              </>
            )}
          </Button>
        </div>
      </form>
    </Form>
  );
}
