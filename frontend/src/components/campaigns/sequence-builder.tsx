"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
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
import {
  Network,
  Mail,
  Smartphone,
  Clock,
  GitBranch,
  Flag,
  ArrowDown,
  GripVertical,
} from "lucide-react";

// ─── constants ───────────────────────────────────────────────────────────────

const STEP_LABELS: Record<string, string> = {
  connect: "LinkedIn Connect",
  follow_up: "LinkedIn Follow-up",
  send_email: "Send Email",
  send_whatsapp: "Send WhatsApp",
  wait: "Wait",
  condition: "Condition",
  end: "End",
};

const CONDITION_LABELS: Record<string, string> = {
  always: "Always proceed",
  no_reply: "If no reply",
  no_open: "If not opened",
  replied: "If replied",
};

const STEP_COLORS: Record<string, string> = {
  connect: "border-blue-500/30 bg-blue-500/5 text-blue-400",
  follow_up: "border-blue-500/30 bg-blue-500/5 text-blue-400",
  send_email: "border-amber-500/30 bg-amber-500/5 text-amber-400",
  send_whatsapp: "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
  wait: "border-zinc-500/30 bg-zinc-500/5 text-zinc-400",
  condition: "border-purple-500/30 bg-purple-500/5 text-purple-400",
  end: "border-red-500/30 bg-red-500/5 text-red-400",
};

const ADD_STEP_OPTIONS = [
  {
    type: "action" as const,
    action: "connect" as const,
    channel: "linkedin" as const,
    label: "LinkedIn Connect",
    requires: [] as string[],
  },
  {
    type: "action" as const,
    action: "follow_up" as const,
    channel: "linkedin" as const,
    label: "LinkedIn Follow-up",
    requires: [] as string[],
  },
  {
    type: "action" as const,
    action: "send_email" as const,
    channel: "email" as const,
    label: "Send Email",
    requires: ["api_email"] as string[],
  },
  {
    type: "action" as const,
    action: "send_whatsapp" as const,
    channel: "whatsapp" as const,
    label: "Send WhatsApp",
    requires: ["phone"] as string[],
  },
  {
    type: "wait" as const,
    action: null,
    channel: null,
    label: "Wait",
    requires: [] as string[],
  },
  {
    type: "condition" as const,
    action: null,
    channel: null,
    label: "Condition",
    requires: [] as string[],
  },
  {
    type: "end" as const,
    action: null,
    channel: null,
    label: "End",
    requires: [] as string[],
  },
];

function stepKey(step: SequenceStep): string {
  return step.data.action || step.type;
}

// ─── types ────────────────────────────────────────────────────────────────────

type Snapshot = { steps: SequenceStep[]; edges: SequenceEdge[] };

// ─── validation ───────────────────────────────────────────────────────────────

function validateSequence(
  steps: SequenceStep[],
  edges: SequenceEdge[],
): string[] {
  if (steps.length === 0) return [];
  const warnings: string[] = [];
  const edgeTargets = new Set(edges.map((e) => e.target));
  const edgeSources = new Set(edges.map((e) => e.source));
  const roots = steps.filter((s) => !edgeTargets.has(s.id));
  if (roots.length > 1) {
    warnings.push(
      `${roots.length} disconnected steps — every step must connect to the next.`,
    );
  }
  if (!steps.some((s) => s.type === "action")) {
    warnings.push("Add at least one action step (Connect or Follow-up).");
  }
  if (!steps.some((s) => s.type === "end")) {
    warnings.push("Add an End step to mark where the sequence finishes.");
  }
  const noOutgoing = steps.filter(
    (s) => s.type !== "end" && !edgeSources.has(s.id),
  );
  if (noOutgoing.length > 0) {
    warnings.push(
      `${noOutgoing.map((s) => `"${s.data.label}"`).join(", ")} ${noOutgoing.length === 1 ? "has" : "have"} no outgoing connection.`,
    );
  }
  return warnings;
}

// ─── StepIcon ────────────────────────────────────────────────────────────────

