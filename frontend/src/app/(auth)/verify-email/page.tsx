"use client"

import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
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
          headers: {
            "Content-Type": "application/json",
          },
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
      // Backend always returns 200 to prevent enumeration — treat as success
      setResendStatus("sent")
    } catch {
      setResendStatus("error")
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Email Verification</CardTitle>
          <CardDescription>
            Verifying your email address
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status === "loading" && (
            <div className="text-center py-8">
              <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-600 mb-4" />
              <p className="text-gray-600">Verifying your email...</p>
            </div>
          )}

          {status === "success" && (
            <Alert className="bg-green-50 border-green-200">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <AlertDescription className="text-green-800 ml-2">
                {message}
              </AlertDescription>
            </Alert>
          )}

          {status === "error" && (
            <>
              <Alert className="bg-red-50 border-red-200">
                <XCircle className="h-5 w-5 text-red-600" />
                <AlertDescription className="text-red-800 ml-2">
                  {message}
                </AlertDescription>
              </Alert>

              <div className="space-y-3 pt-2">
                <p className="text-sm text-gray-600 text-center">
                  Didn&apos;t receive the email or link expired?
                </p>
                <div className="flex gap-2">
                  <input
                    type="email"
                    value={resendEmail}
                    onChange={(e) => setResendEmail(e.target.value)}
                    placeholder="Your email address"
                    className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  <p className="text-xs text-green-700 text-center">
                    If an unverified account exists for that email, a new link has been sent.
                  </p>
                )}
                {resendStatus === "error" && (
                  <p className="text-xs text-red-600 text-center">
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
        </CardContent>
      </Card>
    </div>
  )
}
