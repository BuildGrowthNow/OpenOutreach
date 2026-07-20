"use client"

import { useState, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { CheckCircle2, Loader2 } from "lucide-react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'

function ResetPasswordInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token")

  // Request form state
  const [email, setEmail] = useState("")
  const [requestStatus, setRequestStatus] = useState<"idle" | "loading" | "sent">("idle")
  const [requestError, setRequestError] = useState("")

  // Confirm form state
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [confirmStatus, setConfirmStatus] = useState<"idle" | "loading" | "success">("idle")
  const [confirmError, setConfirmError] = useState("")

  const validatePassword = (pwd: string): string | null => {
    if (pwd.length < 8) return "Password must be at least 8 characters"
    if (!/[A-Z]/.test(pwd)) return "Password must contain at least one uppercase letter"
    if (!/[a-z]/.test(pwd)) return "Password must contain at least one lowercase letter"
    if (!/\d/.test(pwd)) return "Password must contain at least one number"
    return null
  }

  const handleRequestSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setRequestError("")
    if (!email.trim()) {
      setRequestError("Please enter your email address")
      return
    }
    setRequestStatus("loading")
    try {
      await fetch(`${API_BASE}/auth/password-reset/request/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      })
      // Backend always returns success to prevent enumeration
      setRequestStatus("sent")
    } catch {
      setRequestError("Network error. Please try again.")
      setRequestStatus("idle")
    }
  }

  const handleConfirmSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setConfirmError("")

    if (newPassword !== confirmPassword) {
      setConfirmError("Passwords do not match")
      return
    }
    const pwdError = validatePassword(newPassword)
    if (pwdError) {
      setConfirmError(pwdError)
      return
    }

    setConfirmStatus("loading")
    try {
      const response = await fetch(`${API_BASE}/auth/password-reset/confirm/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      })
      const data = await response.json()
      if (!response.ok) {
        setConfirmError(data.detail || "Failed to reset password. The link may have expired.")
        setConfirmStatus("idle")
        return
      }
      setConfirmStatus("success")
      setTimeout(() => router.push("/login?success=password_reset"), 2000)
    } catch {
      setConfirmError("Network error. Please try again.")
      setConfirmStatus("idle")
    }
  }

  // ── Confirm flow (token present) ──────────────────────────────────────────

  if (token) {
    if (confirmStatus === "success") {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
          <Card className="w-full max-w-md">
            <CardContent className="pt-8 text-center space-y-4">
              <CheckCircle2 className="h-12 w-12 text-green-600 mx-auto" />
              <h2 className="text-xl font-semibold">Password updated</h2>
              <p className="text-sm text-gray-600">Redirecting you to login…</p>
            </CardContent>
          </Card>
        </div>
      )
    }

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Set new password</CardTitle>
            <CardDescription>Enter a new password for your account</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleConfirmSubmit} className="space-y-4">
              {confirmError && (
                <Alert variant="destructive">
                  <AlertDescription>{confirmError}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-1">
                <label htmlFor="new-password" className="block text-sm font-medium text-gray-700">
                  New password
                </label>
                <input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                  placeholder="••••••••"
                />
                <p className="text-xs text-gray-500">8+ characters, uppercase, lowercase, number</p>
              </div>
              <div className="space-y-1">
                <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700">
                  Confirm password
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                  placeholder="••••••••"
                />
              </div>
              <Button type="submit" disabled={confirmStatus === "loading"} className="w-full">
                {confirmStatus === "loading" ? (
                  <><Loader2 className="h-4 w-4 animate-spin mr-2" />Updating…</>
                ) : "Update password"}
              </Button>
              <div className="text-center text-sm">
                <Link href="/login" className="text-blue-600 hover:text-blue-500">
                  Back to login
                </Link>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    )
  }

  // ── Request flow (no token) ───────────────────────────────────────────────

  if (requestStatus === "sent") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-8 text-center space-y-4">
            <CheckCircle2 className="h-12 w-12 text-green-600 mx-auto" />
            <h2 className="text-xl font-semibold">Check your email</h2>
            <p className="text-sm text-gray-600">
              If an account exists for <strong>{email}</strong>, a reset link has been sent.
            </p>
            <p className="text-sm text-gray-600">The link expires in 24 hours.</p>
            <div className="pt-2">
              <Link href="/login" className="text-sm font-medium text-blue-600 hover:text-blue-500">
                Back to login
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Reset your password</CardTitle>
          <CardDescription>
            Enter your email and we&apos;ll send a reset link
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRequestSubmit} className="space-y-4">
            {requestError && (
              <Alert variant="destructive">
                <AlertDescription>{requestError}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-1">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                placeholder="you@example.com"
              />
            </div>
            <Button type="submit" disabled={requestStatus === "loading"} className="w-full">
              {requestStatus === "loading" ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" />Sending…</>
              ) : "Send reset link"}
            </Button>
            <div className="text-center text-sm">
              <Link href="/login" className="text-blue-600 hover:text-blue-500">
                Back to login
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    }>
      <ResetPasswordInner />
    </Suspense>
  )
}
