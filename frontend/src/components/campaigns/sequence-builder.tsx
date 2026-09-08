"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  NodeProps,
  EdgeProps,
  getBezierPath,
  BaseEdge,
  EdgeLabelRenderer,
  MarkerType,
  Connection,
  Node as RFNode,
  Edge as RFEdge,
  useReactFlow,
  ReactFlowProvider,
  Panel,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { Icons } from "@/lib/types/components";
import { cn } from "@/lib/utils";
import {
  getSequence,
  saveSequence,
  setSequenceActive,
  getCampaignCoverage,
  CampaignChannelCoverage,
  SequenceStep,
  SequenceEdge,
  getSequenceMetrics,
  SequenceMetrics,
} from "@/lib/api/campaigns";
import { getCampaignTemplates, saveCampaignAsTemplate, getLinks } from "@/lib/api/dashboard";
import type { TrackedLink } from "@/lib/api/dashboard";
import { useToast } from "@/components/ui/use-toast";
import { Network, Mail, Smartphone, Clock, GitBranch, Flag, Plus, X, Undo2 } from "lucide-react";

// ─── constants ────────────────────────────────────────────────────────────────

const STEP_COLORS: Record<string, { border: string; bg: string; text: string; ring: string }> = {
  connect:       { border: "border-blue-500/40",    bg: "bg-blue-500/10",    text: "text-blue-300",    ring: "ring-blue-500" },
  follow_up:     { border: "border-blue-500/40",    bg: "bg-blue-500/10",    text: "text-blue-300",    ring: "ring-blue-500" },
  send_email:    { border: "border-amber-500/40",   bg: "bg-amber-500/10",   text: "text-amber-300",   ring: "ring-amber-500" },
  send_whatsapp: { border: "border-emerald-500/40", bg: "bg-emerald-500/10", text: "text-emerald-300", ring: "ring-emerald-500" },
  notify_internal: { border: "border-cyan-500/40", bg: "bg-cyan-500/10", text: "text-cyan-300", ring: "ring-cyan-500" },
  wait:          { border: "border-zinc-600/40",    bg: "bg-zinc-800/50",    text: "text-zinc-400",    ring: "ring-zinc-500" },
  condition:     { border: "border-purple-500/40",  bg: "bg-purple-500/10",  text: "text-purple-300",  ring: "ring-purple-500" },
  end:           { border: "border-rose-500/40",    bg: "bg-rose-500/10",    text: "text-rose-300",    ring: "ring-rose-500" },
};

const STEP_KEY_LABELS: Record<string, string> = {
  connect:       "LinkedIn Connect",
  follow_up:     "LinkedIn Follow-up",
  send_email:    "Send Email",
  send_whatsapp: "Send WhatsApp",
  notify_internal: "Internal notification",
  wait:          "Wait",
  condition:     "Branch / Gate",
  end:           "End",
};

const CONDITION_OPTIONS = [
  { value: "lead_has_email", label: "Lead has email" },
  { value: "lead_has_phone", label: "Lead has phone" },
  { value: "reply_received", label: "Reply received" },
  { value: "email_opened", label: "Email opened" },
  { value: "email_not_opened", label: "Email not opened" },
  { value: "link_clicked", label: "Link clicked" },
  { value: "link_not_clicked", label: "Link not clicked" },
];

const EDGE_BRANCH_LABELS: Record<string, string> = {
  yes: "Yes",
  no:  "No",
};

// ─── helpers ──────────────────────────────────────────────────────────────────

function stepColorKey(step: SequenceStep): string {
  return step.data.action || step.type;
}

function makeId(): string {
  return crypto.randomUUID();
}

// ─── step icon ────────────────────────────────────────────────────────────────

function StepIcon({ step, className }: { step: SequenceStep; className?: string }) {
  const key = stepColorKey(step);
  const cls = cn("h-4 w-4 shrink-0", className);
  if (key === "connect" || key === "follow_up") return <Network className={cls} />;
  if (key === "send_email") return <Mail className={cls} />;
  if (key === "send_whatsapp") return <Smartphone className={cls} />;
  if (key === "wait") return <Clock className={cls} />;
  if (key === "condition") return <GitBranch className={cls} />;
  return <Flag className={cls} />;
}

// ─── SeqNode ──────────────────────────────────────────────────────────────────

interface SeqNodeData {
  step: SequenceStep;
  coverage: number | null;
  totalLeads: number;
  hasBypass: boolean;
  validationErrors?: string[];
  onDelete: (id: string) => void;
  onEdit: (id: string) => void;
  [key: string]: unknown;
}

function SeqNode({ id, data, selected }: NodeProps) {
  const d = data as SeqNodeData;
  const step = d.step;
  const key = stepColorKey(step);
  const colors = STEP_COLORS[key] ?? STEP_COLORS.wait;
  const isEnd = step.type === "end";
  const isCondition = step.type === "condition";
  const isWait = step.type === "wait";

  return (
    <div
      className={cn(
        "rounded-xl border-2 p-3 min-w-[200px] max-w-[260px] shadow-lg cursor-pointer select-none bg-zinc-950",
        colors.border,
        colors.bg,
        selected && `ring-2 ring-offset-1 ring-offset-zinc-950 ${colors.ring}`,
      )}
      role="button"
      tabIndex={0}
      aria-label={`Edit ${step.data.label || STEP_KEY_LABELS[key] || key}`}
      onClick={() => d.onEdit(id)}
      onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); d.onEdit(id); } }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !border-2 !border-zinc-600 !bg-zinc-900 hover:!border-zinc-400"
      />

      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className={cn("mt-0.5", colors.text)}>
            <StepIcon step={step} />
          </span>
          <div className="min-w-0">
            <div className={cn("text-sm font-semibold truncate", colors.text)}>
              {step.data.label || STEP_KEY_LABELS[key] || key}
            </div>
            {isWait && (
              <div className="text-xs text-zinc-500 mt-0.5">
                {(() => {
                  const d = step.data.wait_days || 0;
                  const h = step.data.wait_hours || 0;
                  if (d > 0 && h > 0) return `${d}d ${h}h`;
                  if (d > 0) return `${d} day${d !== 1 ? "s" : ""}`;
                  if (h > 0) return `${h} hour${h !== 1 ? "s" : ""}`;
                  return "1 day";
                })()}
              </div>
            )}
            {isCondition && step.data.condition && step.data.condition !== "always" && (
              <div className="text-xs text-zinc-500 mt-0.5">
                {CONDITION_OPTIONS.find((o) => o.value === step.data.condition)?.label}
              </div>
            )}
            {step.data.requires && step.data.requires.length > 0 && (
              <div className="text-xs text-zinc-600 mt-0.5">needs: {step.data.requires.join(", ")}</div>
            )}
            {d.validationErrors && d.validationErrors.length > 0 && (
              <div role="alert" className="mt-2 rounded border border-red-500/30 bg-red-500/10 px-2 py-1 text-[10px] leading-tight text-red-300">
                {d.validationErrors[0]}
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <button
            className="text-zinc-600 hover:text-zinc-300 transition-colors p-0.5 rounded"
            onClick={(e) => { e.stopPropagation(); d.onEdit(id); }}
            title="Edit step"
          >
            <Icons.Settings className="h-3.5 w-3.5" />
          </button>
          <button
            className="text-zinc-600 hover:text-red-400 transition-colors p-0.5 rounded"
            onClick={(e) => { e.stopPropagation(); d.onDelete(id); }}
            title="Delete step"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {step.data.requires && step.data.requires.length > 0 && (
        <div className="mt-2">
          {d.coverage === null ? (
            <span className="text-[10px] text-zinc-600">Coverage shown after save</span>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="cursor-default">
                  <Progress
                    value={d.coverage}
                    className={cn("h-1.5 bg-zinc-800", coverageBarClass(d.coverage))}
                  />
                  <div className="flex items-center gap-1 mt-0.5">
                    {d.coverage === 0 ? (
                      <span className="text-[10px] text-red-400 font-medium">⚠ No leads have this data</span>
                    ) : d.coverage < 30 ? (
                      <span className="text-[10px] text-red-400">
                        ⚠ {d.totalLeads > 0 ? `${Math.round(d.coverage * d.totalLeads / 100)} of ${d.totalLeads}` : `${d.coverage}%`} leads reachable
                      </span>
                    ) : (
                      <span className="text-[10px] text-zinc-500">
                        {d.totalLeads > 0 ? `${Math.round(d.coverage * d.totalLeads / 100)} of ${d.totalLeads}` : `${d.coverage}%`} leads reachable
                      </span>
                    )}
                  </div>
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[220px] text-xs">
                {d.coverage < 100
                  ? d.hasBypass
                    ? "✓ Leads without the required data are routed around this step via a Branch node."
                    : "Leads without the required data automatically skip this step and proceed to the next one."
                  : "All leads in this campaign have the required data for this step."}
              </TooltipContent>
            </Tooltip>
          )}
        </div>
      )}

      {isCondition ? (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="yes"
            style={{ left: "30%" }}
            className="!w-3 !h-3 !border-2 !border-emerald-600 !bg-zinc-900 hover:!border-emerald-400"
            title="Yes — condition met (left handle)"
          />
          <Handle
            type="source"
            position={Position.Bottom}
            id="no"
            style={{ left: "70%" }}
            className="!w-3 !h-3 !border-2 !border-rose-600 !bg-zinc-900 hover:!border-rose-400"
            title="No — condition not met (right handle)"
          />
          <div className="flex justify-between mt-3 px-1">
            <span className="text-[10px] text-emerald-500/70">Yes</span>
            <span className="text-[10px] text-rose-500/70">No</span>
          </div>
        </>
      ) : !isEnd ? (
        <Handle
          type="source"
          position={Position.Bottom}
          className="!w-3 !h-3 !border-2 !border-zinc-600 !bg-zinc-900 hover:!border-zinc-400"
        />
      ) : null}
    </div>
  );
}

