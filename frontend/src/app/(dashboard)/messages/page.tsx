"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Icons } from "@/lib/types/components";
import { Send, ExternalLink } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  zincDialogContentClassName,
  zincDialogHeaderClassName,
  zincTextareaClassName,
} from "@/lib/modal-styles";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getMessages,
  getCampaigns,
  sendMessageToLead,
} from "@/lib/api/dashboard";
import { Message, Campaign, Pagination } from "@/lib/types/components";
import { formatDistanceToNow } from "date-fns";
import { generateExportFilename } from "@/lib/export";

// ─── helpers ────────────────────────────────────────────────────────────────

function calcStats(msgs: Message[]) {
  const sent = msgs.filter((m) => m.isOutgoing).length;
  const received = msgs.filter((m) => !m.isOutgoing).length;
  const total = sent + received;
  const activeCampaigns = new Set(msgs.map((m) => m.campaignId).filter(Boolean)).size;
  return {
    totalSent: sent,
    totalReceived: received,
    responseRate: total > 0 ? Math.round((received / total) * 100) : 0,
    activeCampaigns,
  };
}

// ─── sub-components ──────────────────────────────────────────────────────────

interface MessageRowProps {
  message: Message;
  onClick: () => void;
}

function MessageRow({ message, onClick }: MessageRowProps) {
  return (
    <div
      className="flex items-start gap-3 p-4 rounded-lg border hover:bg-muted/30 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div
        className={`mt-1 flex-shrink-0 w-2 h-2 rounded-full ${
          message.isOutgoing ? "bg-blue-500" : "bg-emerald-500"
        }`}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1 gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Badge
              variant="outline"
              className={
                message.isOutgoing
                  ? "shrink-0 bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                  : "shrink-0 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
              }
            >
              {message.isOutgoing ? "Outgoing" : "Incoming"}
            </Badge>
            <span className="font-medium truncate">
              {message.recipientName || "Unknown"}
            </span>
            {message.campaignName && (
              <Badge
                variant="outline"
                className="shrink-0 hidden sm:inline-flex bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20 max-w-[140px] truncate"
              >
                {message.campaignName}
              </Badge>
            )}
          </div>
          <span className="text-xs text-muted-foreground flex-shrink-0">
            {message.creationDate
              ? formatDistanceToNow(new Date(message.creationDate), {
                  addSuffix: true,
                })
              : "—"}
          </span>
        </div>
        <p className="text-sm text-muted-foreground line-clamp-2">
          {message.content}
        </p>
      </div>
    </div>
  );
}

// ─── thread modal ────────────────────────────────────────────────────────────

interface ThreadModalProps {
  message: Message;
  thread: Message[];
  loading: boolean;
  sending: boolean;
  onSend: (content: string) => Promise<void>;
  onClose: () => void;
  onViewLead: (leadId: string) => void;
}

