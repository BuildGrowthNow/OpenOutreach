"use client"

import { RegisterFormV2 } from "@/components/auth/register-form-v2"
import { useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useAuthStore } from "@/lib/authStoreV2"

export default function SignupPageV2() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const intendedPlan = searchParams.get("plan") || undefined
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const isLoading = useAuthStore((state) => state.isLoading)

  // Redirect if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push(intendedPlan === "cloud" ? "/settings/plan?plan=cloud" : "/dashboard")
    }
  }, [isAuthenticated, isLoading, intendedPlan, router])

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
      <RegisterFormV2 intendedPlan={intendedPlan} />
    </div>
  )
}
