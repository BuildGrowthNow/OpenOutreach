"use client"

import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Logo } from "@/components/ui/logo"
import { CheckCircle2, XCircle, Loader2, Mail } from "lucide-react"

const API_BASE = '/api'

export default function VerifyEmailPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token")
  const emailParam = searchParams.get("email") || ""

  const [status, setStatus] = useState<"loading" | "success" | "error">("loading")
  const [message, setMessage] = useState("")
  const [resendEmail, setResendEmail] = useState(emailParam)
  const [resendStatus, setResendStatus] = useState<"idle" | "sending" | "sent" | "error">("idle")

  useEffect(() => {
    if (!token) {
      setStatus("error")
      setMessage("Invalid verification link. Please check your email for the correct link.")
      return
    }

    const verifyEmail = async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/verify-email/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        })

        const data = await response.json()

        if (response.ok) {
          setStatus("success")
          setMessage(data.message || "Email verified successfully!")
          setTimeout(() => {
            router.push("/login?returnUrl=" + encodeURIComponent("/download?welcome=1&success=email_verified"))
          }, 2000)
        } else {
          setStatus("error")
          setMessage(data.detail || "Verification failed. The link may have expired.")
        }
      } catch (error) {
        console.error("Verification error:", error)
        setStatus("error")
        setMessage("Network error. Please try again.")
      }
    }

    verifyEmail()
  }, [token, router])

  const handleResend = async () => {
    if (!resendEmail.trim()) return
    setResendStatus("sending")
    try {
      const url = `${API_BASE}/auth/resend-verification/?email=${encodeURIComponent(resendEmail.trim())}`
      await fetch(url, { method: "POST" })
      setResendStatus("sent")
    } catch {
      setResendStatus("error")
    }
  }

  return (
    <div className="dark min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-6 p-8 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl">
        <div className="flex justify-center">
          <Logo variant="dark" iconSize={40} className="text-lg" />
        </div>

        <div className="text-center">
          <h1 className="text-2xl font-bold text-foreground">Email Verification</h1>
          <p className="mt-1 text-sm text-zinc-400">Verifying your email address</p>
        </div>

        <div className="space-y-4">
          {status === "loading" && (
            <div className="text-center py-8">
              <Loader2 className="h-12 w-12 animate-spin mx-auto text-primary mb-4" />
              <p className="text-zinc-400">Verifying your email...</p>
            </div>
          )}

          {status === "success" && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-md p-4 flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-green-400 shrink-0 mt-0.5" />
              <p className="text-green-400 text-sm">{message}</p>
            </div>
          )}

          {status === "error" && (
            <>
              <div className="bg-red-500/10 border border-red-500/20 rounded-md p-4 flex items-start gap-3">
                <XCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
                <p className="text-red-400 text-sm">{message}</p>
              </div>

              <div className="space-y-3 pt-2">
                <p className="text-sm text-zinc-400 text-center">
                  Didn&apos;t receive the email or link expired?
                </p>
                <div className="flex gap-2">
                  <input
                    type="email"
                    value={resendEmail}
                    onChange={(e) => setResendEmail(e.target.value)}
                    placeholder="Your email address"
                    className="flex-1 rounded-md bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-foreground placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
                  />
                  <Button
                    onClick={handleResend}
                    disabled={resendStatus === "sending" || resendStatus === "sent" || !resendEmail.trim()}
                    size="sm"
                    className="shrink-0"
                  >
                    {resendStatus === "sending" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Mail className="h-4 w-4" />
                    )}
                    <span className="ml-1">
                      {resendStatus === "sent" ? "Sent!" : "Resend"}
                    </span>
                  </Button>
                </div>
                {resendStatus === "sent" && (
                  <p className="text-xs text-green-400 text-center">
                    If an unverified account exists for that email, a new link has been sent.
                  </p>
                )}
                {resendStatus === "error" && (
                  <p className="text-xs text-red-400 text-center">
                    Failed to send. Please try again.
                  </p>
                )}
                <Button
                  onClick={() => router.push("/login")}
                  className="w-full"
                  variant="outline"
                >
                  Back to Login
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