function ThreadModal({
  message,
  thread,
  loading,
  sending,
  onSend,
  onClose,
  onViewLead,
}: ThreadModalProps) {
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread]);

  const handleSend = async () => {
    const trimmed = draft.trim();
    if (!trimmed || sending) return;
    setDraft("");
    await onSend(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent
        className={`${zincDialogContentClassName} flex max-h-[85vh] max-w-2xl flex-col overflow-hidden p-0`}
      >
        {/* Header */}
        <DialogHeader
          className={`${zincDialogHeaderClassName} px-6 pt-6 sm:px-8 sm:pt-7 pb-4`}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <DialogTitle className="text-lg">
                {message.recipientName || "Lead"}
              </DialogTitle>
              <DialogDescription>
                <span className="flex items-center gap-2 mt-1 flex-wrap">
                  {message.campaignName && (
                    <Badge
                      variant="outline"
                      className="bg-violet-500/10 text-violet-400 border-violet-500/20"
                    >
                      {message.campaignName}
                    </Badge>
                  )}
                  {message.leadId && (
                    <button
                      onClick={() => onViewLead(message.leadId!)}
                      className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-100 transition-colors"
                    >
                      <ExternalLink className="h-3 w-3" />
                      View lead
                    </button>
                  )}
                  {message.recipientUrl && (
                    <a
                      href={message.recipientUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-100 transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Icons.ExternalLink className="h-3 w-3" />
                      LinkedIn
                    </a>
                  )}
                </span>
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Thread */}
        <div className="flex-1 overflow-y-auto px-6 py-4 sm:px-8 space-y-3">
          {loading ? (
            <div className="flex h-32 items-center justify-center">
              <Icons.RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
            </div>
          ) : thread.length === 0 ? (
            <div className="flex h-32 flex-col items-center justify-center gap-2">
              <Icons.MessageSquare className="h-8 w-8 text-zinc-500" />
              <p className="text-sm text-zinc-400">No messages yet</p>
            </div>
          ) : (
            thread.map((msg, idx) => {
              const isOut = msg.isOutgoing;
              const prevSameDir = idx > 0 && thread[idx - 1].isOutgoing === isOut;
              return (
                <div
                  key={msg.id}
                  className={`flex ${isOut ? "justify-end" : "justify-start"} ${prevSameDir ? "mt-1" : "mt-4"}`}
                >
                  <div
                    className={`max-w-[78%] rounded-2xl px-4 py-2.5 ${
                      isOut
                        ? "bg-blue-600 text-white rounded-br-none"
                        : "bg-zinc-800 text-zinc-100 border border-zinc-700 rounded-bl-none"
                    }`}
                  >
                    {!prevSameDir && (
                      <p className={`text-xs mb-1 ${isOut ? "text-blue-200" : "text-zinc-400"}`}>
                        {isOut ? "You" : (msg.senderName || message.recipientName || "Lead")}
                      </p>
                    )}
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <p className={`text-xs mt-1 text-right ${isOut ? "text-blue-200" : "text-zinc-500"}`}>
                      {msg.creationDate
                        ? formatDistanceToNow(new Date(msg.creationDate), { addSuffix: true })
                        : ""}
                    </p>
                  </div>
                </div>
              );
            })
          )}
          <div ref={bottomRef} />
        </div>

        {/* Compose */}
        <div className="border-t border-zinc-800 px-6 py-4 sm:px-8">
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Message ${message.recipientName || "lead"}…`}
                className={`${zincTextareaClassName} min-h-[68px] resize-none`}
                disabled={sending || !message.leadId}
                maxLength={1000}
              />
              <div className="flex justify-between mt-1">
                <span className="text-xs text-zinc-500">Enter to send · Shift+Enter for newline</span>
                <span
                  className={`text-xs ${
                    draft.length >= 900
                      ? "text-destructive"
                      : draft.length >= 800
                      ? "text-amber-500"
                      : "text-zinc-500"
                  }`}
                >
                  {draft.length}/1000
                </span>
              </div>
            </div>
            <Button
              onClick={() => void handleSend()}
              disabled={!draft.trim() || sending || !message.leadId}
              className="mb-5"
            >
              {sending ? (
                <Icons.RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          {!message.leadId && (
            <p className="text-xs text-zinc-500 mt-1">
              No lead linked — replies unavailable
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ─── main page ───────────────────────────────────────────────────────────────

const MessagesPage = () => {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [messages, setMessages] = useState<Message[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [campaignFilter, setCampaignFilter] = useState<string>(
    searchParams.get("campaign") || "all"
  );
  const [dateRange, setDateRange] = useState<string>("all");
  const [hasResponseFilter, setHasResponseFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const limit = 20;

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);

  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [threadMessages, setThreadMessages] = useState<Message[]>([]);
  const [threadLoading, setThreadLoading] = useState(false);
  const [sending, setSending] = useState(false);

  const fetchCampaigns = useCallback(async () => {
    try {
      const response = await getCampaigns();
      if (response.data) setCampaigns(response.data.data || []);
    } catch (err) {
      console.error("Error fetching campaigns:", err);
    }
  }, []);

  const fetchMessages = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getMessages(
        campaignFilter !== "all" ? campaignFilter : undefined,
        undefined,
        undefined,
        currentPage,
        limit,
      );
      if (response.data) {
        setMessages(response.data.data || []);
        setPagination(response.data.pagination || null);
      } else {
        setError(response.error || "Failed to fetch messages");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch messages");
    } finally {
      setLoading(false);
    }
  }, [campaignFilter, currentPage]);

  const fetchThread = useCallback(async (dealId: string) => {
    try {
      setThreadLoading(true);
      const response = await getMessages(undefined, dealId);
      if (response.data) setThreadMessages(response.data.data || []);
    } catch (err) {
      console.error("Error fetching thread:", err);
    } finally {
      setThreadLoading(false);
    }
  }, []);

  const handleSend = async (content: string) => {
    if (!selectedMessage?.leadId) return;
    try {
      setSending(true);
      const response = await sendMessageToLead(selectedMessage.leadId, content);
      if (response.data?.success) {
        await fetchThread(selectedMessage.dealId);
      }
    } catch (err) {
      console.error("Failed to send:", err);
    } finally {
      setSending(false);
    }
  };

  const openThread = (message: Message) => {
    setSelectedMessage(message);
    setThreadMessages([]);
    void fetchThread(message.dealId);
  };

  const closeThread = () => {
    setSelectedMessage(null);
    setThreadMessages([]);
  };

  useEffect(() => {
    void (async () => {
      await fetchCampaigns();
      await fetchMessages();
    })();
  }, [fetchCampaigns, fetchMessages]);

  const stats = useMemo(() => calcStats(messages), [messages]);

  // ── client-side filters (date + response status) ──────────────────────────
  const filteredMessages = useMemo(() => {
    return messages.filter((m) => {
      // Date range
      if (dateRange !== "all" && m.creationDate) {
        const created = new Date(m.creationDate);
        const now = new Date();
        const dayMs = 86_400_000;
        const cutoffs: Record<string, number> = {
          today: 1,
          week: 7,
          month: 30,
          "3months": 90,
        };
        const days = cutoffs[dateRange];
        if (days && now.getTime() - created.getTime() > days * dayMs) return false;
      }
      // Response status
      if (hasResponseFilter === "with") {
        return messages.some((m2) => m2.dealId === m.dealId && !m2.isOutgoing);
      }
      if (hasResponseFilter === "without") {
        return !messages.some((m2) => m2.dealId === m.dealId && !m2.isOutgoing);
      }
      // Search
      if (search) {
        const q = search.toLowerCase();
        return (
          m.content.toLowerCase().includes(q) ||
          (m.recipientName || "").toLowerCase().includes(q) ||
          (m.campaignName || "").toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [messages, dateRange, hasResponseFilter, search]);

  const handleExport = () => {
    const headers = ["ID", "Content", "Direction", "Lead", "Campaign", "Created At", "Deal ID"];
    const rows = filteredMessages.map((m) =>
      [
        m.id,
        `"${m.content.replace(/"/g, '""')}"`,
        m.isOutgoing ? "Outgoing" : "Incoming",
        `"${(m.recipientName || "").replace(/"/g, '""')}"`,
        `"${(m.campaignName || "").replace(/"/g, '""')}"`,
        m.creationDate,
        m.dealId,
      ].join(","),
    );
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = generateExportFilename("messages");
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-9 w-28" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-2" />
                <Skeleton className="h-3 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Messages</h1>
          <p className="text-muted-foreground mt-1">
            View and manage all messages across your campaigns
          </p>
        </div>
        <Button variant="outline" onClick={handleExport}>
          <Icons.Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Sent</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalSent}</div>
            <div className="text-xs text-muted-foreground">Messages sent</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Received</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalReceived}</div>
            <div className="text-xs text-muted-foreground">Responses received</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Response Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.responseRate}%</div>
            <div className="text-xs text-muted-foreground">Of messages sent</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Campaigns</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.activeCampaigns}</div>
            <div className="text-xs text-muted-foreground">With messages</div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="all">
        <TabsList className="grid grid-cols-4 w-full md:w-auto">
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="sent">Sent</TabsTrigger>
          <TabsTrigger value="received">Received</TabsTrigger>
          <TabsTrigger value="with-response">With Response</TabsTrigger>
        </TabsList>

        {/* ── All ── */}
        <TabsContent value="all" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Filters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <Label>Campaign</Label>
                  <Select value={campaignFilter} onValueChange={(v) => { if (v) { setCampaignFilter(v); setCurrentPage(1); } }}>
                    <SelectTrigger>
                      <span className="truncate">
                        {campaignFilter === "all"
                          ? "All Campaigns"
                          : (campaigns.find((c) => c.id === campaignFilter)?.name ?? "All Campaigns")}
                      </span>
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Campaigns</SelectItem>
                      {campaigns.map((c) => (
                        <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Search</Label>
                  <div className="relative">
                    <Icons.Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Lead, content, campaign…"
                      value={search}
                      onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
                      className="pl-9"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Date Range</Label>
                  <Select value={dateRange} onValueChange={(v) => { if (v) setDateRange(v); }}>
                    <SelectTrigger><SelectValue placeholder="All Time" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Time</SelectItem>
                      <SelectItem value="today">Today</SelectItem>
                      <SelectItem value="week">Last 7 Days</SelectItem>
                      <SelectItem value="month">Last 30 Days</SelectItem>
                      <SelectItem value="3months">Last 90 Days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Response Status</Label>
                  <Select value={hasResponseFilter} onValueChange={(v) => { if (v) setHasResponseFilter(v); }}>
                    <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="with">With Response</SelectItem>
                      <SelectItem value="without">No Response</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          <MessageListCard
            messages={filteredMessages}
            pagination={pagination}
            search={search}
            campaignFilter={campaignFilter}
            limit={limit}
            onOpen={openThread}
            onPageChange={setCurrentPage}
          />
        </TabsContent>

        {/* ── Sent ── */}
        <TabsContent value="sent" className="mt-4">
          <MessageListCard
            messages={filteredMessages.filter((m) => m.isOutgoing)}
            pagination={null}
            search={search}
            campaignFilter={campaignFilter}
            limit={limit}
            onOpen={openThread}
            onPageChange={setCurrentPage}
          />
        </TabsContent>

        {/* ── Received ── */}
        <TabsContent value="received" className="mt-4">
          <MessageListCard
            messages={filteredMessages.filter((m) => !m.isOutgoing)}
            pagination={null}
            search={search}
            campaignFilter={campaignFilter}
            limit={limit}
            onOpen={openThread}
            onPageChange={setCurrentPage}
          />
        </TabsContent>

        {/* ── With Response ── */}
        <TabsContent value="with-response" className="mt-4">
          <MessageListCard
            messages={dedupeConversations(filteredMessages)}
            pagination={null}
            search={search}
            campaignFilter={campaignFilter}
            limit={limit}
            onOpen={openThread}
            onPageChange={setCurrentPage}
            respondedBadge
          />
        </TabsContent>
      </Tabs>

      {/* Thread modal */}
      {selectedMessage && (
        <ThreadModal
          message={selectedMessage}
          thread={threadMessages}
          loading={threadLoading}
          sending={sending}
          onSend={handleSend}
          onClose={closeThread}
          onViewLead={(leadId) => {
            router.push(`/leads/${leadId}`);
          }}
        />
      )}
    </div>
  );
};

// ─── MessageListCard (shared across all tabs) ─────────────────────────────

interface MessageListCardProps {
  messages: Message[];
  pagination: Pagination | null;
  search: string;
  campaignFilter: string;
  limit: number;
  onOpen: (m: Message) => void;
  onPageChange: (page: number) => void;
  respondedBadge?: boolean;
}

function MessageListCard({
  messages,
  pagination,
  search,
  campaignFilter,
  limit,
  onOpen,
  onPageChange,
  respondedBadge = false,
}: MessageListCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <CardTitle>Messages</CardTitle>
          <p className="text-sm text-muted-foreground">
            {pagination ? `${pagination.total} total` : `${messages.length} messages`}
          </p>
        </div>
        {pagination && pagination.total_pages > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              Page {pagination.page} of {pagination.total_pages}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onPageChange(pagination.page - 1)}
              disabled={pagination.page <= 1}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onPageChange(pagination.page + 1)}
              disabled={pagination.page >= pagination.total_pages}
            >
              Next
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent>
        {messages.length === 0 ? (
          <div className="text-center py-12">
            <Icons.MessageSquare className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Messages Found</h3>
            <p className="text-sm text-muted-foreground">
              {search || campaignFilter !== "all"
                ? "Try adjusting your filters"
                : "Start a campaign to begin sending messages"}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {messages.map((m) => (
              <div key={m.id} className="relative">
                {respondedBadge && (
                  <Badge
                    variant="outline"
                    className="absolute right-4 top-4 z-10 bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  >
                    Responded
                  </Badge>
                )}
                <MessageRow message={m} onClick={() => onOpen(m)} />
              </div>
            ))}
          </div>
        )}
        {pagination && pagination.total > limit && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => onPageChange(pagination.page - 1)}
              disabled={pagination.page <= 1}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {pagination.page} of {pagination.total_pages || 1}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onPageChange(pagination.page + 1)}
              disabled={pagination.page >= (pagination.total_pages || 1)}
            >
              Next
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Returns one representative message per deal that has at least one reply
function dedupeConversations(messages: Message[]): Message[] {
  const respondedDeals = new Set(
    messages.filter((m) => !m.isOutgoing).map((m) => m.dealId),
  );
  const seen = new Set<string>();
  const result: Message[] = [];
  for (const m of messages) {
    if (respondedDeals.has(m.dealId) && !seen.has(m.dealId)) {
      seen.add(m.dealId);
      result.push(m);
    }
  }
  return result;
}

export default MessagesPage;
