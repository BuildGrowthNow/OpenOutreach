"use client";

import { useCallback } from "react";
import { useToast } from "@/components/ui/use-toast";
import { ToastAction } from "@/components/ui/toast";
import type { ToastActionElement } from "@/components/ui/toast";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import React from "react";

/**
 * Returns a handler that inspects an error and, if it's a 402 (plan limit),
 * shows an actionable toast with an "Upgrade" button instead of a generic error.
 *
 * Usage:
 *   const handleUpgradeError = useUpgradeToast();
 *   try { ... } catch (err) { if (!handleUpgradeError(err)) setError(String(err)); }
 *
 * Returns true if the error was a 402 (handled), false otherwise.
 */
export function useUpgradeToast(): (err: unknown) => boolean {
  const { toast } = useToast();
  const router = useRouter();

  return useCallback(
    (err: unknown): boolean => {
      if (err instanceof ApiError && err.status === 402) {
        const action = React.createElement(
          ToastAction,
          { altText: "Upgrade", onClick: () => router.push("/settings/plan") },
          "Upgrade",
        ) as unknown as ToastActionElement;

        toast({
          title: "Plan limit reached",
          description: err.message || "Upgrade your plan to continue.",
          action,
        });
        return true;
      }
      return false;
    },
    [toast, router],
  );
}
