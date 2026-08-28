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
  SequenceStep,
  SequenceEdge,
} from "@/lib/api/campaigns";
import { useToast } from "@/components/ui/use-toast";
import { Network, Mail, Smartphone, Clock, GitBranch, Flag, Plus, X, Undo2 } from "lucide-react";

// ─── constants ────────────────────────────────────────────────────────────────

const STEP_COLORS: Record<string, { border: string; bg: string; text: string; ring: string }> = {
  connect:       { border: "border-blue-500/40",    bg: "bg-blue-500/10",    text: "text-blue-300",    ring: "ring-blue-500" },
  follow_up:     { border: "border-blue-500/40",    bg: "bg-blue-500/10",    text: "text-blue-300",    ring: "ring-blue-500" },
  send_email:    { border: "border-amber-500/40",   bg: "bg-amber-500/10",   text: "text-amber-300",   ring: "ring-amber-500" },
  send_whatsapp: { border: "border-emerald-500/40", bg: "bg-emerald-500/10", text: "text-emerald-300", ring: "ring-emerald-500" },
  wait:          { border: "border-zinc-600/40",    bg: "bg-zinc-800/50",    text: "text-zinc-400",    ring: "ring-zinc-500" },
  condition:     { border: "border-purple-500/40",  bg: "bg-purple-500/10",  text: "text-purple-300",  ring: "ring-purple-500" },
  end:           { border: "border-rose-500/40",    bg: "bg-rose-500/10",    text: "text-rose-300",    ring: "ring-rose-500" },
};

const STEP_KEY_LABELS: Record<string, string> = {
  connect:       "LinkedIn Connect",
  follow_up:     "LinkedIn Follow-up",
  send_email:    "Send Email",
  send_whatsapp: "Send WhatsApp",
  wait:          "Wait",
  condition:     "Branch / Gate",
  end:           "End",
};