// ─── SeqEdge ──────────────────────────────────────────────────────────────────

function SeqEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, selected }: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  const branch = (data as { condition?: string } | undefined)?.condition;
  const branchLabel = branch ? (EDGE_BRANCH_LABELS[branch] ?? branch) : null;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: selected ? "#60a5fa" : branch === "yes" ? "#10b981" : branch === "no" ? "#f43f5e" : "#52525b",
          strokeWidth: selected ? 2.5 : 1.5,
        }}
      />
      {branchLabel && (
        <EdgeLabelRenderer>
          <div
            style={{ transform: `translate(-50%,-50%) translate(${labelX}px,${labelY}px)`, pointerEvents: "all" }}
            className="absolute nodrag nopan"
          >
            <span
              className={cn(
                "text-[10px] font-medium px-1.5 py-0.5 rounded border bg-zinc-950 select-none",
                branch === "yes" ? "border-emerald-600/40 text-emerald-400" : "border-rose-600/40 text-rose-400",
              )}
            >
              {branchLabel}
            </span>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { seq: SeqNode };
const edgeTypes = { seq: SeqEdge };

// ─── layout helper ────────────────────────────────────────────────────────────

function autoLayout(steps: SequenceStep[]): SequenceStep[] {
  return steps.map((s, i) => ({
    ...s,
    position:
      s.position?.x != null && s.position?.y != null && (s.position.x !== 0 || s.position.y !== 0)
        ? s.position
        : { x: 300, y: i * 150 },
  }));
}

// ─── RF converters ────────────────────────────────────────────────────────────

function stepsToNodes(
  steps: SequenceStep[],
  coverage: Record<string, number>,
  edges: SequenceEdge[],
  totalLeads: number,
  onDelete: (id: string) => void,
  onEdit: (id: string) => void,
  validationByNode: Record<string, string[]> = {},
): RFNode[] {
  // Build minimal RFNode array for hasBypassPath (positions don't matter here)
  const minNodes: RFNode[] = steps.map((s) => ({
    id: s.id, type: "seq", position: s.position, data: { step: s } as SeqNodeData,
  }));
  const minEdges: RFEdge[] = edges.map((e) => ({ id: e.id, source: e.source, target: e.target }));
  return steps.map((step) => ({
    id: step.id,
    type: "seq",
    position: step.position,
    data: {
      step,
      coverage: coverage[step.id] ?? null,
      totalLeads,
      hasBypass: hasBypassPath(step.id, minNodes, minEdges),
      validationErrors: validationByNode[step.id] ?? [],
      onDelete,
      onEdit,
    },
  }));
}

function edgesToRF(edges: SequenceEdge[]): RFEdge[] {
  return edges.map((e) => {
    const cond = (e.data as { condition?: string } | undefined)?.condition;
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: cond === "yes" ? "yes" : cond === "no" ? "no" : undefined,
      type: "seq",
      data: e.data ?? {},
      markerEnd: { type: MarkerType.ArrowClosed, color: "#52525b", width: 12, height: 12 },
    };
  });
}

function rfNodesToSteps(nodes: RFNode[], prevSteps: SequenceStep[]): SequenceStep[] {
  const prevMap = new Map(prevSteps.map((s) => [s.id, s]));
  return nodes.map((n) => {
    const prev = prevMap.get(n.id);
    return prev ? { ...prev, position: n.position } : { ...(n.data as SeqNodeData).step, position: n.position };
  });
}

function rfEdgesToSeq(edges: RFEdge[]): SequenceEdge[] {
  return edges.map((e) => {
    const raw = e.data as { condition?: string } | undefined;
    const seqEdge: SequenceEdge = {
      id: e.id,
      source: e.source,
      target: e.target,
    };
    if (raw?.condition) seqEdge.data = { condition: raw.condition };
    return seqEdge;
  });
}

// ─── validation ───────────────────────────────────────────────────────────────

function validateSequence(steps: SequenceStep[], edges: SequenceEdge[]): string[] {
  if (steps.length === 0) return [];
  const warnings: string[] = [];
  const edgeTargets = new Set(edges.map((e) => e.target));
  const edgeSources = new Set(edges.map((e) => e.source));
  const roots = steps.filter((s) => !edgeTargets.has(s.id));
  if (roots.length > 1) warnings.push(`${roots.length} disconnected entry points — connect all steps.`);
  if (!steps.some((s) => s.type === "action")) warnings.push("Add at least one action step (Connect, Follow-up, Send Email, or Send WhatsApp).");
  if (!steps.some((s) => s.type === "end")) warnings.push("Add an End step.");
  const zeroWaits = steps.filter((s) => s.type === "wait" && !(s.data.wait_days || 0) && !(s.data.wait_hours || 0));
  if (zeroWaits.length) warnings.push(`${zeroWaits.length} Wait step${zeroWaits.length === 1 ? " has" : "s have"} no duration.`);
  const noOutgoing = steps.filter((s) => s.type !== "end" && !edgeSources.has(s.id));
  if (noOutgoing.length > 0) {
    warnings.push(
      `${noOutgoing.map((s) => `"${s.data.label}"`).join(", ")} ${noOutgoing.length === 1 ? "has" : "have"} no outgoing connection.`,
    );
  }
  return warnings;
}

function validateNodeErrors(steps: SequenceStep[], edges: SequenceEdge[]): Record<string, string[]> {
  const errors: Record<string, string[]> = {};
  const add = (id: string, message: string) => { errors[id] = [...(errors[id] ?? []), message]; };
  const outgoing = new Map<string, SequenceEdge[]>();
  const incoming = new Set(edges.map((edge) => edge.target));
  for (const edge of edges) outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge]);

  for (const step of steps) {
    const data = step.data;
    if (step.type !== "end" && !(outgoing.get(step.id)?.length)) add(step.id, "Connect this node to its next step.");
    if (step.type === "wait" && !(data.wait_days || data.wait_hours)) add(step.id, "Set a positive wait duration.");
    if (step.type === "condition") {
      if (!data.condition || data.condition === "always") add(step.id, "Choose a supported condition.");
      const branches = new Set((outgoing.get(step.id) ?? []).map((edge) => edge.data?.condition));
      if (!branches.has("yes") || !branches.has("no")) add(step.id, "Connect both Yes and No branches.");
      if ((data.condition === "link_clicked" || data.condition === "link_not_clicked") && !data.link_key) add(step.id, "Add a logical link key.");
    }
    if (step.type === "action") {
      const message = data.message;
      if (["follow_up", "send_email", "send_whatsapp"].includes(data.action ?? "") && (!message || ((message.content_mode === "static" && !message.body?.trim()) || (message.content_mode === "ai_prompt" && !message.prompt?.trim() && !message.body?.trim())))) {
        add(step.id, "Add a static body or AI prompt.");
      }
    }
  }
  const roots = steps.filter((step) => !incoming.has(step.id));
  roots.slice(1).forEach((step) => add(step.id, "Connect this extra entry point to the workflow."));
  return errors;
}

