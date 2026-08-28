"use client";

import { apiClient } from "../apiClientV2";

export interface Mailbox {
  id: string;
  host: string;
  port: number;
  username: string;
  fromAddress: string;
  fromName: string;
  dailyLimit: number;
  headroomToday: number;
  sentToday: number;
  imapHost: string;
  imapPort: number;
  imapUsername: string;
  paused: boolean;
}

/** Convert the API's snake_case response into the UI's camelCase contract. */
function normalizeMailbox(value: Record<string, unknown>): Mailbox {
  return {
    id: String(value.id ?? ""),
    host: String(value.host ?? ""),
    port: Number(value.port ?? 0),
    username: String(value.username ?? ""),
    fromAddress: String(value.from_address ?? value.fromAddress ?? ""),
    fromName: String(value.from_name ?? value.fromName ?? ""),
    dailyLimit: Number(value.daily_limit ?? value.dailyLimit ?? 0),
    headroomToday: Number(value.headroom_today ?? value.headroomToday ?? 0),
    sentToday: Number(value.sent_today ?? value.sentToday ?? 0),
    imapHost: String(value.imap_host ?? value.imapHost ?? ""),
    imapPort: Number(value.imap_port ?? value.imapPort ?? 993),
    imapUsername: String(value.imap_username ?? value.imapUsername ?? ""),
    paused: Boolean(value.paused),
  };
}

export interface MailboxCreate {
  host: string;
  port: number;
  username: string;
  password: string;
  fromAddress?: string;
  fromName?: string;
  dailyLimit?: number;
  imapHost?: string;
  imapPort?: number;
  imapUsername?: string;
  imapPassword?: string;
}

export interface MailboxTestResult {
  ok: boolean;
  message: string;
}

export async function listMailboxes(): Promise<Mailbox[]> {
  const res = await apiClient.get<Mailbox[]>("/mailboxes");
  return (res.data ?? []).map((value) => normalizeMailbox(value as unknown as Record<string, unknown>));
}

export async function testMailbox(
  host: string,
  port: number,
  username: string,
  password: string,
): Promise<MailboxTestResult> {
  const res = await apiClient.post<MailboxTestResult>("/mailboxes/test", {
    host,
    port,
    username,
    password,
  });
  if (!res.data) throw new Error(res.error ?? "Test failed");
  return res.data;
}

export async function createMailbox(data: MailboxCreate): Promise<Mailbox> {
  const res = await apiClient.post<Mailbox>("/mailboxes", {
    host: data.host,
    port: data.port,
    username: data.username,
    password: data.password,
    from_address: data.fromAddress || "",
    from_name: data.fromName || "",
    daily_limit: data.dailyLimit ?? 40,
    imap_host: data.imapHost || "",
    imap_port: data.imapPort ?? 993,
    imap_username: data.imapUsername || "",
    imap_password: data.imapPassword || "",
  });
  if (!res.data) throw new Error(res.error ?? "Failed to create mailbox");
  return normalizeMailbox(res.data as unknown as Record<string, unknown>);
}

export interface MailboxUpdate {
  fromName?: string;
  dailyLimit?: number;
  imapHost?: string;
  imapPort?: number;
  imapUsername?: string;
  imapPassword?: string;
  password?: string;
}

export async function updateMailbox(mailboxId: string, data: MailboxUpdate): Promise<Mailbox> {
  const payload: Record<string, unknown> = {};
  if (data.fromName !== undefined) payload.from_name = data.fromName;
  if (data.dailyLimit !== undefined) payload.daily_limit = data.dailyLimit;
  if (data.imapHost !== undefined) payload.imap_host = data.imapHost;
  if (data.imapPort !== undefined) payload.imap_port = data.imapPort;
  if (data.imapUsername !== undefined) payload.imap_username = data.imapUsername;
  if (data.imapPassword !== undefined) payload.imap_password = data.imapPassword;
  if (data.password !== undefined) payload.password = data.password;
  const res = await apiClient.patch<Mailbox>(`/mailboxes/${mailboxId}`, payload);
  if (!res.data) throw new Error(res.error ?? "Failed to update mailbox");
  return normalizeMailbox(res.data as unknown as Record<string, unknown>);
}

export async function deleteMailbox(mailboxId: string): Promise<void> {
  await apiClient.delete(`/mailboxes/${mailboxId}`);
}

export async function unpauseMailbox(mailboxId: string): Promise<Mailbox> {
  const res = await apiClient.patch<Mailbox>(`/mailboxes/${mailboxId}/unpause`);
  if (!res.data) throw new Error(res.error ?? "Failed to unpause mailbox");
  return normalizeMailbox(res.data as unknown as Record<string, unknown>);
}
