"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Icons } from "@/lib/types/components";
import { Monitor, Maximize2, Minimize2, AlertCircle } from "lucide-react";

interface VncViewerProps {
  vncUrl?: string;
  embedded?: boolean;
}

export function VncViewer({ vncUrl, embedded }: VncViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showViewer, setShowViewer] = useState(true); // Auto-show when used in modal
  const [error, setError] = useState<string | null>(null);

  // Proxy VNC through the same HTTPS origin via /vnc/ nginx location
  const effectiveUrl = vncUrl || `${window.location.origin}/vnc`;

  if (embedded) {
    return (
      <iframe
        src={`${effectiveUrl}/vnc.html?autoconnect=true&resize=scale`}
        className="w-full h-full border-0"
        title="VNC Browser Session"
        allow="clipboard-read; clipboard-write"
      />
    );
  }

  const handleOpenViewer = () => {
    setShowViewer(true);
    setError(null);
  };

  const handleCloseViewer = () => {
    setShowViewer(false);
    setIsExpanded(false);
  };

  const handleIframeError = () => {
    setError(
      "Failed to load VNC viewer. Make sure the container is running with ENABLE_VNC=true and port 6080 is accessible.",
    );
  };

  if (!showViewer) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5" />
            Browser Session Viewer
          </CardTitle>
          <CardDescription>
            Access the live browser session when LinkedIn requires manual
            verification or CAPTCHA solving
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <Icons.Info className="h-4 w-4" />
            <AlertDescription>
              The browser session runs inside the Docker container. Use this
              viewer to interact with LinkedIn challenges, CAPTCHAs, or security
              verifications without SSH/VNC client.
            </AlertDescription>
          </Alert>
          <Button onClick={handleOpenViewer} className="w-full">
            <Monitor className="h-4 w-4 mr-2" />
            Open Browser Viewer
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className={`transition-all ${isExpanded ? "fixed inset-4 z-50" : ""}`}
    >
      <CardHeader className="border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Monitor className="h-5 w-5" />
            <CardTitle>Live Browser Session</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? (
                <Minimize2 className="h-4 w-4" />
              ) : (
                <Maximize2 className="h-4 w-4" />
              )}
            </Button>
            <Button variant="ghost" size="sm" onClick={handleCloseViewer}>
              <Icons.X className="h-4 w-4" />
            </Button>
          </div>
        </div>
        {error && (
          <Alert variant="destructive" className="mt-2">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </CardHeader>
      <CardContent className="p-0">
        <div
          className={`relative bg-black ${isExpanded ? "h-[calc(100vh-8rem)]" : "h-[600px]"}`}
        >
          <iframe
            src={`${effectiveUrl}/vnc.html?autoconnect=true&resize=scale`}
            className="w-full h-full border-0"
            title="VNC Browser Session"
            onError={handleIframeError}
            allow="clipboard-read; clipboard-write"
          />
        </div>
      </CardContent>
    </Card>
  );
}

export default VncViewer;
