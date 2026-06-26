/**
 * Reset Password Page - Supabase Integration
 * 
 * A page for password reset functionality using Supabase.
 */

"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Image from "next/image"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuthStore } from "@/lib/authStore"

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const updatePassword = useAuthStore((state) => state.updatePassword)
  const router = useRouter()
  const searchParams = useSearchParams()

  // Check if user has a session (i.e., they came from email link)
  useEffect(() => {
    const checkAuth = async () => {
      const { session } = useAuthStore.getState()
      if (!session) {
        // Redirect to login if no session
        router.push("/login")
      }
    }
    checkAuth()
  }, [router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    // Validate passwords match
    if (password !== confirmPassword) {
      setError("Passwords do not match")
      setIsLoading(false)
      return
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters")
      setIsLoading(false)
      return
    }

    try {
      const result = await updatePassword(password)

      if (result.error) {
        setError(result.error)
      } else {
        setSuccess(true)
        // Redirect to login after successful password reset
        setTimeout(() => {
          router.push("/login?password-reset=success")
        }, 2000)
      }
    } catch (err) {
      setError("An unexpected error occurred. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  if (success) {
    return (
      <div className="flex items-center justify-center min-h-screen px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-6">
            {/* Logo - Replace src with actual logo path */}
            <div className="flex justify-center items-center py-4">
              <div className="relative h-24 w-64">
                <Image
                  src="/logo.svg"
                  alt="Lengrowth Logo"
                  fill
                  className="object-contain"
                />
              </div>
            </div>
            <div className="text-center space-y-2">
              <CardTitle className="text-2xl text-green-600">Success!</CardTitle>
              <CardDescription className="text-lg">
                Your password has been reset successfully.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-center py-6">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
            <p className="text-center text-lg">Redirecting to login...</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-6">
          {/* Logo - Replace src with actual logo path */}
          <div className="flex justify-center items-center py-4">
            <div className="relative h-24 w-64">
              <Image
                src="/logo.svg"
                alt="Lengrowth Logo"
                fill
                className="object-contain"
              />
            </div>
          </div>
          <div className="text-center space-y-2">
            <CardTitle className="text-3xl">Reset Password</CardTitle>
            <CardDescription className="text-lg">
              Enter a new password for your account
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="text-sm text-red-500 text-center bg-red-500/10 py-3 rounded-lg border border-red-500/20">
                {error}
              </div>
            )}
            <div className="space-y-3">
              <Label htmlFor="password" className="text-base font-medium">New Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter a new password"
                minLength={6}
                required
                className="h-11 px-4"
              />
            </div>
            <div className="space-y-3">
              <Label htmlFor="confirmPassword" className="text-base font-medium">Confirm Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm your new password"
                minLength={6}
                required
                className="h-11 px-4"
              />
            </div>
            <Button type="submit" className="w-full h-11 text-base font-medium" disabled={isLoading}>
              {isLoading ? "Resetting password..." : "Reset Password"}
            </Button>
          </form>
          <div className="mt-6 text-center text-base">
            <a href="/login" className="underline underline-offset-4 hover:text-primary font-medium transition-colors">
              Back to login
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}