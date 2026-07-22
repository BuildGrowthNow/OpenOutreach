"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Linkedin } from "lucide-react";
import { getLinkedInSetupStatus } from "@/lib/api/dashboard";
import { useAuthStore } from "@/lib/authStoreV2";
import LinkedInCredentialForm from "@/components/settings/linkedin-credential-form";

const STORAGE_KEY = "lengrowth_linkedin_setup_prompted";

export function LinkedInSetupModal() {
  const { isAuthenticated } = useAuthStore();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    if (typeof window === "undefined") return;
    if (localStorage.getItem(STORAGE_KEY)) return;

    getLinkedInSetupStatus()
      .then((res) => {
        const complete = res.data?.status?.setupComplete ?? false;
        if (!complete) setOpen(true);
      })
      .catch(() => {
        // Don't block the user on API errors
      });
  }, [isAuthenticated]);

  const handleDismiss = () => {
    localStorage.setItem(STORAGE_KEY, "true");
    setOpen(false);
  };

  const handleSuccess = () => {
    localStorage.setItem(STORAGE_KEY, "true");
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleDismiss(); }}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl">
        <DialogHeader className="border-b border-zinc-800/80 pb-4">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Linkedin className="h-5 w-5 text-[#0A66C2]" />
            Connect your LinkedIn account
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Lengrowth needs your LinkedIn credentials to run outreach campaigns on your behalf.
            Your password is encrypted at rest and never shared.
          </DialogDescription>
        </DialogHeader>

        <LinkedInCredentialForm
          onSuccess={handleSuccess}
          onCancel={handleDismiss}
        />

        <div className="border-t border-zinc-800/60 pt-3 text-center">
          <button
            type="button"
            onClick={handleDismiss}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            I&apos;ll set this up later
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
