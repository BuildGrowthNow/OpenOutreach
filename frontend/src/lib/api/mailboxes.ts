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
  paused: boolean;
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
}

export interface MailboxTestResult {
  ok: boolean;
  message: string;
}

export async function listMailboxes(): Promise<Mailbox[]> {
  const res = await apiClient.get<Mailbox[]>("/mailboxes");
  return res.data ?? [];
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
  });
  if (!res.data) throw new Error(res.error ?? "Failed to create mailbox");
  return res.data;
}

export interface MailboxUpdate {
  fromName?: string;
  dailyLimit?: number;
  imapHost?: string;
  imapPort?: number;
  password?: string;
}

export async function updateMailbox(mailboxId: string, data: MailboxUpdate): Promise<Mailbox> {
  const payload: Record<string, unknown> = {};
  if (data.fromName !== undefined) payload.from_name = data.fromName;
  if (data.dailyLimit !== undefined) payload.daily_limit = data.dailyLimit;
  if (data.imapHost !== undefined) payload.imap_host = data.imapHost;
  if (data.imapPort !== undefined) payload.imap_port = data.imapPort;
  if (data.password !== undefined) payload.password = data.password;
  const res = await apiClient.patch<Mailbox>(`/mailboxes/${mailboxId}`, payload);
  if (!res.data) throw new Error(res.error ?? "Failed to update mailbox");
  return res.data;
}

export async function deleteMailbox(mailboxId: string): Promise<void> {
  await apiClient.delete(`/mailboxes/${mailboxId}`);
}

export async function unpauseMailbox(mailboxId: string): Promise<Mailbox> {
  const res = await apiClient.patch<Mailbox>(`/mailboxes/${mailboxId}/unpause`);
  if (!res.data) throw new Error(res.error ?? "Failed to unpause mailbox");
  return res.data;
}
