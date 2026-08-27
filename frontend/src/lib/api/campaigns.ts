"use client";

import { apiClient } from "../apiClientV2";

export interface ImportResult {
  imported: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export async function importLeadsCSV(
  campaignId: string,
  file: File,
  columnMap: Record<string, string>,
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("column_map", JSON.stringify(columnMap));
  return apiClient.upload<ImportResult>(`/campaigns/${campaignId}/leads/import`, formData);
}

export interface SequenceStep {
  id: string;
  type: "action" | "wait" | "condition" | "end";
  data: {
    channel: "linkedin" | "email" | "whatsapp" | null;
    action: "connect" | "follow_up" | "send_email" | "send_whatsapp" | null;
    label: string;
    wait_days: number;
    condition: "always" | "no_reply" | "no_open" | "replied";
    requires: string[];
  };
  position: { x: number; y: number };
}

export interface SequenceEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  data?: { condition: string };
}

export interface SequenceResponse {
  steps: SequenceStep[];
  edges: SequenceEdge[];
  active: boolean;
  coverage_per_step: Record<string, number>;
}

export async function getSequence(campaignId: string) {
  return apiClient.get<SequenceResponse>(`/campaigns/${campaignId}/sequence`);
}

export async function saveSequence(
  campaignId: string,
  steps: SequenceStep[],
  edges: SequenceEdge[],
) {
  return apiClient.patch<void>(`/campaigns/${campaignId}/sequence`, { steps, edges });
}

export async function setSequenceActive(campaignId: string, active: boolean) {
  return apiClient.patch<void>(`/campaigns/${campaignId}/sequence`, { active });
}

export interface ChannelCoverage {
  count: number;
  pct: number;
}

export interface CampaignChannelCoverage {
  linkedin: ChannelCoverage;
  email: ChannelCoverage;
  whatsapp: ChannelCoverage;
}

export async function getCampaignCoverage(campaignId: string) {
  return apiClient.get<{ channel_coverage: CampaignChannelCoverage }>(
    `/campaigns/${campaignId}/coverage`,
  );
}
