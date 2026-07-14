"use client"

import { useEffect } from "react"
import { useAuthStore } from "@/lib/authStoreV2"

/**
 * Auth Provider - Initializes auth state on mount
 *
 * Wrap your app with this component to initialize authentication.
 */
export function AuthProviderV2({ children }: { children: React.ReactNode }) {
  const initialize = useAuthStore((state) => state.initialize)

  useEffect(() => {
    // Initialize auth state on mount
    initialize()
  }, [initialize])

  return <>{children}</>
}
