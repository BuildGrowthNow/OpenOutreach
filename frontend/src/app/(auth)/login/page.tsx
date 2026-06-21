"use client"

import { LoginForm } from "@/components/auth/login-form"
import { useAuthStore } from "@/lib/authStore"
import { useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const session = useAuthStore((state) => state.session)
  const isAuthenticated = !!session

  const message = (() => {
    const signupSuccess = searchParams.get("signup")
    const error = searchParams.get("error")
    const success = searchParams.get("success")
    const passwordReset = searchParams.get("password-reset")

    if (signupSuccess === "success") {
      return "Account created! Please check your email for verification."
    }
    if (error === "verification_failed") {
      return "Email verification failed. Please try again."
    }
    if (success === "email_verified") {
      return "Email verified successfully! You can now login."
    }
    if (passwordReset === "success") {
      return "Password reset successful! You can now login with your new password."
    }
    return null
  })()

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/dashboard")
    }
  }, [isAuthenticated, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      {message && (
        <div className="fixed top-4 right-4 bg-green-500 text-white px-4 py-2 rounded shadow-lg">
          {message}
        </div>
      )}
      <LoginForm />
    </div>
  )
}
