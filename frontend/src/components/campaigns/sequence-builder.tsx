"use client";

import { useState, useEffect, useCallback } from "react";
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Network, Mail, Smartphone, Clock, GitBranch, Flag, ArrowDown } from "lucide-react";

const STEP_LABELS: Record<string, string> = {
  connect: "LinkedIn Connect",
  follow_up: "LinkedIn Follow-up",
  send_email: "Send Email",
  send_whatsapp: "Send WhatsApp",
  wait: "Wait",
  condition: "Condition",
  end: "End",
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

function stepKey(step: SequenceStep): string {
  return step.data.action || step.type;
}

function StepIcon({ step }: { step: SequenceStep }) {
  const key = stepKey(step);
  if (key === "connect" || key === "follow_up") return <Network className="h-4 w-4" />;
  if (key === "send_email") return <Mail className="h-4 w-4" />;
  if (key === "send_whatsapp") return <Smartphone className="h-4 w-4" />;
  if (key === "wait") return <Clock className="h-4 w-4" />;
  if (key === "condition") return <GitBranch className="h-4 w-4" />;
  return <Flag className="h-4 w-4" />;
}

interface NodeCardProps {
  step: SequenceStep;
  coverage: number | null;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

function NodeCard({ step, coverage, selected, onSelect, onDelete }: NodeCardProps) {
  const key = stepKey(step);
  const colorClass = STEP_COLORS[key] || STEP_COLORS.wait;
  const label = step.data.label || STEP_LABELS[key] || key;

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
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <StepIcon step={step} />
          <span className="text-sm font-medium truncate">{label}</span>
          {step.data.requires && step.data.requires.length > 0 && (
            <Badge variant="outline" className="text-xs shrink-0 border-zinc-600 text-zinc-400">
              needs {step.data.requires.join(", ")}
            </Badge>
          )}
          {step.type === "wait" && step.data.wait_days > 0 && (
            <span className="text-xs text-zinc-500">{step.data.wait_days}d</span>
          )}
        </div>
        <button
          className="text-zinc-600 hover:text-red-400 transition-colors shrink-0"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          aria-label="Delete step"
        >
          <Icons.Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      {coverage !== null && (
        <div className="mt-2">
          <Progress value={coverage} className="h-1 bg-zinc-800 [&>div]:bg-current" />
          <span className="text-xs opacity-60 mt-0.5 inline-block">{coverage}% leads covered</span>
        </div>
      )}
    </div>
  );
}

interface ConfigPanelProps {
  step: SequenceStep;
  onChange: (updated: SequenceStep) => void;
  onClose: () => void;
}

function ConfigPanel({ step, onChange, onClose }: ConfigPanelProps) {
  const [label, setLabel] = useState(step.data.label);
  const [waitDays, setWaitDays] = useState(step.data.wait_days);
  const [condition, setCondition] = useState(step.data.condition);

  const save = () => {
    onChange({
      ...step,
      data: { ...step.data, label, wait_days: waitDays, condition },
    });
    onClose();
  };

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-[400px] bg-zinc-950 border-zinc-800 text-zinc-100">
        <DialogHeader>
          <DialogTitle>Configure Step</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label className="text-zinc-300">Label</Label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-zinc-100"
            />
          </div>
          {step.type === "wait" && (
            <div className="space-y-1.5">
              <Label className="text-zinc-300">Wait days</Label>
              <Input
                type="number"
                min={1}
                value={waitDays}
                onChange={(e) => setWaitDays(Number(e.target.value))}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
          )}
          {step.type === "condition" && (
            <div className="space-y-1.5">
              <Label className="text-zinc-300">Condition</Label>
              <Select value={condition} onValueChange={(v) => setCondition(v as typeof condition)}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  <SelectItem value="always">Always</SelectItem>
                  <SelectItem value="no_reply">No reply</SelectItem>
                  <SelectItem value="no_open">No open</SelectItem>
                  <SelectItem value="replied">Replied</SelectItem>
                </SelectContent>
              </Select>
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

type Template = { name: string; description: string; steps: SequenceStep[]; edges: SequenceEdge[] };

function makeStep(id: string, type: SequenceStep["type"], action: SequenceStep["data"]["action"], channel: SequenceStep["data"]["channel"], label: string, waitDays = 0, requires: string[] = [], y = 0): SequenceStep {
  return { id, type, data: { channel, action, label, wait_days: waitDays, condition: "always", requires }, position: { x: 200, y } };
}
function makeEdge(source: string, target: string): SequenceEdge {
  return { id: `e_${source}_${target}`, source, target };
}

const TEMPLATES: Template[] = [
  {
    name: "LinkedIn Only",
    description: "Connect → wait 3d → Follow-up → wait 7d → Follow-up → End",
    steps: [
      makeStep("t1", "action", "connect", "linkedin", "LinkedIn Connect", 0, [], 0),
      makeStep("t2", "wait", null, null, "Wait 3 days", 3, [], 120),
      makeStep("t3", "action", "follow_up", "linkedin", "LinkedIn Follow-up", 0, [], 240),
      makeStep("t4", "wait", null, null, "Wait 7 days", 7, [], 360),
      makeStep("t5", "action", "follow_up", "linkedin", "LinkedIn Follow-up #2", 0, [], 480),
      makeStep("t6", "end", null, null, "End", 0, [], 600),
    ],
    edges: [makeEdge("t1","t2"), makeEdge("t2","t3"), makeEdge("t3","t4"), makeEdge("t4","t5"), makeEdge("t5","t6")],
  },
  {
    name: "LinkedIn + Email",
    description: "Connect → wait 3d → no reply → Email → wait 5d → Follow-up → End",
    steps: [
      makeStep("t1", "action", "connect", "linkedin", "LinkedIn Connect", 0, [], 0),
      makeStep("t2", "wait", null, null, "Wait 3 days", 3, [], 120),
      makeStep("t3", "condition", null, null, "No reply?", 0, [], 240),
      makeStep("t4", "action", "send_email", "email", "Send Email", 0, ["api_email"], 360),
      makeStep("t5", "wait", null, null, "Wait 5 days", 5, [], 480),
      makeStep("t6", "action", "follow_up", "linkedin", "LinkedIn Follow-up", 0, [], 600),
      makeStep("t7", "end", null, null, "End", 0, [], 720),
    ],
    edges: [makeEdge("t1","t2"), makeEdge("t2","t3"), makeEdge("t3","t4"), makeEdge("t4","t5"), makeEdge("t5","t6"), makeEdge("t6","t7")],
  },
  {
    name: "Full Multichannel",
    description: "Connect → Email → WhatsApp → Follow-up → End",
    steps: [
      makeStep("t1", "action", "connect", "linkedin", "LinkedIn Connect", 0, [], 0),
      makeStep("t2", "wait", null, null, "Wait 3 days", 3, [], 120),
      makeStep("t3", "action", "send_email", "email", "Send Email", 0, ["api_email"], 240),
      makeStep("t4", "wait", null, null, "Wait 5 days", 5, [], 360),
      makeStep("t5", "action", "send_whatsapp", "whatsapp", "Send WhatsApp", 0, ["phone"], 480),
      makeStep("t6", "wait", null, null, "Wait 3 days", 3, [], 600),
      makeStep("t7", "action", "follow_up", "linkedin", "LinkedIn Follow-up", 0, [], 720),
      makeStep("t8", "end", null, null, "End", 0, [], 840),
    ],
    edges: [makeEdge("t1","t2"), makeEdge("t2","t3"), makeEdge("t3","t4"), makeEdge("t4","t5"), makeEdge("t5","t6"), makeEdge("t6","t7"), makeEdge("t7","t8")],
  },
];

const ADD_STEP_OPTIONS = [
  { type: "action" as const, action: "connect" as const, channel: "linkedin" as const, label: "LinkedIn Connect", requires: [] as string[] },
  { type: "action" as const, action: "follow_up" as const, channel: "linkedin" as const, label: "LinkedIn Follow-up", requires: [] as string[] },
  { type: "action" as const, action: "send_email" as const, channel: "email" as const, label: "Send Email", requires: ["api_email"] as string[] },
  { type: "action" as const, action: "send_whatsapp" as const, channel: "whatsapp" as const, label: "Send WhatsApp", requires: ["phone"] as string[] },
  { type: "wait" as const, action: null, channel: null, label: "Wait", requires: [] as string[] },
  { type: "condition" as const, action: null, channel: null, label: "Condition", requires: [] as string[] },
  { type: "end" as const, action: null, channel: null, label: "End", requires: [] as string[] },
];

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
  const [showCanvas, setShowCanvas] = useState(false);

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
  }, [campaignId]);

  useEffect(() => { fetchSequence(); }, [fetchSequence]);

  const handleSave = async () => {
    setSaving(true);
    const res = await saveSequence(campaignId, steps, edges);
    setSaving(false);
    if (res.error) {
      toast({ title: "Save failed", description: res.error, variant: "destructive" });
    } else {
      toast({ title: "Sequence saved" });
    }
  };

  const handleToggleActive = async () => {
    if (!active) {
      const confirmed = window.confirm("Activate sequence? The daemon will start executing steps for all active deals in this campaign.");
      if (!confirmed) return;
    }
    setToggling(true);
    const nextActive = !active;
    const res = await setSequenceActive(campaignId, nextActive);
    setToggling(false);
    if (res.error) {
      toast({ title: "Failed to update sequence", description: res.error, variant: "destructive" });
      return;
    }
    setActive(nextActive);
    toast({ title: nextActive ? "Sequence activated" : "Sequence deactivated" });
  };

  const addStep = (opt: typeof ADD_STEP_OPTIONS[number]) => {
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
      position: { x: 200, y: steps.length * 120 + 100 },
    };
    setSteps((prev) => {
      if (prev.length > 0) {
        const prevId = prev[prev.length - 1].id;
        const edgeId = `edge_${prevId}_${id}`;
        setEdges((e) => [...e, { id: edgeId, source: prevId, target: id }]);
      }
      return [...prev, newStep];
    });
    setShowAddMenu(false);
  };

  const deleteStep = (stepId: string) => {
    setSteps((prev) => prev.filter((s) => s.id !== stepId));
    setEdges((prev) => prev.filter((e) => e.source !== stepId && e.target !== stepId));
    if (selectedStepId === stepId) setSelectedStepId(null);
  };

  const updateStep = (updated: SequenceStep) => {
    setSteps((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    setSelectedStepId(null);
  };

  const selectedStep = steps.find((s) => s.id === selectedStepId);

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

  const applyTemplate = (tpl: Template) => {
    setSteps(tpl.steps);
    setEdges(tpl.edges);
    setShowCanvas(true);
  };

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
            Build a multi-step outreach sequence, or start from a template below.
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

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <Card className="border-zinc-800">
        <CardContent className="py-3 px-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-zinc-200">Sequence Builder</span>
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
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
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
                    <button
                      className="w-full text-left px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-800"
                      onClick={() => setShowAddMenu(false)}
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? <Icons.RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Icons.Save className="mr-1.5 h-3.5 w-3.5" />}
                Save
              </Button>
              <Button
                size="sm"
                className={cn(
                  active
                    ? "bg-zinc-700 hover:bg-zinc-600 text-zinc-200"
                    : "bg-blue-600 hover:bg-blue-700",
                )}
                onClick={handleToggleActive}
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

      {/* Steps Canvas — vertical flow */}
      <Card className="border-zinc-800">
        <CardContent className="py-6">
          {steps.length === 0 ? (
            <div className="text-center py-10 text-zinc-500 text-sm">
              No steps yet. Click &ldquo;Add Step&rdquo; to begin.
            </div>
          ) : (
            <div className="flex flex-col items-center gap-0">
              {steps.map((step, idx) => (
                <div key={step.id} className="flex flex-col items-center w-full max-w-sm">
                  <NodeCard
                    step={step}
                    coverage={coverage[step.id] ?? null}
                    selected={selectedStepId === step.id}
                    onSelect={() => setSelectedStepId(step.id === selectedStepId ? null : step.id)}
                    onDelete={() => deleteStep(step.id)}
                  />
                  {idx < steps.length - 1 && (
                    <div className="flex flex-col items-center my-1 text-zinc-700">
                      <ArrowDown className="h-5 w-5" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {selectedStep && (
        <ConfigPanel
          step={selectedStep}
          onChange={updateStep}
          onClose={() => setSelectedStepId(null)}
        />
      )}
    </div>
  );
}