function StepIcon({ step }: { step: SequenceStep }) {
  const key = stepKey(step);
  if (key === "connect" || key === "follow_up")
    return <Network className="h-4 w-4" />;
  if (key === "send_email") return <Mail className="h-4 w-4" />;
  if (key === "send_whatsapp") return <Smartphone className="h-4 w-4" />;
  if (key === "wait") return <Clock className="h-4 w-4" />;
  if (key === "condition") return <GitBranch className="h-4 w-4" />;
  return <Flag className="h-4 w-4" />;
}

// ─── NodeCard ─────────────────────────────────────────────────────────────────

interface NodeCardProps {
  step: SequenceStep;
  coverage: number | null;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onUpdateWaitDays?: (days: number) => void;
}

function NodeCard({
  step,
  coverage,
  selected,
  onSelect,
  onDelete,
  onUpdateWaitDays,
}: NodeCardProps) {
  const key = stepKey(step);
  const colorClass = STEP_COLORS[key] || STEP_COLORS.wait;
  const label = step.data.label || STEP_LABELS[key] || key;
  const isWait = step.type === "wait";
  const isCondition = step.type === "condition";

  return (
    <div
      className={cn(
        "rounded-lg border-2 p-3 cursor-pointer transition-all select-none w-full",
        colorClass,
        selected && "ring-2 ring-offset-2 ring-offset-zinc-950 ring-blue-500",
      )}
      onClick={onSelect}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0 flex-wrap">
          <StepIcon step={step} />
          <span className="text-sm font-medium truncate">{label}</span>
          {step.data.requires && step.data.requires.length > 0 && (
            <Badge
              variant="outline"
              className="text-xs shrink-0 border-zinc-600 text-zinc-400"
            >
              needs {step.data.requires.join(", ")}
            </Badge>
          )}
          {/* Fix #4 / #9: show configured condition on card */}
          {isCondition &&
            step.data.condition &&
            step.data.condition !== "always" && (
              <Badge
                variant="outline"
                className="text-xs shrink-0 border-purple-500/30 text-purple-400"
              >
                {CONDITION_LABELS[step.data.condition] ?? step.data.condition}
              </Badge>
            )}
        </div>
        <button
          className="text-zinc-600 hover:text-red-400 transition-colors shrink-0"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          aria-label="Delete step"
        >
          <Icons.Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {isWait && (
        <div
          className="mt-2 flex items-center gap-2"
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="number"
            min={1}
            max={90}
            value={step.data.wait_days > 0 ? step.data.wait_days : 1}
            onChange={(e) => {
              const v = Math.max(1, Math.min(90, Number(e.target.value)));
              onUpdateWaitDays?.(v);
            }}
            className="w-14 bg-zinc-900 border border-zinc-700 rounded text-xs text-zinc-200 px-1.5 py-0.5 focus:outline-none focus:border-zinc-500 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          />
          <span className="text-xs text-zinc-500">days</span>
        </div>
      )}

      {coverage !== null && (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="mt-2 cursor-default">
              <Progress
                value={coverage}
                className="h-1 bg-zinc-800 [&>div]:bg-current"
              />
              <span className="text-xs opacity-60 mt-0.5 inline-block">
                {coverage}% leads covered
              </span>
            </div>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-[220px] text-xs">
            % of leads in this campaign that have the required data for this
            step (e.g. a work email for email steps).
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}

// ─── ConfigPanel ──────────────────────────────────────────────────────────────

interface ConfigPanelProps {
  step: SequenceStep;
  onChange: (updated: SequenceStep) => void;
  onClose: () => void;
}

function ConfigPanel({ step, onChange, onClose }: ConfigPanelProps) {
  const [label, setLabel] = useState(step.data.label);
  const [condition, setCondition] = useState(step.data.condition ?? "always");

  const save = () => {
    onChange({ ...step, data: { ...step.data, label, condition } });
    onClose();
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-[400px] bg-zinc-950 border-zinc-800 text-zinc-100">
        <DialogHeader>
          <DialogTitle>Configure Step</DialogTitle>
          <DialogDescription className="text-zinc-400">
            {step.type === "action" && step.data.action === "connect" &&
              "Sends a LinkedIn connection request to the lead."}
            {step.type === "action" && step.data.action === "follow_up" &&
              "Sends a LinkedIn message via the campaign follow-up agent."}
            {step.type === "action" && step.data.action === "send_email" &&
              "Sends an email to the lead's work email address."}
            {step.type === "action" && step.data.action === "send_whatsapp" &&
              "Sends a WhatsApp message to the lead's phone number."}
            {step.type === "condition" &&
              "Checks a condition before proceeding. If not met, the sequence stops for that lead."}
            {step.type === "end" && "Marks the end of the sequence."}
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
          {step.type === "condition" && (
            <div className="space-y-1.5">
              <Label className="text-zinc-300">Condition</Label>
              <Select
                value={condition}
                onValueChange={(v) => setCondition(v as typeof condition)}
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  <SelectItem value="always">Always proceed</SelectItem>
                  <SelectItem value="no_reply">
                    Only if no reply received
                  </SelectItem>
                  <SelectItem value="no_open">
                    Only if email not opened
                  </SelectItem>
                  <SelectItem value="replied">
                    Only if reply received
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-zinc-500">
                If the condition is not met, the sequence stops for that lead.
              </p>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button onClick={save} className="bg-blue-600 hover:bg-blue-700">
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── SortableItem ─────────────────────────────────────────────────────────────

interface SortableItemProps extends NodeCardProps {
  id: string;
}

function SortableItem({ id, ...props }: SortableItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 w-full max-w-sm"
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            {...attributes}
            {...listeners}
            className="text-zinc-700 hover:text-zinc-400 cursor-grab active:cursor-grabbing shrink-0 touch-none"
            aria-label="Drag to reorder"
            tabIndex={-1}
          >
            <GripVertical className="h-4 w-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="left" className="text-xs">
          Drag to reorder
        </TooltipContent>
      </Tooltip>
      <div className="flex-1 min-w-0">
        <NodeCard {...props} />
      </div>
    </div>
  );
}

// ─── templates ────────────────────────────────────────────────────────────────

type Template = {
  name: string;
  description: string;
  steps: SequenceStep[];
  edges: SequenceEdge[];
};

function makeStep(
  id: string,
  type: SequenceStep["type"],
  action: SequenceStep["data"]["action"],
  channel: SequenceStep["data"]["channel"],
  label: string,
  waitDays = 0,
  requires: string[] = [],
): SequenceStep {
  return {
    id,
    type,
    data: { channel, action, label, wait_days: waitDays, condition: "always", requires },
    position: { x: 200, y: 0 },
  };
}

function makeEdge(source: string, target: string): SequenceEdge {
  return { id: `e_${source}_${target}`, source, target };
}

const TEMPLATES: Template[] = [
  {
    name: "LinkedIn Only",
    description: "Connect → 3d → Follow-up → 7d → Follow-up → End",
    steps: [
      makeStep("t1", "action", "connect", "linkedin", "LinkedIn Connect"),
      makeStep("t2", "wait", null, null, "Wait 3 days", 3),
      makeStep("t3", "action", "follow_up", "linkedin", "LinkedIn Follow-up"),
      makeStep("t4", "wait", null, null, "Wait 7 days", 7),
      makeStep("t5", "action", "follow_up", "linkedin", "LinkedIn Follow-up #2"),
      makeStep("t6", "end", null, null, "End"),
    ],
    edges: [
      makeEdge("t1", "t2"), makeEdge("t2", "t3"), makeEdge("t3", "t4"),
      makeEdge("t4", "t5"), makeEdge("t5", "t6"),
    ],
  },
  {
    name: "LinkedIn + Email",
    description: "Connect → 3d → no reply check → Email → 5d → Follow-up → End",
    steps: [
      makeStep("t1", "action", "connect", "linkedin", "LinkedIn Connect"),
      makeStep("t2", "wait", null, null, "Wait 3 days", 3),
      makeStep("t3", "condition", null, null, "No reply?"),
      makeStep("t4", "action", "send_email", "email", "Send Email", 0, ["api_email"]),
      makeStep("t5", "wait", null, null, "Wait 5 days", 5),
      makeStep("t6", "action", "follow_up", "linkedin", "LinkedIn Follow-up"),
      makeStep("t7", "end", null, null, "End"),
    ],
    edges: [
      makeEdge("t1", "t2"), makeEdge("t2", "t3"), makeEdge("t3", "t4"),
      makeEdge("t4", "t5"), makeEdge("t5", "t6"), makeEdge("t6", "t7"),
    ],
  },
  {
    name: "Full Multichannel",
    description: "Connect → Email → WhatsApp → Follow-up → End",
    steps: [
      makeStep("t1", "action", "connect", "linkedin", "LinkedIn Connect"),
      makeStep("t2", "wait", null, null, "Wait 3 days", 3),
      makeStep("t3", "action", "send_email", "email", "Send Email", 0, ["api_email"]),
      makeStep("t4", "wait", null, null, "Wait 5 days", 5),
      makeStep("t5", "action", "send_whatsapp", "whatsapp", "Send WhatsApp", 0, ["phone"]),
      makeStep("t6", "wait", null, null, "Wait 3 days", 3),
      makeStep("t7", "action", "follow_up", "linkedin", "LinkedIn Follow-up"),
      makeStep("t8", "end", null, null, "End"),
    ],
    edges: [
      makeEdge("t1", "t2"), makeEdge("t2", "t3"), makeEdge("t3", "t4"),
      makeEdge("t4", "t5"), makeEdge("t5", "t6"), makeEdge("t6", "t7"),
      makeEdge("t7", "t8"),
    ],
  },
];

// ─── SequenceBuilder ──────────────────────────────────────────────────────────

interface SequenceBuilderProps {
  campaignId: string;
}

export function SequenceBuilder({ campaignId }: SequenceBuilderProps) {
  const { toast } = useToast();

  const [steps, setSteps] = useState<SequenceStep[]>([]);
  const [edges, setEdges] = useState<SequenceEdge[]>([]);
  const [active, setActive] = useState(false);
  const [coverage, setCoverage] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [insertAfterIndex, setInsertAfterIndex] = useState<number | null>(null);
  const [showCanvas, setShowCanvas] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  // Fix #8: proper dialogs replacing window.confirm
  const [showActivateDialog, setShowActivateDialog] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);
  // Fix #12: undo history
  const [history, setHistory] = useState<Snapshot[]>([]);

  const initialLoad = useRef(true);
  // Fix #10: click-outside ref for toolbar add-step dropdown
  const addMenuRef = useRef<HTMLDivElement>(null);

  // ── fetch ───────────────────────────────────────────────────────────────────

  const fetchSequence = useCallback(async () => {
    setLoading(true);
    const res = await getSequence(campaignId);
    if (res.data) {
      setSteps(res.data.steps ?? []);
      setEdges(res.data.edges ?? []);
      setActive(res.data.active ?? false);
      setCoverage(res.data.coverage_per_step ?? {});
      if ((res.data.steps ?? []).length > 0) setShowCanvas(true);
    }
    setLoading(false);
    setIsDirty(false);
    setHistory([]);
    initialLoad.current = false;
  }, [campaignId]);

  useEffect(() => { void fetchSequence(); }, [fetchSequence]);

  useEffect(() => {
    if (initialLoad.current) return;
    setIsDirty(true);
  }, [steps, edges]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!isDirty) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  // Fix #10: close toolbar dropdown on outside click
  useEffect(() => {
    if (!showAddMenu) return;
    const handler = (e: MouseEvent) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) {
        setShowAddMenu(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showAddMenu]);

  // Close inline insert popover on outside click
  useEffect(() => {
    if (insertAfterIndex === null) return;
    const handler = (e: MouseEvent) => {
      if (!(e.target as Element).closest("[data-insert-popover]")) {
        setInsertAfterIndex(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [insertAfterIndex]);

  // ── undo ────────────────────────────────────────────────────────────────────

  const pushSnapshot = useCallback(() => {
    setHistory((prev) => [...prev.slice(-19), { steps, edges }]);
  }, [steps, edges]);

  const handleUndo = useCallback(() => {
    setHistory((prev) => {
      if (prev.length === 0) return prev;
      const snapshot = prev[prev.length - 1];
      // setState calls inside setHistory updater run synchronously in the same batch
      setSteps(snapshot.steps);
      setEdges(snapshot.edges);
      return prev.slice(0, -1);
    });
  }, []);

  // Fix #12: Ctrl+Z keyboard shortcut (placed after handleUndo is declared)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        handleUndo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleUndo]);

  // ── mutations ────────────────────────────────────────────────────────────────

  // Fix #3: toolbar add inserts before last End step; edge bridging is correct
  const addStep = useCallback(
    (opt: (typeof ADD_STEP_OPTIONS)[number], afterIndex?: number) => {
      pushSnapshot();
      const id = `step_${Date.now()}`;
      const newStep: SequenceStep = {
        id,
        type: opt.type,
        data: {
          channel: opt.channel,
          action: opt.action,
          label: opt.label,
          wait_days: opt.type === "wait" ? 3 : 0,
          condition: "always",
          requires: [...opt.requires],
        },
        position: { x: 200, y: 0 },
      };

      let insertIdx: number;
      if (afterIndex !== undefined) {
        insertIdx = afterIndex;
      } else {
        // Insert before the last End step, falling back to end-of-list
        const endIdx = steps.reduceRight(
          (acc, s, i) => (acc === -1 && s.type === "end" ? i : acc),
          -1,
        );
        insertIdx = endIdx > 0 ? endIdx - 1 : steps.length - 1;
      }

      // Capture edge neighbours from current closure before setState
      const prevStepId = steps[insertIdx]?.id;
      const nextStepId = steps[insertIdx + 1]?.id;

      setSteps((prev) => {
        const next = [...prev];
        next.splice(insertIdx + 1, 0, newStep);
        return next;
      });

      setEdges((prev) => {
        let next = [...prev];
        if (prevStepId && nextStepId) {
          // Bridge: remove old direct edge, route through new step
          next = next.filter(
            (e) => !(e.source === prevStepId && e.target === nextStepId),
          );
          next.push({ id: `edge_${prevStepId}_${id}`, source: prevStepId, target: id });
          next.push({ id: `edge_${id}_${nextStepId}`, source: id, target: nextStepId });
        } else if (prevStepId) {
          next.push({ id: `edge_${prevStepId}_${id}`, source: prevStepId, target: id });
        }
        return next;
      });

      setShowAddMenu(false);
      setInsertAfterIndex(null);
      if (opt.type === "condition") {
        setSelectedStepId(id);
      }
    },
    [steps, pushSnapshot],
  );

  // Fix #1: reconnect predecessor → successor on delete
  const deleteStep = useCallback(
    (stepId: string) => {
      pushSnapshot();
      const incomingEdge = edges.find((e) => e.target === stepId);
      const outgoingEdge = edges.find((e) => e.source === stepId);

      setSteps((prev) => prev.filter((s) => s.id !== stepId));
      setEdges((prev) => {
        const filtered = prev.filter(
          (e) => e.source !== stepId && e.target !== stepId,
        );
        if (incomingEdge && outgoingEdge) {
          return [
            ...filtered,
            {
              id: `edge_${incomingEdge.source}_${outgoingEdge.target}`,
              source: incomingEdge.source,
              target: outgoingEdge.target,
            },
          ];
        }
        return filtered;
      });

      if (selectedStepId === stepId) setSelectedStepId(null);
    },
    [edges, selectedStepId, pushSnapshot],
  );

  const updateStep = useCallback((updated: SequenceStep) => {
    setSteps((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    setSelectedStepId(null);
  }, []);

  const updateStepWaitDays = useCallback((stepId: string, days: number) => {
    setSteps((prev) =>
      prev.map((s) =>
        s.id === stepId ? { ...s, data: { ...s.data, wait_days: days } } : s,
      ),
    );
  }, []);

  // ── drag ─────────────────────────────────────────────────────────────────────

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active: dragActive, over } = event;
      if (!over || dragActive.id === over.id) return;
      pushSnapshot();
      setSteps((prev) => {
        const oldIdx = prev.findIndex((s) => s.id === dragActive.id);
        const newIdx = prev.findIndex((s) => s.id === over.id);
        const reordered = arrayMove(prev, oldIdx, newIdx);
        const newEdges: SequenceEdge[] = reordered.slice(0, -1).map((s, i) => ({
          id: `edge_${s.id}_${reordered[i + 1].id}`,
          source: s.id,
          target: reordered[i + 1].id,
        }));
        setEdges(newEdges);
        return reordered;
      });
    },
    [pushSnapshot],
  );

  // ── save / activate ──────────────────────────────────────────────────────────

  const handleSave = async (): Promise<boolean> => {
    // Fix #6: client-side validation
    const warnings = validateSequence(steps, edges);
    setValidationWarnings(warnings);
    const hasDisconnected = warnings.some((w) =>
      w.includes("disconnected") || w.includes("no outgoing"),
    );
    if (hasDisconnected) return false;

    setSaving(true);
    const res = await saveSequence(campaignId, steps, edges);
    setSaving(false);
    if (res.error) {
      toast({ title: "Save failed", description: res.error, variant: "destructive" });
      return false;
    }
    setIsDirty(false);
    setValidationWarnings([]);
    toast({ title: "Sequence saved" });
    return true;
  };

  // Fix #2: open dialog instead of activating immediately
  const handleActivateClick = () => setShowActivateDialog(true);

  // Fix #2 + #8: save-if-dirty then activate
  const handleConfirmActivate = async () => {
    setShowActivateDialog(false);
    if (isDirty) {
      const saved = await handleSave();
      if (!saved) return;
    }
    setToggling(true);
    const nextActive = !active;
    const res = await setSequenceActive(campaignId, nextActive);
    setToggling(false);
    if (res.error) {
      // Backend returns { detail: { errors: [...] } } for validation failures
      const errDetail = (res as { data?: { errors?: string[] } }).data;
      const errList =
        errDetail?.errors?.length
          ? errDetail.errors
          : [res.error ?? "Failed to update sequence"];
      setValidationWarnings(errList);
      toast({ title: "Activation failed", description: errList[0], variant: "destructive" });
      return;
    }
    setActive(nextActive);
    setValidationWarnings([]);
    toast({ title: nextActive ? "Sequence activated" : "Sequence deactivated" });
  };

  // Fix #7: reset to template picker
  const handleConfirmReset = () => {
    setSteps([]);
    setEdges([]);
    setShowCanvas(false);
    setIsDirty(false);
    setShowResetDialog(false);
    setValidationWarnings([]);
    setHistory([]);
  };

  const applyTemplate = (tpl: Template) => {
    setSteps(tpl.steps);
    setEdges(tpl.edges);
    setShowCanvas(true);
  };

  // ── derived ───────────────────────────────────────────────────────────────────

  const selectedStep = steps.find((s) => s.id === selectedStepId);

  const sequenceSummary = (() => {
    const actionCount = steps.filter((s) => s.type === "action").length;
    const totalDays = steps
      .filter((s) => s.type === "wait")
      .reduce((acc, s) => acc + (s.data.wait_days || 0), 0);
    if (actionCount === 0) return null;
    return `${actionCount} action${actionCount !== 1 ? "s" : ""} · ~${totalDays} day${totalDays !== 1 ? "s" : ""}`;
  })();

  // ── render: loading ───────────────────────────────────────────────────────────

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

  // ── render: template picker ───────────────────────────────────────────────────

  if (!showCanvas) {
    return (
      <Card className="border-zinc-800">
        <CardHeader>
          <CardTitle>Sequence Builder</CardTitle>
          <CardDescription>
            No sequence configured — campaign uses default single-channel behavior.
          </CardDescription>
        </CardHeader>
        <CardContent className="py-6 space-y-6">
          <p className="text-sm text-zinc-400">
            Build a multi-step outreach sequence, or start from a template.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {TEMPLATES.map((tpl) => (
              <div
                key={tpl.name}
                className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 cursor-pointer hover:border-blue-500/50 hover:bg-zinc-900 transition-all"
                onClick={() => applyTemplate(tpl)}
              >
                <div className="font-medium text-sm text-zinc-200 mb-1">
                  {tpl.name}
                </div>
                <div className="text-xs text-zinc-500">{tpl.description}</div>
              </div>
            ))}
          </div>
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              onClick={() => setShowCanvas(true)}
              className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            >
              <Icons.Plus className="mr-2 h-4 w-4" />
              Start from scratch
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // ── render: canvas ────────────────────────────────────────────────────────────

  return (
    <TooltipProvider>
      <div className="space-y-4">
        {/* Fix #6: validation warning banner */}
        {validationWarnings.length > 0 && (
          <Alert className="border-red-500/30 bg-red-500/10 text-red-400">
            <Icons.AlertTriangle className="h-4 w-4 text-red-400" />
            <AlertDescription>
              <ul className="space-y-0.5 ml-1">
                {validationWarnings.map((w, i) => (
                  <li key={i} className="text-sm">
                    {w}
                  </li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {/* Toolbar */}
        <Card className="border-zinc-800">
          <CardContent className="py-3 px-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-zinc-200">
                  Sequence Builder
                </span>
                <Badge
                  variant="outline"
                  className={cn(
                    "text-xs",
                    active
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                      : "border-zinc-600 text-zinc-500",
                  )}
                >
                  {active ? "Active" : "Inactive"}
                </Badge>
                {sequenceSummary && (
                  <span className="text-xs text-zinc-500">{sequenceSummary}</span>
                )}
                {isDirty && (
                  <Badge
                    variant="outline"
                    className="text-xs border-amber-500/30 bg-amber-500/10 text-amber-400"
                  >
                    Unsaved changes
                  </Badge>
                )}
              </div>

              <div className="flex items-center gap-2">
                {/* Fix #12: undo button */}
                {history.length > 0 && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                        onClick={handleUndo}
                      >
                        <Icons.RotateCcw className="h-3.5 w-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="text-xs">
                      Undo (Ctrl+Z)
                    </TooltipContent>
                  </Tooltip>
                )}

                {/* Fix #10: add-step dropdown with outside-click ref */}
                <div className="relative" ref={addMenuRef}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                    onClick={() => setShowAddMenu((v) => !v)}
                  >
                    <Icons.Plus className="mr-1.5 h-3.5 w-3.5" />
                    Add Step
                  </Button>
                  {showAddMenu && (
                    <div className="absolute top-full left-0 mt-1 z-50 rounded-md border border-zinc-800 bg-zinc-950 shadow-lg py-1 min-w-[180px]">
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

                {/* Fix #7: reset button */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-zinc-700 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
                      onClick={() => setShowResetDialog(true)}
                    >
                      <Icons.RefreshCw className="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent className="text-xs">
                    Reset to templates
                  </TooltipContent>
                </Tooltip>

                <Button
                  variant="outline"
                  size="sm"
                  className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? (
                    <Icons.RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Icons.Save className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  Save
                </Button>

                {/* Fix #2 + #8: dialog instead of window.confirm */}
                <Button
                  size="sm"
                  className={cn(
                    active
                      ? "bg-zinc-700 hover:bg-zinc-600 text-zinc-200"
                      : "bg-blue-600 hover:bg-blue-700",
                  )}
                  onClick={handleActivateClick}
                  disabled={toggling || (steps.length === 0 && !active)}
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
        <Card className="border-zinc-800">
          <CardContent className="py-6">
            {steps.length === 0 ? (
              <div className="text-center py-10 text-zinc-500 text-sm">
                No steps yet. Click &ldquo;Add Step&rdquo; to begin.
              </div>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={steps.map((s) => s.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="flex flex-col items-center gap-0">
                    {steps.map((step, idx) => (
                      <div
                        key={step.id}
                        className="flex flex-col items-center w-full max-w-sm"
                      >
                        <SortableItem
                          id={step.id}
                          step={step}
                          coverage={coverage[step.id] ?? null}
                          selected={selectedStepId === step.id}
                          onSelect={() => {
                            if (step.type === "wait") return;
                            setSelectedStepId(
                              step.id === selectedStepId ? null : step.id,
                            );
                          }}
                          onDelete={() => deleteStep(step.id)}
                          onUpdateWaitDays={(days) =>
                            updateStepWaitDays(step.id, days)
                          }
                        />

                        {idx < steps.length - 1 &&
                          (() => {
                            const outEdge = edges.find(
                              (e) => e.source === step.id,
                            );
                            const edgeCond = (
                              outEdge?.data as { condition?: string } | undefined
                            )?.condition;
                            const edgeLabel =
                              edgeCond && edgeCond !== "always"
                                ? (
                                    {
                                      no_reply: "no reply",
                                      replied: "replied",
                                      no_open: "not opened",
                                    } as Record<string, string>
                                  )[edgeCond]
                                : null;

                            return (
                              <div
                                className="flex flex-col items-center w-full max-w-sm relative group/connector"
                                data-insert-popover
                              >
                                <div className="w-px h-3 bg-zinc-800" />
                                {edgeLabel && (
                                  <span className="text-[10px] text-zinc-600 px-1.5 py-0.5 rounded border border-zinc-800 bg-zinc-950 mb-0.5 select-none">
                                    {edgeLabel}
                                  </span>
                                )}
                                {/* Fix #11: tooltip on insert button */}
                                <div className="relative flex items-center justify-center">
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <button
                                        className="opacity-0 group-hover/connector:opacity-100 transition-opacity w-5 h-5 rounded-full border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 hover:border-zinc-500 flex items-center justify-center z-10"
                                        onClick={() =>
                                          setInsertAfterIndex(
                                            insertAfterIndex === idx ? null : idx,
                                          )
                                        }
                                      >
                                        <Icons.Plus className="h-3 w-3 text-zinc-400" />
                                      </button>
                                    </TooltipTrigger>
                                    <TooltipContent side="right" className="text-xs">
                                      Insert step here
                                    </TooltipContent>
                                  </Tooltip>

                                  {insertAfterIndex === idx && (
                                    <div
                                      className="absolute top-full mt-1 z-50 rounded-md border border-zinc-800 bg-zinc-950 shadow-xl py-1 min-w-[190px]"
                                      data-insert-popover
                                    >
                                      <div className="px-3 py-1 text-xs text-zinc-600 font-medium uppercase tracking-wider">
                                        Insert step
                                      </div>
                                      {ADD_STEP_OPTIONS.map((opt) => (
                                        <button
                                          key={`${opt.type}-${opt.action}`}
                                          className="w-full text-left px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
                                          onClick={() => addStep(opt, idx)}
                                        >
                                          {opt.label}
                                        </button>
                                      ))}
                                      <div className="border-t border-zinc-800 mt-1 pt-1">
                                        <button
                                          className="w-full text-left px-3 py-1 text-xs text-zinc-600 hover:bg-zinc-800"
                                          onClick={() => setInsertAfterIndex(null)}
                                        >
                                          Cancel
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </div>
                                <div className="w-px h-3 bg-zinc-800" />
                                <ArrowDown className="h-4 w-4 text-zinc-700" />
                              </div>
                            );
                          })()}
                      </div>
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            )}
          </CardContent>
        </Card>

        {/* Config dialog */}
        {selectedStep && (
          <ConfigPanel
            step={selectedStep}
            onChange={updateStep}
            onClose={() => setSelectedStepId(null)}
          />
        )}

        {/* Fix #8: activate / deactivate confirmation */}
        <AlertDialog open={showActivateDialog} onOpenChange={setShowActivateDialog}>
          <AlertDialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100">
            <AlertDialogHeader>
              <AlertDialogTitle>
                {active ? "Deactivate sequence?" : "Activate sequence?"}
              </AlertDialogTitle>
              <AlertDialogDescription className="text-zinc-400 space-y-1">
                {!active && isDirty && (
                  <span className="block text-amber-400 text-sm">
                    You have unsaved changes — they will be saved first.
                  </span>
                )}
                <span className="block">
                  {active
                    ? "The daemon will stop executing steps. Deals in progress will pause at their current position."
                    : "The daemon will start executing steps for all active deals in this campaign."}
                </span>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 bg-zinc-900">
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmActivate}
                className={
                  active
                    ? "bg-zinc-700 hover:bg-zinc-600 text-zinc-200"
                    : "bg-blue-600 hover:bg-blue-700"
                }
              >
                {active ? "Deactivate" : isDirty ? "Save & Activate" : "Activate"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Fix #7: reset confirmation */}
        <AlertDialog open={showResetDialog} onOpenChange={setShowResetDialog}>
          <AlertDialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100">
            <AlertDialogHeader>
              <AlertDialogTitle>Reset sequence?</AlertDialogTitle>
              <AlertDialogDescription className="text-zinc-400">
                All steps will be cleared and you&apos;ll return to the template
                picker.{isDirty && " Unsaved changes will be lost."}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="border-zinc-700 text-zinc-300 hover:bg-zinc-800 bg-zinc-900">
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmReset}
                className="bg-red-600 hover:bg-red-700"
              >
                Reset
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  );
}
