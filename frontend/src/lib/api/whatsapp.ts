"use client";

import { apiClient } from "../apiClientV2";

export interface WhatsAppProfile {
  id: string;
  userId: string;
  phoneNumber: string | null;
  displayName: string | null;
  status: "connected" | "disconnected" | "banned";
  lastSeen: string | null;
  createdAt: string;
  qrDataUrl: string | null;
  executionMode: "desktop" | "cloud";
  proxyMode: "none" | "managed" | "byo";
  proxyId: string | null;
  proxyRegionCountry: string | null;
  proxyRegionSubdivision: string | null;
  proxyRegionCity: string | null;
}

export interface CreateWhatsAppProfileOptions {
  executionMode?: "desktop" | "cloud";
  duoLinkedInProfileId?: string;
}

export async function listWhatsAppProfiles(): Promise<WhatsAppProfile[]> {
  const res = await apiClient.get<WhatsAppProfile[]>("/whatsapp/profiles");
  return res.data ?? [];
}

export async function createWhatsAppProfile(
  displayName?: string,
  options?: CreateWhatsAppProfileOptions,
): Promise<WhatsAppProfile> {
  const res = await apiClient.post<WhatsAppProfile>("/whatsapp/profiles", {
    display_name: displayName || null,
    execution_mode: options?.executionMode ?? "desktop",
    duo_linkedin_profile_id: options?.duoLinkedInProfileId ?? null,
  });
  if (!res.data) throw new Error(res.error ?? "Failed to create profile");
  return res.data;
}

export async function getWhatsAppProfile(profileId: string): Promise<WhatsAppProfile | null> {
  const res = await apiClient.get<WhatsAppProfile>(`/whatsapp/profiles/${profileId}`);
  return res.data ?? null;
}

export async function deleteWhatsAppProfile(profileId: string): Promise<void> {
  await apiClient.delete(`/whatsapp/profiles/${profileId}`);
}

export function getQrUrl(profileId: string): string {
  return `/api/whatsapp/qr/${profileId}`;
}

export async function resetQr(profileId: string): Promise<void> {
  await apiClient.post(`/whatsapp/qr/${profileId}/reset`, {});
}
