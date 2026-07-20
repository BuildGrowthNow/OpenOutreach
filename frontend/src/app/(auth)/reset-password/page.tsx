"use client"

import { useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Logo } from "@/components/ui/logo"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { CheckCircle2, Loader2 } from "lucide-react"

const API_BASE = '/api'

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

  const inputClass = "block w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-foreground placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm"
  const labelClass = "block text-sm font-medium text-zinc-300"
  const linkClass = "text-sm font-medium text-primary hover:text-primary/80"

  // ── Confirm flow (token present) ──────────────────────────────────────────

  if (token) {
    if (confirmStatus === "success") {
      return (
        <div className="dark min-h-screen flex items-center justify-center bg-background px-4">
          <div className="w-full max-w-md p-8 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl text-center space-y-4">
            <div className="flex justify-center">
              <Logo variant="dark" iconSize={40} className="text-lg" />
            </div>
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-500/10 border border-green-500/20">
              <CheckCircle2 className="h-6 w-6 text-green-400" />
            </div>
            <h2 className="text-xl font-semibold text-foreground">Password updated</h2>
            <p className="text-sm text-zinc-400">Redirecting you to login…</p>
          </div>
        </div>
      )
    }

    return (
      <div className="dark min-h-screen flex items-center justify-center bg-background px-4">
        <div className="w-full max-w-md space-y-6 p-8 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl">
          <div className="flex justify-center">
            <Logo variant="dark" iconSize={40} className="text-lg" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-foreground">Set new password</h1>
            <p className="mt-1 text-sm text-zinc-400">Enter a new password for your account</p>
          </div>
          <form onSubmit={handleConfirmSubmit} className="space-y-4">
            {confirmError && (
              <Alert variant="destructive">
                <AlertDescription>{confirmError}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-1">
              <label htmlFor="new-password" className={labelClass}>New password</label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className={inputClass}
                placeholder="••••••••"
              />
              <p className="text-xs text-zinc-500">8+ characters, uppercase, lowercase, number</p>
            </div>
            <div className="space-y-1">
              <label htmlFor="confirm-password" className={labelClass}>Confirm password</label>
              <input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={inputClass}
                placeholder="••••••••"
              />
            </div>
            <Button type="submit" disabled={confirmStatus === "loading"} className="w-full">
              {confirmStatus === "loading" ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" />Updating…</>
              ) : "Update password"}
            </Button>
            <div className="text-center">
              <Link href="/login" className={linkClass}>Back to login</Link>
            </div>
          </form>
        </div>
      </div>
    )
  }

  // ── Request flow (no token) ───────────────────────────────────────────────

  if (requestStatus === "sent") {
    return (
      <div className="dark min-h-screen flex items-center justify-center bg-background px-4">
        <div className="w-full max-w-md p-8 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl text-center space-y-4">
          <div className="flex justify-center">
            <Logo variant="dark" iconSize={40} className="text-lg" />
          </div>
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-500/10 border border-green-500/20">
            <CheckCircle2 className="h-6 w-6 text-green-400" />
          </div>
          <h2 className="text-xl font-semibold text-foreground">Check your email</h2>
          <p className="text-sm text-zinc-400">
            If an account exists for <strong className="text-foreground">{email}</strong>, a reset link has been sent.
          </p>
          <p className="text-sm text-zinc-400">The link expires in 24 hours.</p>
          <div className="pt-2">
            <Link href="/login" className={linkClass}>Back to login</Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="dark min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-6 p-8 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl">
        <div className="flex justify-center">
          <Logo variant="dark" iconSize={40} className="text-lg" />
        </div>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-foreground">Reset your password</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Enter your email and we&apos;ll send a reset link
          </p>
        </div>
        <form onSubmit={handleRequestSubmit} className="space-y-4">
          {requestError && (
            <Alert variant="destructive">
              <AlertDescription>{requestError}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-1">
            <label htmlFor="email" className={labelClass}>Email address</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="you@example.com"
            />
          </div>
          <Button type="submit" disabled={requestStatus === "loading"} className="w-full">
            {requestStatus === "loading" ? (
              <><Loader2 className="h-4 w-4 animate-spin mr-2" />Sending…</>
            ) : "Send reset link"}
          </Button>
          <div className="text-center">
            <Link href="/login" className={linkClass}>Back to login</Link>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="dark min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    }>
      <ResetPasswordInner />
    </Suspense>
  )
}
