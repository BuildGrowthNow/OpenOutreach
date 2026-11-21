"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getLinkedInProfiles } from "@/lib/api/dashboard";
import { listWhatsAppProfiles } from "@/lib/api/whatsapp";
import { listMailboxes } from "@/lib/api/mailboxes";
import { useBilling } from "@/lib/contexts/billing-context";
import { CheckCircle2, Circle, Mail, MessageCircle, Users } from "lucide-react";

type ChannelState = {
  linkedin: number;
  whatsapp: number;
  email: number;
};

export function ChannelBundleCard() {
  const { billingStatus } = useBilling();
  const [counts, setCounts] = useState<ChannelState>({ linkedin: 0, whatsapp: 0, email: 0 });

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      getLinkedInProfiles().catch(() => ({ data: null })),
      listWhatsAppProfiles().catch(() => []),
      listMailboxes().catch(() => []),
    ]).then(([linkedin, whatsapp, mailboxes]) => {
      if (cancelled) return;
      setCounts({
        linkedin: linkedin.data?.profiles?.length ?? 0,
        whatsapp: whatsapp.length,
        email: mailboxes.length,
      });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const cloudSeatLimit = billingStatus?.cloud_seat_limit ?? 0;
  const cloudSeatsUsed = billingStatus?.cloud_seats_used ?? 0;
  const emailLimit = billingStatus?.email_slot_limit ?? 0;
  const emailUsed = Math.max(
    billingStatus?.email_slots_used ?? 0,
    counts.email,
  );

  const steps = [
    {
      key: "linkedin",
      label: "LinkedIn",
      description: "Cloud or desktop browser account",
      done: counts.linkedin > 0,
      icon: Users,
    },
    {
      key: "whatsapp",
      label: "WhatsApp",
      description: "Cloud Duo or desktop number",
      done: counts.whatsapp > 0,
      icon: MessageCircle,
    },
    {
      key: "email",
      label: "Email",
      description: "BYO SMTP/IMAP · no proxy",
      done: counts.email > 0,
      icon: Mail,
    },
  ];

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base">Channel bundle</CardTitle>
            <CardDescription>
              LinkedIn → WhatsApp → email. One seat includes one browser account,
              one email slot, and one proxy identity.
            </CardDescription>
          </div>
          <Badge variant="secondary">
            {cloudSeatsUsed} of {cloudSeatLimit} cloud seat
            {cloudSeatLimit === 1 ? "" : "s"} used
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.key}
                className="flex items-start gap-2 rounded-lg border border-border/60 p-3"
              >
                {step.done ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                ) : (
                  <Circle className="mt-0.5 h-4 w-4 text-muted-foreground" />
                )}
                <div className="min-w-0">
                  <p className="flex items-center gap-1 text-sm font-medium">
                    <Icon className="h-3.5 w-3.5" />
                    {step.label}
                  </p>
                  <p className="text-xs text-muted-foreground">{step.description}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {step.done ? "Connected" : "Not connected"}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          Email: {emailUsed} of {emailLimit} slot{emailLimit === 1 ? "" : "s"} used.
          Desktop WhatsApp and email run on your local IP with no proxy. Cloud
          channels require a healthy managed proxy and never use the server IP.
        </p>
      </CardContent>
    </Card>
  );
}
