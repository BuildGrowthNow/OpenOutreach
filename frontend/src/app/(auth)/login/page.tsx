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
  const token = useAuthStore((state) => state.token)

  // Handle desktop app callback
  useEffect(() => {
    if (!isLoading && isAuthenticated && token) {
      const isDesktop = searchParams.get("desktop") === "true"
      const callback = searchParams.get("callback")

      if (isDesktop && callback) {
        // Desktop app login - redirect back with token
        // Profile ID will be fetched by desktop app using the token
        window.location.href = `${callback}?token=${token}`
        return
      }
    }
  }, [isAuthenticated, isLoading, token, searchParams])

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
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (isAuthenticated) {
    return null // Will redirect
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <LoginFormV2 />
    </div>
  )
}
