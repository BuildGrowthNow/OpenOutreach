"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Download, Cloud, Lock, Sparkles, Info } from "lucide-react";

interface ExecutionModeChoiceModalProps {
  open: boolean;
  onClose: () => void;
  onSelectDesktop: () => void;
  onSelectCloud: () => void;
  canUseCloud: boolean;
  isTrialing: boolean;
  upgradeUrl?: string;
}

export function ExecutionModeChoiceModal({
  open,
  onClose,
  onSelectDesktop,
  onSelectCloud,
  canUseCloud,
  isTrialing,
  upgradeUrl = "/settings/billing",
}: ExecutionModeChoiceModalProps) {
  const [selectedMode, setSelectedMode] = useState<"desktop" | "cloud">("desktop");

  const handleContinue = () => {
    if (selectedMode === "desktop") {
      onSelectDesktop();
    } else if (selectedMode === "cloud") {
      if (canUseCloud) {
        onSelectCloud();
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            How do you want to run automation?
          </DialogTitle>
          <DialogDescription>
            Choose where your LinkedIn automation will execute
          </DialogDescription>
        </DialogHeader>

        <RadioGroup value={selectedMode} onValueChange={(v) => setSelectedMode(v as "desktop" | "cloud")} className="space-y-4">
          {/* Desktop Option - Always Available */}
          <div
            className={`relative border-2 rounded-lg p-4 cursor-pointer transition-all ${
              selectedMode === "desktop"
                ? "border-primary bg-primary/5"
                : "border-muted hover:border-muted-foreground/50"
            }`}
            onClick={() => setSelectedMode("desktop")}
          >
            <div className="flex items-start space-x-3">
              <RadioGroupItem value="desktop" id="desktop" className="mt-1" />
              <div className="flex-1 space-y-2">
                <Label htmlFor="desktop" className="text-lg font-semibold cursor-pointer flex items-center gap-2">
                  <Download className="h-5 w-5 text-blue-600" />
                  Desktop App
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/20 dark:text-amber-300 rounded-full">
                    <Sparkles className="h-3 w-3" />
                    Recommended
                  </span>
                </Label>
                <ul className="space-y-1.5 text-sm text-muted-foreground">
                  <li className="flex items-center gap-2">
                    <span className="text-green-600">✓</span>
                    <span><strong>Free</strong> - no additional cost</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-green-600">✓</span>
                    <span>Uses your <strong>residential IP</strong></span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-green-600">✓</span>
                    <span>Runs on your computer</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Cloud Option - May be Locked */}
          <div
            className={`relative border-2 rounded-lg p-4 transition-all ${
              !canUseCloud ? "opacity-60 cursor-not-allowed" : "cursor-pointer"
            } ${
              selectedMode === "cloud" && canUseCloud
                ? "border-primary bg-primary/5"
                : "border-muted hover:border-muted-foreground/50"
            }`}
            onClick={() => canUseCloud && setSelectedMode("cloud")}
          >
            {!canUseCloud && (
              <div className="absolute top-3 right-3">
                <Lock className="h-5 w-5 text-muted-foreground" />
              </div>
            )}
            <div className="flex items-start space-x-3">
              <RadioGroupItem
                value="cloud"
                id="cloud"
                disabled={!canUseCloud}
                className="mt-1"
              />
              <div className="flex-1 space-y-2">
                <Label
                  htmlFor="cloud"
                  className={`text-lg font-semibold flex items-center gap-2 ${
                    !canUseCloud ? "cursor-not-allowed" : "cursor-pointer"
                  }`}
                >
                  <Cloud className="h-5 w-5 text-green-600" />
                  Cloud Execution
                  {!canUseCloud && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-400 rounded-full">
                      <Lock className="h-3 w-3" />
                      Upgrade Required
                    </span>
                  )}
                </Label>
                <ul className="space-y-1.5 text-sm text-muted-foreground">
                  <li className="flex items-center gap-2">
                    <span className="text-blue-600">•</span>
                    <span><strong>$39/month</strong> per LinkedIn account</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-blue-600">•</span>
                    <span>Runs <strong>24/7</strong> on our servers</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-blue-600">•</span>
                    <span>No computer needed</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </RadioGroup>

        {/* Trial User Warning */}
        {isTrialing && (
          <Alert className="bg-amber-50 border-amber-200 dark:bg-amber-900/10 dark:border-amber-900">
            <Info className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-sm text-amber-800 dark:text-amber-300">
              Cloud execution is not available during trial. Please use the desktop app,
              or upgrade to a paid plan to unlock cloud execution.
            </AlertDescription>
          </Alert>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <div className="flex items-center gap-2">
            {selectedMode === "cloud" && !canUseCloud && (
              <Button onClick={() => window.location.href = upgradeUrl}>
                Upgrade to Cloud Add-on
              </Button>
            )}
            {(selectedMode === "desktop" || canUseCloud) && (
              <Button onClick={handleContinue}>
                Continue
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
