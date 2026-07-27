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
  profileId?: string;  // LinkedIn profile ID for per-user VNC sessions
}

export function VncViewer({ vncUrl, embedded, profileId }: VncViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showViewer, setShowViewer] = useState(true); // Auto-show when used in modal
  const [error, setError] = useState<string | null>(null);
  const [vncSession, setVncSession] = useState<{ websockify_port: number } | null>(null);
  const [loading, setLoading] = useState(!!profileId);

  // Fetch profile-specific VNC session if profileId provided
  useState(() => {
    if (profileId) {
      import("@/lib/api/dashboard")
        .then((api) => api.getVNCSession(profileId))
        .then((response) => {
          if (response.data) {
            setVncSession(response.data);
            setLoading(false);
          } else {
            setError("Failed to load VNC session for this profile");
            setLoading(false);
          }
        })
        .catch(() => {
          setError("Browser view unavailable. Make sure the desktop app is running.");
          setLoading(false);
        });
    }
  });

  // Build effective URL based on profileId or fallback
  const effectiveUrl = (() => {
    if (vncUrl) return vncUrl;
    if (vncSession) {
      // Use profile-specific websockify port
      const origin = window.location.origin.replace(/:\d+$/, "");
      return `${origin}:${vncSession.websockify_port}`;
    }
    return `${window.location.origin}/vnc`;  // Fallback to shared session
  })();

  if (embedded) {
    if (loading) {
      return (
        <div className="w-full h-full flex items-center justify-center bg-zinc-900 text-zinc-400">
          <div className="flex flex-col items-center gap-2">
            <Icons.Loader className="h-6 w-6 animate-spin" />
            <p className="text-sm">Loading browser view...</p>
          </div>
        </div>
      );
    }
    if (error) {
      return (
        <div className="w-full h-full flex items-center justify-center bg-zinc-900 text-red-400">
          <div className="flex flex-col items-center gap-2">
            <AlertCircle className="h-6 w-6" />
            <p className="text-sm">{error}</p>
          </div>
        </div>
      );
    }
    return (
      <iframe
        src={`${effectiveUrl}/vnc.html?autoconnect=true&resize=remote&reconnect=true`}
        className="w-full h-full border-0"
        title="Live Browser View"
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
      "Unable to load the browser view. Make sure Lengrowth Cloud is running with the browser viewer enabled.",
    );
  };

  if (!showViewer) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5" />
            Live Browser View
          </CardTitle>
          <CardDescription>
            See the live browser when LinkedIn asks for verification or a CAPTCHA
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <Icons.Info className="h-4 w-4" />
            <AlertDescription>
              Use this viewer to complete LinkedIn security challenges directly — no extra tools needed.
            </AlertDescription>
          </Alert>
          <Button onClick={handleOpenViewer} className="w-full">
            <Monitor className="h-4 w-4 mr-2" />
            Open Browser View
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
            <CardTitle>Live Browser View</CardTitle>
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
            src={`${effectiveUrl}/vnc.html?autoconnect=true&resize=remote&reconnect=true`}
            className="w-full h-full border-0"
            title="Live Browser View"
            onError={handleIframeError}
            allow="clipboard-read; clipboard-write"
          />
        </div>
      </CardContent>
    </Card>
  );
}

export default VncViewer;