const CONDITION_OPTIONS = [
  { value: "always",   label: "Always proceed" },
  { value: "no_reply", label: "If no reply" },
  { value: "replied",  label: "If replied" },
  { value: "no_open",  label: "If not opened" },
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
                {step.data.wait_days || 1} day{(step.data.wait_days || 1) !== 1 ? "s" : ""}
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

      {d.coverage !== null && (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="mt-2 cursor-default">
              <Progress value={d.coverage} className="h-1 bg-zinc-800 [&>div]:bg-current" />
              <span className="text-[10px] opacity-50 mt-0.5 inline-block">{d.coverage}% leads covered</span>
            </div>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-[200px] text-xs">
            Percentage of leads in this campaign that have the required data for this step.
          </TooltipContent>
        </Tooltip>
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
  onDelete: (id: string) => void,
  onEdit: (id: string) => void,
): RFNode[] {
  return steps.map((step) => ({
    id: step.id,
    type: "seq",
    position: step.position,
    data: { step, coverage: coverage[step.id] ?? null, onDelete, onEdit },
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
      label: typeof e.label === "string" ? e.label : undefined,
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
  if (!steps.some((s) => s.type === "action")) warnings.push("Add at least one action step (Connect or Follow-up).");
  if (!steps.some((s) => s.type === "end")) warnings.push("Add an End step.");
  const noOutgoing = steps.filter((s) => s.type !== "end" && !edgeSources.has(s.id));
  if (noOutgoing.length > 0) {
    warnings.push(
      `${noOutgoing.map((s) => `"${s.data.label}"`).join(", ")} ${noOutgoing.length === 1 ? "has" : "have"} no outgoing connection.`,
    );
  }
  return warnings;
}

// ─── templates ────────────────────────────────────────────────────────────────

function makeStep(
  id: string,
  type: SequenceStep["type"],
  action: SequenceStep["data"]["action"],
  channel: SequenceStep["data"]["channel"],
  label: string,
  waitDays = 0,
  requires: string[] = [],
  condition: SequenceStep["data"]["condition"] = "always",
): SequenceStep {
  return { id, type, data: { channel, action, label, wait_days: waitDays, condition, requires }, position: { x: 0, y: 0 } };
}

function makeSeqEdge(source: string, target: string, branch?: string): SequenceEdge {
  return {
    id: `e_${source}_${target}${branch ? `_${branch}` : ""}`,
    source,
    target,
    data: branch ? { condition: branch } : undefined,
  };
}

type Template = { name: string; description: string; steps: SequenceStep[]; edges: SequenceEdge[] };

const TEMPLATES: Template[] = [
  {
    name: "LinkedIn Only",
    description: "Connect → 3d → Follow-up → 7d → Follow-up → End",
    steps: [
      makeStep("t1", "action",  "connect",   "linkedin", "LinkedIn Connect"),
      makeStep("t2", "wait",    null,          null,      "Wait 3 days", 3),
      makeStep("t3", "action",  "follow_up",  "linkedin", "LinkedIn Follow-up"),
      makeStep("t4", "wait",    null,          null,      "Wait 7 days", 7),
      makeStep("t5", "action",  "follow_up",  "linkedin", "LinkedIn Follow-up #2"),
      makeStep("t6", "end",     null,          null,      "End"),
    ],
    edges: [
      makeSeqEdge("t1","t2"), makeSeqEdge("t2","t3"), makeSeqEdge("t3","t4"),
      makeSeqEdge("t4","t5"), makeSeqEdge("t5","t6"),
    ],
  },
  {
    name: "LinkedIn + Email",
    description: "Connect → 3d → Branch (no reply → Email, replied → End) → Follow-up → End",
    steps: [
      makeStep("t1", "action",    "connect",   "linkedin", "LinkedIn Connect"),
      makeStep("t2", "wait",      null,          null,     "Wait 3 days", 3),
      makeStep("t3", "condition", null,          null,     "Got a reply?", 0, [], "replied"),
      makeStep("t4", "action",    "send_email", "email",   "Send Email", 0, ["api_email"]),
      makeStep("t5", "wait",      null,          null,     "Wait 5 days", 5),
      makeStep("t6", "action",    "follow_up",  "linkedin","LinkedIn Follow-up"),
      makeStep("t7", "end",       null,          null,     "End"),
      makeStep("t8", "end",       null,          null,     "End (replied)"),
    ],
    edges: [
      makeSeqEdge("t1","t2"),
      makeSeqEdge("t2","t3"),
      makeSeqEdge("t3","t8","yes"),
      makeSeqEdge("t3","t4","no"),
      makeSeqEdge("t4","t5"),
      makeSeqEdge("t5","t6"),
      makeSeqEdge("t6","t7"),
    ],
  },
  {
    name: "Full Multichannel",
    description: "Connect → Branch → Email path + WhatsApp path → Follow-up → End",
    steps: [
      makeStep("t1", "action",    "connect",       "linkedin",  "LinkedIn Connect"),
      makeStep("t2", "wait",      null,             null,        "Wait 3 days", 3),
      makeStep("t3", "condition", null,             null,        "Has email?", 0, [], "no_reply"),
      makeStep("t4", "action",    "send_email",    "email",     "Send Email", 0, ["api_email"]),
      makeStep("t5", "action",    "send_whatsapp", "whatsapp",  "Send WhatsApp", 0, ["phone"]),
      makeStep("t6", "wait",      null,             null,        "Wait 5 days", 5),
      makeStep("t7", "action",    "follow_up",     "linkedin",  "LinkedIn Follow-up"),
      makeStep("t8", "end",       null,             null,        "End"),
    ],
    edges: [
      makeSeqEdge("t1","t2"),
      makeSeqEdge("t2","t3"),
      makeSeqEdge("t3","t4","yes"),
      makeSeqEdge("t3","t5","no"),
      makeSeqEdge("t4","t6"),
      makeSeqEdge("t5","t6"),
      makeSeqEdge("t6","t7"),
      makeSeqEdge("t7","t8"),
    ],
  },
];

const ADD_STEP_OPTIONS = [
  { type: "action"    as const, action: "connect"        as const, channel: "linkedin"  as const, label: "LinkedIn Connect",   requires: [] as string[] },
  { type: "action"    as const, action: "follow_up"      as const, channel: "linkedin"  as const, label: "LinkedIn Follow-up", requires: [] as string[] },
  { type: "action"    as const, action: "send_email"     as const, channel: "email"     as const, label: "Send Email",         requires: ["api_email"] as string[] },
  { type: "action"    as const, action: "send_whatsapp"  as const, channel: "whatsapp"  as const, label: "Send WhatsApp",      requires: ["phone"] as string[] },
  { type: "wait"      as const, action: null,                       channel: null,                 label: "Wait",               requires: [] as string[] },
  { type: "condition" as const, action: null,                       channel: null,                 label: "Branch / Gate",      requires: [] as string[] },
  { type: "end"       as const, action: null,                       channel: null,                 label: "End",                requires: [] as string[] },
];

// ─── ConfigPanel ──────────────────────────────────────────────────────────────

function ConfigPanel({ step, onChange, onClose }: { step: SequenceStep; onChange: (u: SequenceStep) => void; onClose: () => void }) {
  const [label, setLabel] = useState(step.data.label);
  const [condition, setCondition] = useState(step.data.condition ?? "always");
  const [waitDays, setWaitDays] = useState(Math.max(1, step.data.wait_days || 1));

  useEffect(() => {
    setLabel(step.data.label);
    setCondition(step.data.condition ?? "always");
    setWaitDays(Math.max(1, step.data.wait_days || 1));
  }, [step.id, step.data.label, step.data.condition, step.data.wait_days]);

  const save = () => {
    onChange({ ...step, data: { ...step.data, label, condition, ...(step.type === "wait" ? { wait_days: waitDays } : {}) } });
    onClose();
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-[400px] bg-zinc-950 border-zinc-800 text-zinc-100">
        <DialogHeader>
          <DialogTitle>Configure Step</DialogTitle>
          <DialogDescription className="text-zinc-400">
            {step.type === "action" && step.data.action === "connect"       && "Sends a LinkedIn connection request."}
            {step.type === "action" && step.data.action === "follow_up"     && "Sends a LinkedIn follow-up message via the campaign AI agent."}
            {step.type === "action" && step.data.action === "send_email"    && "Sends an email to the lead's work address."}
            {step.type === "action" && step.data.action === "send_whatsapp" && "Sends a WhatsApp message to the lead's phone number."}
            {step.type === "wait"      && "Pauses the sequence for the given number of days before proceeding."}
            {step.type === "condition" && "Routes leads down two paths. Drag from the green handle (Yes/left) and red handle (No/right) to connect both branches."}
            {step.type === "end"       && "Marks the end of this path."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
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
            <div className="space-y-1.5">
              <Label className="text-zinc-300">Wait Days</Label>
              <Input
                type="number"
                min={1}
                max={90}
                value={waitDays}
                onChange={(e) => setWaitDays(Math.max(1, Math.min(90, Number(e.target.value))))}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
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
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" className="border-zinc-700 text-zinc-300 hover:bg-zinc-800" onClick={onClose}>Cancel</Button>
          <Button onClick={save} className="bg-blue-600 hover:bg-blue-700">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── SequenceCanvas ───────────────────────────────────────────────────────────

function SequenceCanvas({ campaignId, isActive }: { campaignId: string; isActive?: boolean }) {
  const { toast } = useToast();
  const { fitView } = useReactFlow();

  const [seqSteps, setSeqSteps] = useState<SequenceStep[]>([]);
  const [coverage, setCoverage] = useState<Record<string, number>>({});
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
  const [showSaveWhileActiveDialog, setShowSaveWhileActiveDialog] = useState(false);

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

  const pushSnapshot = useCallback(() => {
    setHistory((prev) => [...prev.slice(-19), { nodes: nodesRef.current, edges: edgesRef.current }]);
  }, []);

  // stable node callbacks
  const handleDeleteNode = useCallback((id: string) => {
    pushSnapshot();
    setNodes((prev) => prev.filter((n) => n.id !== id));
    setEdges((prev) => prev.filter((e) => e.source !== id && e.target !== id));
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
  }, [nodes, edges]);

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
    const res = await getSequence(campaignId);
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
        setNodes(stepsToNodes(loadedSteps, cov, handleDeleteNode, handleEditNode));
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
        data: { channel: opt.channel, action: opt.action, label: opt.label, wait_days: opt.type === "wait" ? 3 : 0, condition: "always", requires: [...opt.requires] },
        position: { x: 300, y: maxY + 160 },
      };
      setNodes((prev) => [
        ...prev,
        { id, type: "seq", position: newStep.position, data: { step: newStep, coverage: null, onDelete: handleDeleteNode, onEdit: handleEditNode } },
      ]);
      setShowAddMenu(false);
      setIsDirty(true);
      if (opt.type === "condition") setEditingStepId(id);
    },
    [pushSnapshot, handleDeleteNode, handleEditNode, setNodes],
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
    if (warnings.some((w) => w.includes("disconnected") || w.includes("no outgoing"))) return false;

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
    // refresh coverage
    const refreshed = await getSequence(campaignId);
    if (refreshed.data?.coverage_per_step) {
      const cov = refreshed.data.coverage_per_step;
      setCoverage(cov);
      setNodes((prev) => prev.map((n) => ({ ...n, data: { ...(n.data as SeqNodeData), coverage: cov[n.id] ?? null } })));
    }
    toast({ title: "Sequence saved" });
    return true;
  };

  const handleSave = async () => { if (active) { setShowSaveWhileActiveDialog(true); return; } await executeSave(); };
  const handleConfirmSaveWhileActive = async () => { setShowSaveWhileActiveDialog(false); await executeSave(); };

  const handleActivateClick = () => setShowActivateDialog(true);

  const handleConfirmActivate = async () => {
    setShowActivateDialog(false);
    if (isDirty) { const saved = await executeSave(); if (!saved) return; }
    setToggling(true);
    const nextActive = !active;
    const res = await setSequenceActive(campaignId, nextActive);
    setToggling(false);
    if (res.error) {
      const errList = (res as { data?: { errors?: string[] } }).data?.errors ?? [res.error ?? "Failed"];
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
    tpl.steps.forEach((s) => idMap.set(s.id, makeId()));
    const freshSteps = autoLayout(tpl.steps.map((s) => ({ ...s, id: idMap.get(s.id)! })));
    const freshEdges = tpl.edges.map((e) => ({
      ...e,
      id: `edge_${idMap.get(e.source)}_${idMap.get(e.target)}${e.data?.condition ? `_${e.data.condition}` : ""}`,
      source: idMap.get(e.source) ?? e.source,
      target: idMap.get(e.target) ?? e.target,
    }));
    suppressDirty.current = false;
    setSeqSteps(freshSteps);
    setNodes(stepsToNodes(freshSteps, {}, handleDeleteNode, handleEditNode));
    setEdges(edgesToRF(freshEdges));
    setShowCanvas(true);
    setIsDirty(true);
    setTimeout(() => void fitView({ padding: 0.15 }), 50);
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
            <strong className="text-zinc-200">Branch / Gate</strong> nodes to route leads down different paths (e.g. replied vs. no reply).
            Drag from a node handle to connect steps.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {TEMPLATES.map((tpl) => (
              <div
                key={tpl.name}
                className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 cursor-pointer hover:border-blue-500/50 hover:bg-zinc-900 transition-all"
                onClick={() => applyTemplate(tpl)}
              >
                <div className="font-medium text-sm text-zinc-200 mb-1">{tpl.name}</div>
                <div className="text-xs text-zinc-500">{tpl.description}</div>
              </div>
            ))}
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
                    <div className="absolute top-full left-0 mt-1 z-50 rounded-md border border-zinc-800 bg-zinc-950 shadow-lg py-1 min-w-[190px]">
                      {ADD_STEP_OPTIONS.map((opt) => (
                        <button
                          key={`${opt.type}-${opt.action}`}
                          className="w-full text-left px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                          onClick={() => addStep(opt)}
                        >
                          {opt.label}
                        </button>
                      ))}
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

        {/* Canvas */}
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

        {editingStep && (
          <ConfigPanel key={editingStep.id} step={editingStep} onChange={handleUpdateStep} onClose={() => setEditingStepId(null)} />
        )}

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
                Saving updates what the daemon executes for deals already in progress. Completed steps are unaffected; pending steps use the new configuration immediately.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 bg-zinc-900">Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleConfirmSaveWhileActive} className="bg-blue-600 hover:bg-blue-700">Save Anyway</AlertDialogAction>
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
