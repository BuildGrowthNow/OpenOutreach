"use client";

import { useEffect, useState } from "react";
import { Network, Mail, Smartphone } from "lucide-react";
import { getCampaignCoverage, CampaignChannelCoverage } from "@/lib/api/campaigns";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface CoverageBarsProps {
  campaignId: string;
  totalLeads: number;
}

export function CoverageBars({ campaignId, totalLeads }: CoverageBarsProps) {
  const [coverage, setCoverage] = useState<CampaignChannelCoverage | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (totalLeads === 0) return;
    setLoading(true);
    getCampaignCoverage(campaignId)
      .then((res) => {
        if (res.data?.channel_coverage) setCoverage(res.data.channel_coverage);
      })
      .finally(() => setLoading(false));
  }, [campaignId, totalLeads]);

  if (totalLeads === 0 || loading || !coverage) return null;

  const rows = [
    { label: "LinkedIn", icon: Network, data: coverage.linkedin, color: "text-blue-500", barClass: "[&>div]:bg-blue-500" },
    { label: "Email", icon: Mail, data: coverage.email, color: "text-amber-500", barClass: "[&>div]:bg-amber-500" },
    { label: "WhatsApp", icon: Smartphone, data: coverage.whatsapp, color: "text-emerald-500", barClass: "[&>div]:bg-emerald-500" },
  ];

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4 mb-4">
      <p className="text-xs font-medium text-zinc-400 mb-3">Channel Coverage</p>
      <div className="space-y-2.5">
        {rows.map(({ label, icon: Icon, data, color, barClass }) => (
          <div key={label} className="flex items-center gap-3">
            <Icon className={cn("h-3.5 w-3.5 shrink-0", color)} />
            <span className="text-xs text-zinc-400 w-14 shrink-0">{label}</span>
            <Progress value={data.pct} className={cn("flex-1 h-1.5 bg-zinc-800", barClass)} />
            <span className="text-xs text-zinc-400 w-12 text-right shrink-0">
              {data.count} / {totalLeads}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
