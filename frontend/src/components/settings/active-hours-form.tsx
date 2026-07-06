"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Icons } from "@/lib/types/components";
import { updateSettings, type Settings } from "@/lib/api/dashboard";
import { useToast } from "@/components/ui/use-toast";
import { Clock, Calendar, Globe } from "lucide-react";

interface ActiveHoursFormProps {
  settings: Settings;
  onUpdate: () => void;
}

const TIMEZONES = [
  { value: "UTC", label: "UTC" },
  { value: "America/New_York", label: "Eastern Time (US)" },
  { value: "America/Chicago", label: "Central Time (US)" },
  { value: "America/Denver", label: "Mountain Time (US)" },
  { value: "America/Los_Angeles", label: "Pacific Time (US)" },
  { value: "Europe/London", label: "London (GMT)" },
  { value: "Europe/Paris", label: "Paris (CET)" },
  { value: "Europe/Berlin", label: "Berlin (CET)" },
  { value: "Asia/Dubai", label: "Dubai (GST)" },
  { value: "Asia/Singapore", label: "Singapore (SGT)" },
  { value: "Asia/Tokyo", label: "Tokyo (JST)" },
  { value: "Australia/Sydney", label: "Sydney (AEDT)" },
];

const WEEKDAYS = [
  { value: 1, label: "Mon", fullLabel: "Monday" },
  { value: 2, label: "Tue", fullLabel: "Tuesday" },
  { value: 3, label: "Wed", fullLabel: "Wednesday" },
  { value: 4, label: "Thu", fullLabel: "Thursday" },
  { value: 5, label: "Fri", fullLabel: "Friday" },
  { value: 6, label: "Sat", fullLabel: "Saturday" },
  { value: 7, label: "Sun", fullLabel: "Sunday" },
];

