"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icons } from "@/lib/types/components";
import { CampaignActivity } from "@/components/campaigns/campaign-activity";

export default function CampaignLogsPage() {
  const params = useParams();
  const campaignId = params.id as string;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Link href={`/campaigns/${campaignId}`}>
          <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-100">
            <Icons.ChevronLeft className="mr-1 h-4 w-4" />
            Back to campaign
          </Button>
        </Link>
        <h1 className="text-xl font-semibold text-zinc-100">Campaign Logs</h1>
      </div>

      <CampaignActivity campaignId={campaignId} compact={false} />
    </div>
  );
}