// ─── coverage helpers ─────────────────────────────────────────────────────────

function instantCoverageForStep(step: SequenceStep, channelCoverage: CampaignChannelCoverage | null): number | null {
  if (!channelCoverage) return null;
  if (!step.data.requires || step.data.requires.length === 0) return null;
  // Map requires fields → channel coverage percentage.
  // Use the lowest coverage among all required fields (most restrictive).
  let min = 100;
  for (const req of step.data.requires) {
    if (req === "api_email") min = Math.min(min, channelCoverage.email.pct);
    else if (req === "phone") min = Math.min(min, channelCoverage.whatsapp.pct);
    else return null; // unknown field — can't compute
  }
  return min;
}

function coverageBarClass(pct: number | null): string {
  if (pct === null) return "[&>div]:bg-zinc-600";
  if (pct === 0)    return "[&>div]:bg-red-500";
  if (pct < 30)     return "[&>div]:bg-red-500";
  if (pct < 70)     return "[&>div]:bg-amber-500";
  return "[&>div]:bg-emerald-500";
}

function hasBypassPath(stepId: string, nodes: RFNode[], edges: RFEdge[]): boolean {
  const visited = new Set<string>();
  const queue = [stepId];
  while (queue.length) {
    const id = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    for (const e of edges) {
      if (e.target !== id) continue;
      const parent = nodes.find((n) => n.id === e.source);
      if (parent && (parent.data as SeqNodeData).step.type === "condition") return true;
      queue.push(e.source);
    }
  }
  return false;
}

// Templates are supplied by the backend so the canvas and campaign creation
// flow cannot drift into separate workflow definitions.
type Template = { name: string; description: string; sequence_steps: SequenceStep[]; sequence_edges: SequenceEdge[]; channels?: string[]; required_data?: string[] };

const ADD_STEP_OPTIONS = [
  { type: "action"    as const, action: "connect"        as const, channel: "linkedin"  as const, label: "LinkedIn Connect",   requires: [] as string[] },
  { type: "action"    as const, action: "follow_up"      as const, channel: "linkedin"  as const, label: "LinkedIn Follow-up", requires: [] as string[] },
  { type: "action"    as const, action: "send_email"     as const, channel: "email"     as const, label: "Send Email",         requires: ["api_email"] as string[] },
  { type: "action"    as const, action: "send_whatsapp"  as const, channel: "whatsapp"  as const, label: "Send WhatsApp",      requires: ["phone"] as string[] },
  { type: "action"    as const, action: "notify_internal" as const, channel: "internal" as const, label: "Internal notification", requires: [] as string[] },
  { type: "wait"      as const, action: null,                       channel: null,                 label: "Wait",               requires: [] as string[] },
  { type: "condition" as const, action: null,                       channel: null,                 label: "Branch / Gate",      requires: [] as string[] },
  { type: "end"       as const, action: null,                       channel: null,                 label: "End",                requires: [] as string[] },
];

// ─── ConfigPanel ──────────────────────────────────────────────────────────────

