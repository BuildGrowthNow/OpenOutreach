"use client"

import { RegisterFormV2 } from "@/components/auth/register-form-v2"
import { useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useAuthStore } from "@/lib/authStoreV2"

export default function SignupPageV2() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const intendedPlan = searchParams.get("plan") || undefined
  const inviteToken = searchParams.get("invite_token") || undefined
  const initialEmail = searchParams.get("email") || undefined
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const isLoading = useAuthStore((state) => state.isLoading)

  // Redirect if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      if (inviteToken) {
        router.push(`/team/accept?token=${encodeURIComponent(inviteToken)}`)
        return
      }
      router.push(intendedPlan === "cloud" ? "/settings/plan?plan=cloud" : "/dashboard")
    }
  }, [isAuthenticated, isLoading, intendedPlan, inviteToken, router])

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
      <RegisterFormV2
        intendedPlan={intendedPlan}
        inviteToken={inviteToken}
        initialEmail={initialEmail}
      />
    </div>
  )
}
