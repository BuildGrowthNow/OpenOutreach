"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Download, Apple, Monitor, CheckCircle2, ExternalLink } from "lucide-react";

interface DesktopDownloadInstructionsProps {
  open: boolean;
  onClose: () => void;
}

export function DesktopDownloadInstructions({
  open,
  onClose,
}: DesktopDownloadInstructionsProps) {
  const [platform, setPlatform] = useState<"windows" | "mac" | "unknown">("unknown");

  useEffect(() => {
    // Detect platform
    const userAgent = window.navigator.userAgent.toLowerCase();
    if (userAgent.includes("mac")) {
      setPlatform("mac");
    } else if (userAgent.includes("win")) {
      setPlatform("windows");
    }
  }, []);

  const downloadUrls = {
    windows: "https://github.com/BuildGrowthNow/OpenOutreach/releases/latest/download/OpenOutreach-Setup.exe",
    mac: "https://github.com/BuildGrowthNow/OpenOutreach/releases/latest/download/OpenOutreach.dmg",
  };

  const handleDownload = () => {
    if (platform !== "unknown") {
      window.open(downloadUrls[platform], "_blank");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold flex items-center gap-2">
            <Download className="h-6 w-6 text-primary" />
            Download Desktop App
          </DialogTitle>
          <DialogDescription>
            Follow these steps to set up LinkedIn automation on your computer
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Download Button */}
          <div className="flex flex-col items-center gap-4 p-6 bg-muted/50 rounded-lg border-2 border-dashed">
            <div className="flex items-center gap-3 text-muted-foreground">
              {platform === "mac" && <Apple className="h-8 w-8" />}
              {platform === "windows" && <Monitor className="h-8 w-8" />}
              {platform === "unknown" && <Download className="h-8 w-8" />}
              <span className="text-sm font-medium">
                {platform === "mac" && "macOS"}
                {platform === "windows" && "Windows"}
                {platform === "unknown" && "Desktop App"}
              </span>
            </div>
            <Button size="lg" onClick={handleDownload} disabled={platform === "unknown"}>
              <Download className="mr-2 h-5 w-5" />
              Download for {platform === "mac" ? "macOS" : platform === "windows" ? "Windows" : "Desktop"}
            </Button>
            {platform === "unknown" && (
              <p className="text-xs text-muted-foreground text-center">
                Unable to detect your operating system. Please visit our{" "}
                <a
                  href="https://github.com/BuildGrowthNow/OpenOutreach/releases/latest"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  releases page
                </a>{" "}
                to download manually.
              </p>
            )}
          </div>

          {/* Instructions */}
          <div className="space-y-4">
            <h4 className="font-semibold text-sm">Installation Steps:</h4>
            <ol className="space-y-3 text-sm">
              <li className="flex gap-3">
                <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary font-semibold text-xs">
                  1
                </span>
                <div className="flex-1">
                  <p className="font-medium">Download and install the app</p>
                  <p className="text-muted-foreground">
                    {platform === "mac" && "Open the DMG file and drag OpenOutreach to Applications"}
                    {platform === "windows" && "Run the installer and follow the setup wizard"}
                    {platform === "unknown" && "Run the installer for your operating system"}
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary font-semibold text-xs">
                  2
                </span>
                <div className="flex-1">
                  <p className="font-medium">Sign in with this account</p>
                  <p className="text-muted-foreground">
                    Use the same email and password you use for OpenOutreach web app
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary font-semibold text-xs">
                  3
                </span>
                <div className="flex-1">
                  <p className="font-medium">Add your LinkedIn credentials</p>
                  <p className="text-muted-foreground">
                    The desktop app will prompt you for your LinkedIn email and password
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary font-semibold text-xs">
                  4
                </span>
                <div className="flex-1">
                  <p className="font-medium">Credential appears automatically here</p>
                  <p className="text-muted-foreground">
                    After successful login, your credential will show up in this list with a Desktop badge
                  </p>
                </div>
              </li>
            </ol>
          </div>

          {/* Info Alert */}
          <Alert>
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-sm">
              <strong>Completely free!</strong> Desktop execution uses your own computer and
              residential IP - no additional monthly fees or proxy costs.
            </AlertDescription>
          </Alert>

          {/* Alternate Downloads */}
          <div className="pt-4 border-t">
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground flex items-center gap-2">
                <ExternalLink className="h-4 w-4" />
                Need a different version or having trouble?
              </summary>
              <div className="mt-3 space-y-2 pl-6">
                <p>
                  <a
                    href="https://github.com/BuildGrowthNow/OpenOutreach/releases/latest"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    View all releases on GitHub →
                  </a>
                </p>
                <p className="text-muted-foreground text-xs">
                  Includes standalone executables, installers, and platform-specific builds
                </p>
              </div>
            </details>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end pt-4">
          <Button onClick={onClose}>Done</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