function ConfigPanel({ step, onChange, onClose, links }: { step: SequenceStep; onChange: (u: SequenceStep) => void; onClose: () => void; links: TrackedLink[] }) {
  const [label, setLabel] = useState(step.data.label);
  const [condition, setCondition] = useState(step.data.condition ?? "lead_has_email");
  const [linkKey, setLinkKey] = useState(step.data.link_key ?? "");
  const [observationWindowHours, setObservationWindowHours] = useState(step.data.observation_window_hours ?? 24);
  // waitMode: "days" shows a days input, "hours" shows an hours input, "both" shows both.
  // Detect initial mode from existing data.
  const initMode = (() => {
    const d = step.data.wait_days || 0;
    const h = step.data.wait_hours || 0;
    if (d > 0 && h > 0) return "both" as const;
    if (h > 0) return "hours" as const;
    return "days" as const;
  })();
  const [waitMode, setWaitMode] = useState<"days" | "hours" | "both">(initMode);
  const [waitDays, setWaitDays] = useState(step.data.wait_days || 0);
  const [waitHours, setWaitHours] = useState(step.data.wait_hours || 0);
  const [requires, setRequires] = useState<string[]>(step.data.requires ?? []);
  const [message, setMessage] = useState(step.data.message ?? { content_mode: "ai_prompt" as const, prompt: "", subject: "", body: "", link_refs: [] as string[], stop_on_reply: true, fallback_mode: "continue" as const, fallback_body: "" });

  useEffect(() => {
    setLabel(step.data.label);
    setCondition(step.data.condition ?? "lead_has_email");
    setLinkKey(step.data.link_key ?? "");
    setObservationWindowHours(step.data.observation_window_hours ?? 24);
    const d = step.data.wait_days || 0;
    const h = step.data.wait_hours || 0;
    setWaitDays(d);
    setWaitHours(h);
    setWaitMode(d > 0 && h > 0 ? "both" : h > 0 ? "hours" : "days");
    setRequires(step.data.requires ?? []);
    setMessage(step.data.message ?? { content_mode: "ai_prompt", prompt: "", subject: "", body: "", link_refs: [], stop_on_reply: true, fallback_mode: "continue", fallback_body: "" });
  }, [step.id, step.data.label, step.data.condition, step.data.link_key, step.data.observation_window_hours, step.data.wait_days, step.data.wait_hours, step.data.requires, step.data.message]);

  const save = () => {
    const waitUpdate = step.type === "wait" ? {
      wait_days: waitMode !== "hours" ? Math.max(0, waitDays) : 0,
      wait_hours: waitMode !== "days" ? Math.max(0, waitHours) : 0,
    } : {};
    const eventCondition = ["reply_received", "email_opened", "email_not_opened", "link_clicked", "link_not_clicked"].includes(condition);
    const {
      condition: _oldCondition,
      link_key: _oldLinkKey,
      observation_window_hours: _oldObservationWindow,
      message: _oldMessage,
      ...sharedData
    } = step.data;
    const nodeData = {
      ...sharedData,
      label,
      ...(step.type === "action" ? { requires, message } : {}),
      ...(step.type === "condition" ? {
        condition,
        link_key: linkKey || undefined,
        observation_window_hours: eventCondition && observationWindowHours > 0 ? observationWindowHours : undefined,
      } : {}),
      ...waitUpdate,
    };
    onChange({ ...step, data: nodeData });
    onClose();
  };

  return (
    <Card className="h-full min-h-[580px] border-zinc-800 bg-zinc-950 text-zinc-100">
        <CardHeader className="border-b border-zinc-800">
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>Configure step</CardTitle>
              <CardDescription className="text-zinc-400">
            {step.type === "action" && step.data.action === "connect"       && "Sends a LinkedIn connection request."}
            {step.type === "action" && step.data.action === "follow_up"     && "Sends a LinkedIn follow-up message via the campaign AI agent."}
            {step.type === "action" && step.data.action === "send_email"    && "Sends an email to the lead's work address."}
            {step.type === "action" && step.data.action === "send_whatsapp" && "Sends a WhatsApp message to the lead's phone number."}
            {step.type === "wait"      && "Pauses the sequence before proceeding to the next step."}
            {step.type === "condition" && "Routes leads down two paths. Drag from the green handle (Yes/left) and red handle (No/right) to connect both branches."}
            {step.type === "end"       && "Marks the end of this path."}
              </CardDescription>
            </div>
            <Button variant="ghost" size="icon" aria-label="Close step inspector" onClick={onClose} className="text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="max-h-[480px] space-y-4 overflow-y-auto py-4">
          <div className="space-y-1.5">
            <Label className="text-zinc-300">Label</Label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-zinc-100"
              onKeyDown={(e) => e.key === "Enter" && save()}
            />
          </div>
          {step.type === "wait" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Label className="text-zinc-300">Wait duration</Label>
                <div className="flex items-center gap-1 ml-auto">
                  {(["days", "hours", "both"] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setWaitMode(m)}
                      className={cn(
                        "text-xs px-2 py-0.5 rounded border transition-colors",
                        waitMode === m
                          ? "border-blue-500/50 bg-blue-500/20 text-blue-300"
                          : "border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600",
                      )}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
              {waitMode !== "hours" && (
                <div className="space-y-1.5">
                  <Label className="text-xs text-zinc-400">Days</Label>
                  <Input
                    type="number"
                    min={0}
                    max={365}
                    value={waitDays}
                    onChange={(e) => setWaitDays(Math.max(0, Math.min(365, Number(e.target.value))))}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
              )}
              {waitMode !== "days" && (
                <div className="space-y-1.5">
                  <Label className="text-xs text-zinc-400">Hours</Label>
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={waitHours}
                    onChange={(e) => setWaitHours(Math.max(0, Math.min(23, Number(e.target.value))))}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
              )}
            </div>
          )}
          {step.type === "condition" && (
            <div className="space-y-1.5">
              <Label className="text-zinc-300">Condition to check</Label>
              <Select value={condition} onValueChange={(v) => setCondition(v as typeof condition)}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  {CONDITION_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-zinc-500">
                Green handle (left) = Yes / condition met. Red handle (right) = No / not met.
              </p>
              {(condition === "link_clicked" || condition === "link_not_clicked") && (
                <div className="space-y-1.5 mt-2">
                  <Label className="text-xs text-zinc-400">Tracked link</Label>
                  <Select value={linkKey || "__none"} onValueChange={(value) => setLinkKey(value === "__none" ? "" : value || "")}>
                    <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100"><SelectValue placeholder="Select a campaign link" /></SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                      <SelectItem value="__none">Select a campaign link</SelectItem>
                      {links.filter((link) => !!link.key).map((link) => <SelectItem key={link.id} value={link.key || ""}>{link.name} ({link.key})</SelectItem>)}
                    </SelectContent>
                  </Select>
                  {links.length === 0 && <p className="text-xs text-amber-400/80">Create a tracked link below the sequence first.</p>}
                </div>
              )}
              {["reply_received", "email_opened", "email_not_opened", "link_clicked", "link_not_clicked"].includes(condition) && (
                <div className="space-y-1.5 mt-2">
                  <Label className="text-xs text-zinc-400">Observation window (hours)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={87600}
                    step={0.25}
                    value={observationWindowHours}
                    onChange={(event) => setObservationWindowHours(Math.max(0, Math.min(87600, Number(event.target.value) || 0)))}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                  <p className="text-xs text-zinc-500">The branch stays in Waiting until this window closes, unless the event is observed sooner.</p>
                </div>
              )}
            </div>
          )}
          {step.type === "action" && (
            <div className="space-y-1.5">
              <Label className="text-zinc-300">Required lead data</Label>
              <div className="flex flex-wrap gap-2">
                {[
                  { value: "api_email", label: "Work email" },
                  { value: "phone", label: "Phone / WhatsApp" },
                ].map((opt) => {
                  const checked = requires.includes(opt.value);
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() =>
                        setRequires((prev) =>
                          checked ? prev.filter((r) => r !== opt.value) : [...prev, opt.value],
                        )
                      }
                      className={cn(
                        "text-xs px-2.5 py-1 rounded border transition-colors",
                        checked
                          ? "border-blue-500/50 bg-blue-500/15 text-blue-300"
                          : "border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600",
                      )}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-zinc-500">
                Leads missing required data automatically skip this step.
              </p>
            </div>
          )}
          {step.type === "action" && step.data.action !== "connect" && (
            <div className="space-y-3 rounded-md border border-zinc-800 p-3">
              <Label className="text-zinc-300">Message configuration</Label>
              <Select value={message.content_mode} onValueChange={(value) => setMessage((prev) => ({ ...prev, content_mode: value as "ai_prompt" | "static" }))}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100"><SelectItem value="ai_prompt">AI prompt</SelectItem><SelectItem value="static">Static message</SelectItem></SelectContent>
              </Select>
              {message.content_mode === "ai_prompt" ? <Textarea value={message.prompt} onChange={(event) => setMessage((prev) => ({ ...prev, prompt: event.target.value }))} placeholder="Writing guidance for this message" className="bg-zinc-900 border-zinc-700 text-zinc-100" /> : <Textarea value={message.body} onChange={(event) => setMessage((prev) => ({ ...prev, body: event.target.value }))} placeholder="Message body; use {{link.demo}} for a tracked link" className="bg-zinc-900 border-zinc-700 text-zinc-100" />}
              {(step.data.channel === "email") && <Input value={message.subject} onChange={(event) => setMessage((prev) => ({ ...prev, subject: event.target.value }))} placeholder="Subject (email)" className="bg-zinc-900 border-zinc-700 text-zinc-100" />}
              <div className="space-y-1.5">
                <Label className="text-xs text-zinc-400">Insert tracked link</Label>
                <Select value="__add_link" onValueChange={(value) => {
                  if (value === "__add_link") return;
                  setMessage((prev) => ({
                    ...prev,
                    link_refs: Array.from(new Set([...prev.link_refs, value || ""])).filter(Boolean),
                    body: prev.body?.includes(`{{link.${value}}}`) ? prev.body : `${prev.body || ""}${prev.body ? " " : ""}{{link.${value}}}`,
                  }));
                }}>
                  <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100"><SelectValue placeholder={links.length ? "Choose a campaign link" : "Create a campaign link below"} /></SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                    <SelectItem value="__add_link">Choose a link</SelectItem>
                    {links.filter((link) => !!link.key).map((link) => <SelectItem key={link.id} value={link.key || ""}>{link.name} ({link.key})</SelectItem>)}
                  </SelectContent>
                </Select>
                {message.link_refs.length > 0 && <p className="text-xs text-emerald-400">Tracked: {message.link_refs.join(", ")}</p>}
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-zinc-400">Fallback if generation fails</Label>
                <Select value={message.fallback_mode ?? "continue"} onValueChange={(value) => setMessage((prev) => ({ ...prev, fallback_mode: value as "skip" | "static" | "continue" }))}>
                  <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                    <SelectItem value="continue">Use campaign default message</SelectItem>
                    <SelectItem value="skip">Skip this step</SelectItem>
                    <SelectItem value="static">Use fallback text</SelectItem>
                  </SelectContent>
                </Select>
                {message.fallback_mode === "static" && <Textarea value={message.fallback_body ?? ""} onChange={(event) => setMessage((prev) => ({ ...prev, fallback_body: event.target.value }))} placeholder="Fallback message body" className="bg-zinc-900 border-zinc-700 text-zinc-100" />}
              </div>
              <label className="flex items-center gap-2 text-xs text-zinc-400"><input type="checkbox" checked={message.stop_on_reply} onChange={(event) => setMessage((prev) => ({ ...prev, stop_on_reply: event.target.checked }))} /> Stop this sequence when the lead replies</label>
            </div>
          )}
        </CardContent>
        <div className="flex items-center justify-end gap-2 border-t border-zinc-800 p-4">
          <Button variant="outline" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800" onClick={onClose}>Cancel</Button>
          <Button onClick={save} className="bg-blue-600 hover:bg-blue-700">Apply</Button>
        </div>
    </Card>
  );
}

// ─── SequenceCanvas ───────────────────────────────────────────────────────────

function SequenceCanvas({ campaignId, isActive }: { campaignId: string; isActive?: boolean }) {
  const { toast } = useToast();
  const { fitView } = useReactFlow();

  const [seqSteps, setSeqSteps] = useState<SequenceStep[]>([]);
  const [coverage, setCoverage] = useState<Record<string, number>>({});
  const [totalLeads, setTotalLeads] = useState(0);
  const [channelCoverage, setChannelCoverage] = useState<CampaignChannelCoverage | null>(null);
  const [sequenceMetrics, setSequenceMetrics] = useState<SequenceMetrics | null>(null);
  const [active, setActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [showCanvas, setShowCanvas] = useState(false);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [showActivateDialog, setShowActivateDialog] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [showReplaceDialog, setShowReplaceDialog] = useState(false);
  const [showSaveWhileActiveDialog, setShowSaveWhileActiveDialog] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [campaignLinks, setCampaignLinks] = useState<TrackedLink[]>([]);

  const addMenuRef = useRef<HTMLDivElement>(null);
  const savedSnapshotRef = useRef<string>("");
  const prevIsActiveRef = useRef<boolean | undefined>(undefined);
  // suppress dirty flag during initial fetch
  const suppressDirty = useRef(true);

  const [history, setHistory] = useState<{ nodes: RFNode[]; edges: RFEdge[] }[]>([]);

  const [nodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);

  // stable refs so pushSnapshot doesn't need nodes/edges in its dep array
  const nodesRef = useRef<RFNode[]>([]);
  const edgesRef = useRef<RFEdge[]>([]);
  useEffect(() => { nodesRef.current = nodes; }, [nodes]);
  useEffect(() => { edgesRef.current = edges; }, [edges]);

  useEffect(() => {
    void getCampaignTemplates().then((response) => {
      const rows = response.data?.data ?? [];
      setTemplates(rows.map((template) => ({
        name: template.name,
        description: template.description ?? "",
        sequence_steps: template.sequence_steps,
        sequence_edges: template.sequence_edges,
        channels: template.channels,
        required_data: template.required_data,
      })));
    });
  }, []);

  const pushSnapshot = useCallback(() => {
    setHistory((prev) => [...prev.slice(-19), { nodes: nodesRef.current, edges: edgesRef.current }]);
  }, []);

  // stable node callbacks
  const handleDeleteNode = useCallback((id: string) => {
    pushSnapshot();
    setNodes((prev) => prev.filter((n) => n.id !== id));
    setEdges((prev) => prev.filter((e) => e.source !== id && e.target !== id));
    setEditingStepId((prev) => (prev === id ? null : prev));
    setIsDirty(true);
  }, [pushSnapshot, setNodes, setEdges]);

  const handleEditNode = useCallback((id: string) => {
    setEditingStepId(id);
  }, []);

  const handleUndo = useCallback(() => {
    setHistory((prev) => {
      if (prev.length === 0) return prev;
      const snapshot = prev[prev.length - 1];
      setNodes(snapshot.nodes);
      setEdges(snapshot.edges);
      setIsDirty(true);
      return prev.slice(0, -1);
    });
  }, [setNodes, setEdges]);

  const isValidConnection = useCallback(
    (connection: Connection | RFEdge) => {
      if (connection.source === connection.target) return false;
      const sourceNode = nodesRef.current.find((n) => n.id === connection.source);
      if (!sourceNode) return true;
      if ((sourceNode.data as SeqNodeData).step.type === "end") return false;
      const existingFromHandle = edgesRef.current.filter(
        (e) =>
          e.source === connection.source &&
          (e.sourceHandle ?? null) === ((connection.sourceHandle ?? null) as string | null),
      );
      return existingFromHandle.length === 0;
    },
    [],
  );

  // sync RF nodes → seqSteps (B3: read step directly from node data, no stale closure)
  useEffect(() => {
    if (suppressDirty.current) return;
    setSeqSteps(nodesRef.current.map((n) => ({ ...(n.data as SeqNodeData).step, position: n.position })));
  }, [nodes]);

  // G6: live validation
  useEffect(() => {
    if (suppressDirty.current) return;
    const currentSteps = nodesRef.current.map((n) => ({ ...(n.data as SeqNodeData).step, position: n.position }));
    setValidationWarnings(validateSequence(currentSteps, rfEdgesToSeq(edgesRef.current)));
    const nodeErrors = validateNodeErrors(currentSteps, rfEdgesToSeq(edgesRef.current));
    setNodes((prev) => {
      let changed = false;
      const next = prev.map((node) => {
        const current = (node.data as SeqNodeData).validationErrors ?? [];
        const updated = nodeErrors[node.id] ?? [];
        if (JSON.stringify(current) === JSON.stringify(updated)) return node;
        changed = true;
        return { ...node, data: { ...(node.data as SeqNodeData), validationErrors: updated } };
      });
      return changed ? next : prev;
    });
  }, [nodes, edges, setNodes]);

  // G1: Ctrl+Z undo (skip when focus is inside text input)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!((e.ctrlKey || e.metaKey) && e.key === "z")) return;
      const target = e.target as HTMLElement;
      if (target.tagName === "TEXTAREA" || target.tagName === "INPUT") return;
      e.preventDefault();
      handleUndo();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleUndo]);

  const fetchSequence = useCallback(async () => {
    suppressDirty.current = true;
    setLoading(true);
    setFetchError(false);
    setHistory([]);
    const [res, covRes, metricsRes] = await Promise.all([
      getSequence(campaignId),
      getCampaignCoverage(campaignId),
      getSequenceMetrics(campaignId),
    ]);
    if (metricsRes.data) setSequenceMetrics(metricsRes.data);
    const total = covRes.data?.total ?? 0;
    if (covRes.data) {
      setTotalLeads(total);
      setChannelCoverage(covRes.data.channel_coverage ?? null);
    }
    if (res.data) {
      const loadedSteps = autoLayout(res.data.steps ?? []);
      const loadedEdges = res.data.edges ?? [];
      const cov = res.data.coverage_per_step ?? {};
      setSeqSteps(loadedSteps);
      setCoverage(cov);
      setActive(res.data.active ?? false);
      savedSnapshotRef.current = JSON.stringify({ steps: loadedSteps, edges: loadedEdges });
      if (loadedSteps.length > 0) {
        setShowCanvas(true);
        setNodes(stepsToNodes(loadedSteps, cov, loadedEdges, total, handleDeleteNode, handleEditNode, validateNodeErrors(loadedSteps, loadedEdges)));
        setEdges(edgesToRF(loadedEdges));
        // B1: suppressDirty cleared in onInit callback, not setTimeout
      } else {
        suppressDirty.current = false;
      }
    } else {
      setFetchError(true);
      suppressDirty.current = false;
    }
    setLoading(false);
    setIsDirty(false);
  }, [campaignId, setNodes, setEdges, handleDeleteNode, handleEditNode]);

  useEffect(() => { void fetchSequence(); }, [fetchSequence]);

  useEffect(() => {
    void getLinks(campaignId).then((response) => {
      if (response.data) setCampaignLinks(response.data.data || []);
    });
  }, [campaignId]);

  useEffect(() => {
    if (prevIsActiveRef.current === false && isActive === true && !isDirty && !loading) {
      void fetchSequence();
    }
    prevIsActiveRef.current = isActive;
  }, [isActive, isDirty, loading, fetchSequence]);

  // close add menu on outside click
  useEffect(() => {
    if (!showAddMenu) return;
    const handler = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as unknown as globalThis.Node)) setShowAddMenu(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showAddMenu]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => { if (!isDirty) return; e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  // ── add step ──────────────────────────────────────────────────────────────────

  const addStep = useCallback(
    (opt: (typeof ADD_STEP_OPTIONS)[number]) => {
      pushSnapshot();
      const id = makeId();
      const maxY = nodesRef.current.reduce((m, n) => Math.max(m, n.position.y), 0);
      const newStep: SequenceStep = {
        id,
        type: opt.type,
        data: { channel: opt.channel, action: opt.action, label: opt.label, wait_days: opt.type === "wait" ? 3 : 0, wait_hours: 0, condition: opt.type === "condition" ? "lead_has_email" : undefined, requires: [...opt.requires] },
        position: { x: 300, y: maxY + 160 },
      };
      const instantCov = instantCoverageForStep(newStep, channelCoverage);
      setNodes((prev) => [
        ...prev,
        { id, type: "seq", position: newStep.position, data: { step: newStep, coverage: instantCov, totalLeads, hasBypass: false, onDelete: handleDeleteNode, onEdit: handleEditNode } },
      ]);
      setShowAddMenu(false);
      setIsDirty(true);
      if (opt.type === "condition") setEditingStepId(id);
    },
    [pushSnapshot, handleDeleteNode, handleEditNode, setNodes, totalLeads, channelCoverage],
  );

  // ── connect ───────────────────────────────────────────────────────────────────

  const onConnect = useCallback(
    (connection: Connection) => {
      pushSnapshot();
      const branch = connection.sourceHandle === "yes" ? "yes" : connection.sourceHandle === "no" ? "no" : undefined;
      const newEdge: RFEdge = {
        id: `e_${connection.source}_${connection.target}${branch ? `_${branch}` : ""}`,
        source: connection.source!,
        target: connection.target!,
        sourceHandle: connection.sourceHandle ?? undefined,
        targetHandle: connection.targetHandle ?? undefined,
        type: "seq",
        data: branch ? { condition: branch } : {},
        markerEnd: { type: MarkerType.ArrowClosed, color: "#52525b", width: 12, height: 12 },
      };
      setEdges((prev) => addEdge(newEdge, prev));
      setIsDirty(true);
    },
    [pushSnapshot, setEdges],
  );

  // ── update step ───────────────────────────────────────────────────────────────

  const handleUpdateStep = useCallback(
    (updated: SequenceStep) => {
      pushSnapshot();
      setNodes((prev) =>
        prev.map((n) => n.id === updated.id ? { ...n, data: { ...(n.data as SeqNodeData), step: updated } } : n),
      );
      setSeqSteps((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setIsDirty(true);
    },
    [pushSnapshot, setNodes],
  );

  // ── save ──────────────────────────────────────────────────────────────────────

  const executeSave = async (): Promise<boolean> => {
    const currentSteps = nodes.map((n) => ({ ...(n.data as SeqNodeData).step, position: n.position }));
    const currentEdges = rfEdgesToSeq(edges);
    setValidationWarnings([]);
    const warnings = validateSequence(currentSteps, currentEdges);
    setValidationWarnings(warnings);
    if (warnings.some((w) => w.includes("disconnected") || w.includes("no outgoing") || w.includes("no duration"))) return false;

    setSaving(true);
    const res = await saveSequence(campaignId, currentSteps, currentEdges);
    setSaving(false);
    if (res.error) {
      toast({ title: "Save failed", description: res.error, variant: "destructive" });
      return false;
    }
    savedSnapshotRef.current = JSON.stringify({ steps: currentSteps, edges: currentEdges });
    setIsDirty(false);
    setValidationWarnings([]);
    // refresh coverage and channel totals
    const [refreshed, covRefresh] = await Promise.all([
      getSequence(campaignId),
      getCampaignCoverage(campaignId),
    ]);
    const refreshedTotal = covRefresh.data?.total ?? totalLeads;
    if (covRefresh.data?.channel_coverage) setChannelCoverage(covRefresh.data.channel_coverage);
    if (refreshedTotal !== totalLeads) setTotalLeads(refreshedTotal);
    if (refreshed.data?.coverage_per_step) {
      const cov = refreshed.data.coverage_per_step;
      setCoverage(cov);
      setNodes((prev) => {
        const currentEdges = edgesRef.current;
        return prev.map((n) => ({
          ...n,
          data: {
            ...(n.data as SeqNodeData),
            coverage: cov[n.id] ?? null,
            totalLeads: refreshedTotal,
            hasBypass: hasBypassPath(n.id, prev, currentEdges),
          },
        }));
      });
    }
    toast({ title: "Sequence saved" });
    return true;
  };

  const handleSave = async () => { if (active) { setShowSaveWhileActiveDialog(true); return; } await executeSave(); };
  const handleConfirmSaveWhileActive = async () => {
    setShowSaveWhileActiveDialog(false);
    toast({ title: "Deactivate sequence first", description: "Graph edits are blocked while a sequence is active to protect in-progress deals.", variant: "destructive" });
  };

  const handleSaveAsTemplate = async () => {
    const name = window.prompt("Template name", "My campaign workflow");
    if (!name?.trim()) return;
    const response = await saveCampaignAsTemplate(campaignId, { name: name.trim() });
    if (response.error) {
      toast({ title: "Could not save template", description: response.error, variant: "destructive" });
      return;
    }
    toast({ title: "Template saved" });
  };

  const handleActivateClick = () => setShowActivateDialog(true);

  const handleConfirmActivate = async () => {
    setShowActivateDialog(false);
    if (isDirty) { const saved = await executeSave(); if (!saved) return; }
    setToggling(true);
    const nextActive = !active;
    const res = await setSequenceActive(campaignId, nextActive);
    setToggling(false);
    if (res.error) {
      const detail = (res as { data?: { detail?: unknown } }).data?.detail;
      const errList: string[] = Array.isArray(detail)
        ? (detail as string[])
        : [typeof detail === "string" ? detail : (res.error ?? "Activation failed")];
      setValidationWarnings(errList);
      toast({ title: "Activation failed", description: errList[0], variant: "destructive" });
      return;
    }
    setActive(nextActive);
    setValidationWarnings([]);
    toast({ title: nextActive ? "Sequence activated" : "Sequence deactivated" });
  };

  const handleConfirmReset = () => {
    setNodes([]); setEdges([]); setSeqSteps([]);
    setShowCanvas(false); setIsDirty(false); setShowResetDialog(false); setValidationWarnings([]); setHistory([]);
  };

  const applyTemplate = (tpl: Template) => {
    const idMap = new Map<string, string>();
    tpl.sequence_steps.forEach((s) => idMap.set(s.id, makeId()));
    const freshSteps = autoLayout(tpl.sequence_steps.map((s) => ({ ...s, id: idMap.get(s.id)! })));
    const freshEdges = tpl.sequence_edges.map((e) => ({
      ...e,
      id: `edge_${idMap.get(e.source)}_${idMap.get(e.target)}${e.data?.condition ? `_${e.data.condition}` : ""}`,
      source: idMap.get(e.source) ?? e.source,
      target: idMap.get(e.target) ?? e.target,
    }));
    suppressDirty.current = false;
    setSeqSteps(freshSteps);
    setNodes(stepsToNodes(freshSteps, {}, freshEdges, totalLeads, handleDeleteNode, handleEditNode, validateNodeErrors(freshSteps, freshEdges)));
    setEdges(edgesToRF(freshEdges));
    setShowCanvas(true);
    setIsDirty(true);
    requestAnimationFrame(() => void fitView({ padding: 0.15 }));
  };

  // ── derived ───────────────────────────────────────────────────────────────────

  const editingStep =
    seqSteps.find((s) => s.id === editingStepId) ??
    (nodes.find((n) => n.id === editingStepId)?.data as SeqNodeData | undefined)?.step;

  const sequenceSummary = (() => {
    const ac = seqSteps.filter((s) => s.type === "action").length;
    const td = seqSteps.filter((s) => s.type === "wait").reduce((a, s) => a + (s.data.wait_days || 0), 0);
    if (ac === 0) return null;
    return `${ac} action${ac !== 1 ? "s" : ""} · ~${td}d`;
  })();

  // ── render ────────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <Card className="border-zinc-800">
        <CardContent className="py-12 text-center text-zinc-500">
          <Icons.RefreshCw className="h-6 w-6 mx-auto animate-spin mb-2" />
          Loading sequence…
        </CardContent>
      </Card>
    );
  }

  if (fetchError) {
    return (
      <Card className="border-zinc-800">
        <CardContent className="py-12 text-center text-zinc-500">
          <p className="mb-4">Failed to load sequence.</p>
          <Button variant="outline" onClick={() => void fetchSequence()}>
            <Icons.RefreshCw className="h-4 w-4 mr-2" />Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!showCanvas) {
    return (
      <Card className="border-zinc-800">
        <CardHeader>
          <CardTitle>Sequence Builder</CardTitle>
          <CardDescription>No sequence configured — campaign uses default single-channel behavior.</CardDescription>
        </CardHeader>
        <CardContent className="py-6 space-y-6">
          <p className="text-sm text-zinc-400">
            Build a multi-step, multi-path outreach sequence. Use{" "}
            <strong className="text-zinc-200">Branch / Gate</strong> nodes to route leads down different paths (for example, email availability or link engagement).
            Drag from a node handle to connect steps.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {templates.map((tpl) => {
              // Compute which channels this template uses
              const usesEmail = tpl.channels?.includes("email") || tpl.required_data?.includes("api_email");
              const usesWhatsApp = tpl.channels?.includes("whatsapp") || tpl.required_data?.includes("phone");
              const emailPct = channelCoverage?.email.pct ?? null;
              const whatsappPct = channelCoverage?.whatsapp.pct ?? null;
              const hasZeroCoverage =
                (usesEmail && emailPct === 0) || (usesWhatsApp && whatsappPct === 0);
              return (
                <div
                  key={tpl.name}
                  className={cn(
                    "rounded-lg border bg-zinc-900/50 p-4 cursor-pointer transition-all",
                    hasZeroCoverage
                      ? "border-amber-500/30 hover:border-amber-500/50 hover:bg-zinc-900"
                      : "border-zinc-800 hover:border-blue-500/50 hover:bg-zinc-900",
                  )}
                  onClick={() => applyTemplate(tpl)}
                >
                  <div className="font-medium text-sm text-zinc-200 mb-1">{tpl.name}</div>
                  <div className="text-xs text-zinc-500 mb-2">{tpl.description}</div>
                  {channelCoverage && (usesEmail || usesWhatsApp) && (
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {usesEmail && emailPct !== null && (
                        <span className={cn(
                          "text-[10px] flex items-center gap-0.5 px-1.5 py-0.5 rounded border",
                          emailPct === 0
                            ? "border-amber-500/40 bg-amber-500/10 text-amber-400"
                            : emailPct < 30
                              ? "border-red-500/40 bg-red-500/10 text-red-400"
                              : "border-zinc-700 text-zinc-400",
                        )}>
                          <Mail className="h-2.5 w-2.5" />
                          {emailPct}%
                          {emailPct === 0 && " ⚠"}
                        </span>
                      )}
                      {usesWhatsApp && whatsappPct !== null && (
                        <span className={cn(
                          "text-[10px] flex items-center gap-0.5 px-1.5 py-0.5 rounded border",
                          whatsappPct === 0
                            ? "border-amber-500/40 bg-amber-500/10 text-amber-400"
                            : whatsappPct < 30
                              ? "border-red-500/40 bg-red-500/10 text-red-400"
                              : "border-zinc-700 text-zinc-400",
                        )}>
                          <Smartphone className="h-2.5 w-2.5" />
                          {whatsappPct}%
                          {whatsappPct === 0 && " ⚠"}
                        </span>
                      )}
                    </div>
                  )}
                  {hasZeroCoverage && (
                    <p className="text-[10px] text-amber-500/80 mt-1.5">
                      Most leads will skip the 0% channel step.
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              onClick={() => { suppressDirty.current = false; setShowCanvas(true); }}
              className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            >
              <Plus className="mr-2 h-4 w-4" />
              Start from scratch
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <TooltipProvider>
      <div className="space-y-3">
        {validationWarnings.length > 0 && (
          <Alert className="border-red-500/30 bg-red-500/10 text-red-400">
            <Icons.AlertTriangle className="h-4 w-4 text-red-400" />
            <AlertDescription>
              <ul className="ml-1 space-y-0.5">
                {validationWarnings.map((w, i) => <li key={i} className="text-sm">{w}</li>)}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {/* Toolbar */}
        <Card className="border-zinc-800">
          <CardContent className="py-3 px-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-zinc-200">Sequence Builder</span>
                <Badge
                  variant="outline"
                  className={cn("text-xs", active ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-zinc-600 text-zinc-500")}
                >
                  {active ? "Active" : "Inactive"}
                </Badge>
                {sequenceSummary && <span className="text-xs text-zinc-500">{sequenceSummary}</span>}
                {sequenceMetrics && (sequenceMetrics.stuck_deals > 0 || sequenceMetrics.error_deals > 0) && (
                  <Badge variant="outline" className="text-xs border-red-500/30 bg-red-500/10 text-red-400">
                    {sequenceMetrics.error_deals} errors · {sequenceMetrics.stuck_deals} stuck
                  </Badge>
                )}
                {totalLeads > 0 && <span className="text-xs text-zinc-600">·</span>}
                {totalLeads > 0 && channelCoverage && (
                  <>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className={cn("text-xs flex items-center gap-1 cursor-default", channelCoverage.linkedin.pct >= 70 ? "text-blue-400" : channelCoverage.linkedin.pct >= 30 ? "text-amber-400" : "text-red-400")}>
                          <Network className="h-3 w-3" />{channelCoverage.linkedin.pct}%
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="text-xs">{channelCoverage.linkedin.count} of {totalLeads} leads have LinkedIn</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className={cn("text-xs flex items-center gap-1 cursor-default", channelCoverage.email.pct >= 70 ? "text-amber-400" : channelCoverage.email.pct >= 30 ? "text-amber-300" : channelCoverage.email.pct === 0 ? "text-zinc-600" : "text-red-400")}>
                          <Mail className="h-3 w-3" />{channelCoverage.email.pct}%
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="text-xs">{channelCoverage.email.count} of {totalLeads} leads have email</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className={cn("text-xs flex items-center gap-1 cursor-default", channelCoverage.whatsapp.pct >= 70 ? "text-emerald-400" : channelCoverage.whatsapp.pct >= 30 ? "text-emerald-300" : channelCoverage.whatsapp.pct === 0 ? "text-zinc-600" : "text-red-400")}>
                          <Smartphone className="h-3 w-3" />{channelCoverage.whatsapp.pct}%
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="text-xs">{channelCoverage.whatsapp.count} of {totalLeads} leads have WhatsApp</TooltipContent>
                    </Tooltip>
                  </>
                )}
                {totalLeads === 0 && (
                  <span className="text-xs text-zinc-600">Import leads to see channel coverage</span>
                )}
                {isDirty && (
                  <Badge variant="outline" className="text-xs border-amber-500/30 bg-amber-500/10 text-amber-400">
                    Unsaved
                  </Badge>
                )}
              </div>

              <div className="flex items-center gap-2">
                <div className="relative" ref={addMenuRef}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                    onClick={() => setShowAddMenu((v) => !v)}
                  >
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    Add Step
                  </Button>
                  {showAddMenu && (
                    <div className="absolute top-full left-0 mt-1 z-50 rounded-md border border-zinc-800 bg-zinc-950 shadow-lg py-1 min-w-[220px]">
                      {ADD_STEP_OPTIONS.map((opt) => {
                        const cov = instantCoverageForStep(
                          { id: "", type: opt.type, data: { channel: opt.channel, action: opt.action, label: opt.label, wait_days: 0, wait_hours: 0, condition: opt.type === "condition" ? "lead_has_email" : undefined, requires: opt.requires }, position: { x: 0, y: 0 } },
                          channelCoverage,
                        );
                        const hasZeroCov = cov !== null && cov === 0;
                        return (
                          <button
                            key={`${opt.type}-${opt.action}`}
                            className="w-full text-left px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 flex items-center justify-between gap-2"
                            onClick={() => addStep(opt)}
                          >
                            <span>{opt.label}</span>
                            {cov !== null && (
                              <span className={cn(
                                "text-[10px] shrink-0",
                                cov === 0 ? "text-amber-400" : cov < 30 ? "text-red-400" : "text-zinc-500",
                              )}>
                                {cov}%{hasZeroCov ? " ⚠" : ""}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {history.length > 0 && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-zinc-700 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                        onClick={handleUndo}
                      >
                        <Undo2 className="h-3.5 w-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="text-xs">Undo (Ctrl+Z)</TooltipContent>
                  </Tooltip>
                )}

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-zinc-700 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                      onClick={() => setShowResetDialog(true)}
                    >
                      <Icons.RotateCcw className="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="text-xs">Reset to templates</TooltipContent>
                </Tooltip>

                <Button
                  variant="outline"
                  size="sm"
                  className={cn("border-zinc-700 hover:bg-zinc-800", isDirty ? "text-amber-400 border-amber-500/30" : "text-zinc-300")}
                  onClick={handleSave}
                  disabled={!isDirty || saving || toggling}
                >
                  {saving ? <Icons.RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Icons.Save className="mr-1.5 h-3.5 w-3.5" />}
                  Save
                </Button>

                <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800" onClick={() => void handleSaveAsTemplate()} disabled={saving || toggling}>
                  Save as template
                </Button>

                <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800" onClick={() => setShowReplaceDialog(true)} disabled={active || saving || toggling}>
                  Replace from template
                </Button>

                <Button
                  size="sm"
                  className={cn(active ? "bg-zinc-700 hover:bg-zinc-600 text-zinc-200" : "bg-blue-600 hover:bg-blue-700")}
                  onClick={handleActivateClick}
                  disabled={toggling || saving || (nodes.length === 0 && !active)}
                >
                  {toggling ? (
                    <Icons.RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : active ? (
                    <Icons.Pause className="mr-1.5 h-3.5 w-3.5" />
                  ) : (
                    <Icons.Play className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  {active ? "Deactivate" : "Activate"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Canvas and persistent node inspector */}
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="rounded-xl border border-zinc-800 overflow-hidden" style={{ height: 580 }}>
            <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={(changes) => {
              const removed = changes.filter((c) => c.type === "remove").map((c) => (c as { id: string }).id);
              if (removed.length > 0) pushSnapshot();
              onNodesChange(changes);
              if (!suppressDirty.current) setIsDirty(true);
              if (editingStepId && removed.includes(editingStepId)) setEditingStepId(null);
            }}
            onEdgesChange={(changes) => { onEdgesChange(changes); if (!suppressDirty.current) setIsDirty(true); }}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            onInit={() => { suppressDirty.current = false; void fitView({ padding: 0.15 }); }}
            deleteKeyCode={["Backspace", "Delete"]}
            proOptions={{ hideAttribution: true }}
            className="bg-zinc-950"
            defaultEdgeOptions={{
              type: "seq",
              markerEnd: { type: MarkerType.ArrowClosed, color: "#52525b", width: 12, height: 12 },
            }}
          >
            <Background color="#27272a" gap={20} size={1} />
            <Controls className="[&>button]:bg-zinc-900 [&>button]:border-zinc-700 [&>button]:text-zinc-400 [&>button:hover]:bg-zinc-800" />
            <MiniMap
              nodeColor={(n) => {
                const step = (n.data as SeqNodeData)?.step;
                if (!step) return "#27272a";
                const colorMap: Record<string, string> = {
                  connect: "#3b82f6", follow_up: "#3b82f6", send_email: "#f59e0b",
                  send_whatsapp: "#10b981", wait: "#52525b", condition: "#a855f7", end: "#f43f5e",
                };
                return colorMap[stepColorKey(step)] ?? "#52525b";
              }}
              className="!bg-zinc-900 !border-zinc-800"
              maskColor="rgba(0,0,0,0.5)"
            />
            <Panel position="bottom-center">
              <p className="text-[10px] text-zinc-600 bg-zinc-950/80 px-2 py-1 rounded">
                Drag to pan · Scroll to zoom · Drag handle to connect · Del/Backspace removes selected
              </p>
            </Panel>
            </ReactFlow>
          </div>

          {editingStep ? (
            <ConfigPanel key={editingStep.id} step={editingStep} links={campaignLinks} onChange={handleUpdateStep} onClose={() => setEditingStepId(null)} />
          ) : (
            <Card className="flex min-h-[220px] items-center justify-center border-zinc-800 bg-zinc-950 text-center">
              <CardContent className="space-y-2 py-8">
                <p className="text-sm font-medium text-zinc-300">Node inspector</p>
                <p className="max-w-[240px] text-xs text-zinc-500">Select a workflow node to edit its timing, conditions, message, links, and stop rules.</p>
              </CardContent>
            </Card>
          )}
        </div>

        <AlertDialog open={showActivateDialog} onOpenChange={setShowActivateDialog}>
          <AlertDialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100">
            <AlertDialogHeader>
              <AlertDialogTitle>{active ? "Deactivate sequence?" : "Activate sequence?"}</AlertDialogTitle>
              <AlertDialogDescription className="text-zinc-400 space-y-1">
                {!active && isDirty && <span className="block text-amber-400 text-sm">Unsaved changes will be saved first.</span>}
                <span className="block">
                  {active
                    ? "The daemon stops executing steps. Deals in progress pause at their current position."
                    : "The daemon starts executing steps for all active deals in this campaign."}
                </span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 bg-zinc-900">Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmActivate}
                className={active ? "bg-zinc-700 hover:bg-zinc-600 text-zinc-200" : "bg-blue-600 hover:bg-blue-700"}
              >
                {active ? "Deactivate" : isDirty ? "Save & Activate" : "Activate"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <AlertDialog open={showSaveWhileActiveDialog} onOpenChange={setShowSaveWhileActiveDialog}>
          <AlertDialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100">
            <AlertDialogHeader>
              <AlertDialogTitle>Save while sequence is active?</AlertDialogTitle>
              <AlertDialogDescription className="text-zinc-400">
                Graph edits are blocked while active to protect in-progress deals. Deactivate the sequence, edit and save, then activate it again.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 bg-zinc-900">Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleConfirmSaveWhileActive} className="bg-blue-600 hover:bg-blue-700">Got it</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <AlertDialog open={showResetDialog} onOpenChange={setShowResetDialog}>
          <AlertDialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100">
            <AlertDialogHeader>
              <AlertDialogTitle>Reset sequence?</AlertDialogTitle>
              <AlertDialogDescription className="text-zinc-400">
                All steps will be cleared and you&apos;ll return to the template picker.
                {isDirty && " Unsaved changes will be lost."}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 bg-zinc-900">Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleConfirmReset} className="bg-red-600 hover:bg-red-700">Reset</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <AlertDialog open={showReplaceDialog} onOpenChange={setShowReplaceDialog}>
          <AlertDialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100">
            <AlertDialogHeader>
              <AlertDialogTitle>Replace workflow from a template?</AlertDialogTitle>
              <AlertDialogDescription className="text-zinc-400">
                This replaces the current workflow and discards unsaved graph changes. The selected template will be copied into this campaign as an unsaved draft.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="max-h-64 space-y-2 overflow-y-auto py-2">
              {templates.map((tpl) => (
                <Button
                  key={tpl.name}
                  variant="outline"
                  className="h-auto w-full justify-start border-zinc-700 bg-zinc-900 text-left text-zinc-200 hover:bg-zinc-800"
                  onClick={() => { setShowReplaceDialog(false); applyTemplate(tpl); }}
                >
                  <span>
                    <span className="block text-sm font-medium">{tpl.name}</span>
                    <span className="block text-xs font-normal text-zinc-500">{tpl.description}</span>
                  </span>
                </Button>
              ))}
              {templates.length === 0 && <p className="text-sm text-zinc-500">No templates are available.</p>}
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 bg-zinc-900">Cancel</AlertDialogCancel>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  );
}

// ─── public export ────────────────────────────────────────────────────────────

interface SequenceBuilderProps {
  campaignId: string;
  isActive?: boolean;
}

export function SequenceBuilder({ campaignId, isActive }: SequenceBuilderProps) {
  return (
    <ReactFlowProvider>
      <SequenceCanvas campaignId={campaignId} isActive={isActive} />
    </ReactFlowProvider>
  );
}