export default function ActiveHoursForm({ settings, onUpdate }: ActiveHoursFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [enabled, setEnabled] = useState(settings.active_hours.enable_active_hours);
  const [startHour, setStartHour] = useState(settings.active_hours.active_start_hour);
  const [endHour, setEndHour] = useState(settings.active_hours.active_end_hour);
  const [timezone, setTimezone] = useState(settings.active_hours.active_timezone);
  const [activeDays, setActiveDays] = useState<number[]>(
    settings.active_hours.active_days.split(",").map((d) => parseInt(d.trim())).filter((d) => !isNaN(d))
  );
  const { toast } = useToast();

  const handleDayToggle = (day: number) => {
    setActiveDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort()
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (activeDays.length === 0) {
      toast({
        title: "Validation Error",
        description: "Please select at least one active day",
        variant: "destructive",
      });
      return;
    }

    if (startHour >= endHour) {
      toast({
        title: "Validation Error",
        description: "Start hour must be before end hour",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await updateSettings({
        active_hours: {
          enable_active_hours: enabled,
          active_start_hour: startHour,
          active_end_hour: endHour,
          active_timezone: timezone,
          active_days: activeDays.join(","),
        },
      });

      if (response.data) {
        toast({
          title: "Success",
          description: "Active hours updated successfully",
        });
        onUpdate();
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to update active hours",
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "An unexpected error occurred",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const hours = Array.from({ length: 24 }, (_, i) => i);

  return (
    <form onSubmit={handleSubmit}>
      <Card className="border-zinc-800/80 bg-zinc-950/40 shadow-none">
        <CardHeader>
          <CardTitle>Active Hours Configuration</CardTitle>
          <CardDescription>
            Control when the daemon executes tasks. Outside active hours, the daemon will idle until the next active window.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Enable/Disable Toggle */}
          <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950/70 p-4">
            <div className="space-y-0.5">
              <Label htmlFor="enable-active-hours" className="text-base font-medium">
                Enable Active Hours
              </Label>
              <p className="text-sm text-zinc-400">
                {enabled
                  ? "Daemon will only run during configured hours"
                  : "Daemon will run 24/7 regardless of time"}
              </p>
            </div>
            <Switch
              id="enable-active-hours"
              checked={enabled}
              onCheckedChange={setEnabled}
            />
          </div>

          {/* Hours Configuration */}
          <div className="space-y-4 opacity-100 transition-opacity" style={{ opacity: enabled ? 1 : 0.5 }}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="start-hour" className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Start Hour
                </Label>
                <Select
                  value={startHour.toString()}
                  onValueChange={(v) => v && setStartHour(parseInt(v))}
                  disabled={!enabled}
                >
                  <SelectTrigger id="start-hour" className="bg-zinc-900 border-zinc-800">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    {hours.map((h) => (
                      <SelectItem key={h} value={h.toString()}>
                        {h.toString().padStart(2, "0")}:00
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-zinc-500">Tasks start executing at this hour</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="end-hour" className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  End Hour
                </Label>
                <Select
                  value={endHour.toString()}
                  onValueChange={(v) => v && setEndHour(parseInt(v))}
                  disabled={!enabled}
                >
                  <SelectTrigger id="end-hour" className="bg-zinc-900 border-zinc-800">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    {hours.map((h) => (
                      <SelectItem key={h} value={h.toString()}>
                        {h.toString().padStart(2, "0")}:00
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-zinc-500">Tasks stop executing at this hour (exclusive)</p>
              </div>
            </div>

            {/* Timezone */}
            <div className="space-y-2">
              <Label htmlFor="timezone" className="flex items-center gap-2">
                <Globe className="h-4 w-4" />
                Timezone
              </Label>
              <Select
                value={timezone}
                onValueChange={(v) => v && setTimezone(v)}
                disabled={!enabled}
              >
                <SelectTrigger id="timezone" className="bg-zinc-900 border-zinc-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800">
                  {TIMEZONES.map((tz) => (
                    <SelectItem key={tz.value} value={tz.value}>
                      {tz.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-zinc-500">All times are interpreted in this timezone</p>
            </div>

            {/* Active Days */}
            <div className="space-y-3">
              <Label className="flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Active Days
              </Label>
              <div className="grid grid-cols-7 gap-2">
                {WEEKDAYS.map((day) => (
                  <div key={day.value} className="flex flex-col items-center space-y-2">
                    <Checkbox
                      id={`day-${day.value}`}
                      checked={activeDays.includes(day.value)}
                      onCheckedChange={() => handleDayToggle(day.value)}
                      disabled={!enabled}
                      className="h-5 w-5"
                    />
                    <Label
                      htmlFor={`day-${day.value}`}
                      className="text-xs font-medium cursor-pointer"
                      title={day.fullLabel}
                    >
                      {day.label}
                    </Label>
                  </div>
                ))}
              </div>
              <p className="text-xs text-zinc-500">
                {activeDays.length === 7
                  ? "Running every day"
                  : activeDays.length === 0
                    ? "No active days selected"
                    : `Running on ${activeDays.length} day${activeDays.length > 1 ? "s" : ""} per week`}
              </p>
            </div>
          </div>

          {/* Summary */}
          {enabled && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-4">
              <h4 className="text-sm font-medium mb-2">Configuration Summary</h4>
              <div className="space-y-1 text-sm text-zinc-400">
                <p>
                  • Active hours: {startHour.toString().padStart(2, "0")}:00 - {endHour.toString().padStart(2, "0")}:00
                </p>
                <p>• Timezone: {TIMEZONES.find((tz) => tz.value === timezone)?.label || timezone}</p>
                <p>
                  • Active days: {activeDays.length === 7
                    ? "Every day"
                    : activeDays.map((d) => WEEKDAYS.find((wd) => wd.value === d)?.label).join(", ")}
                </p>
                <p className="pt-2 text-xs text-zinc-500">
                  The daemon will idle outside these windows and resume when conditions are met.
                </p>
              </div>
            </div>
          )}

          <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
            {isSubmitting ? (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Icons.Check className="mr-2 h-4 w-4" />
                Save Active Hours
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    </form>
  );
}
