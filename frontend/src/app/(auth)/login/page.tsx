"use client"

import { LoginFormV2 } from "@/components/auth/login-form-v2"
import { useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useAuthStore } from "@/lib/authStoreV2"

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const isLoading = useAuthStore((state) => state.isLoading)
  const accessToken = useAuthStore((state) => state.accessToken)
  const refreshToken = useAuthStore((state) => state.refreshTokenValue)

  // Handle desktop app callback
  useEffect(() => {
    if (!isLoading && isAuthenticated && accessToken) {
      const isDesktop = searchParams.get("desktop") === "true"
      const callback = searchParams.get("callback")

      if (isDesktop && callback) {
        // Call pywebview API directly if available (avoids OS protocol launch)
        const pywebview = (window as unknown as Record<string, unknown>).pywebview as
          { api?: {
            store_auth_tokens?: (access: string, refresh?: string | null) => void
            handle_lengrowth_url?: (u: string) => void
          } } | undefined
        if (pywebview?.api?.store_auth_tokens) {
          pywebview.api.store_auth_tokens(accessToken, refreshToken)
        } else if (pywebview?.api?.handle_lengrowth_url) {
          // Compatibility with older desktop builds. Never include the
          // refresh token in the OS protocol URL.
          pywebview.api.handle_lengrowth_url(`${callback}?token=${encodeURIComponent(accessToken)}`)
        } else {
          window.location.href = `${callback}?token=${encodeURIComponent(accessToken)}`
        }
        return
      }
    }
  }, [isAuthenticated, isLoading, accessToken, refreshToken, searchParams])

  // Redirect if already authenticated (non-desktop)
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      const isDesktop = searchParams.get("desktop") === "true"
      if (!isDesktop) {
        const returnUrl = searchParams.get("returnUrl") || "/dashboard"
        router.push(returnUrl)
      }
    }
  }, [isAuthenticated, isLoading, router, searchParams])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (isAuthenticated) {
    return null // Will redirect
  }

  return (
    <div className="dark min-h-screen flex items-center justify-center bg-background px-4">
      <LoginFormV2 />
    </div>
  )
}
