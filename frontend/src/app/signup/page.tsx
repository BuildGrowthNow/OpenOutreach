/**
 * Signup Page - Supabase Integration
 * 
 * A page for new user registration using Supabase.
 */

"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
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
import { getLinkedInSetupStatus } from "@/lib/api/dashboard"

export default function SignupPage() {
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checkingLinkedIn, setCheckingLinkedIn] = useState(false)
  const signup = useAuthStore((state) => state.signup)
  const router = useRouter()
  const searchParams = useSearchParams()
  const callbackUrl = searchParams.get("callbackUrl") || "/dashboard"

  // Check if LinkedIn is configured after signup - this runs after signup completes
  useEffect(() => {
    const shouldCheckLinkedIn = searchParams.get("check-linkedin") === "true"
    
    if (shouldCheckLinkedIn) {
      const checkLinkedInStatus = async () => {
        try {
          setCheckingLinkedIn(true)
          const response = await getLinkedInSetupStatus()
          
          if (response.data && !response.data.status.setup_complete) {
            // LinkedIn is NOT configured - show modal
            sessionStorage.setItem('openoutreach_linkedin_setup_pending', 'true')
            router.push('/settings')
          } else {
            // LinkedIn is configured - go to dashboard
            router.push(callbackUrl)
          }
        } catch (err) {
          console.error('Failed to check LinkedIn status:', err)
          // On error, still go to dashboard (user can set up LinkedIn later)
          router.push(callbackUrl)
        } finally {
          setCheckingLinkedIn(false)
        }
      }
      
      checkLinkedInStatus()
    }
  }, [searchParams, router, callbackUrl])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const result = await signup(email, password, fullName)
      
      if (result.error) {
        setError(result.error)
      } else {
        // Show success message - user needs to verify email
        // After email verification, users will be asked to configure LinkedIn
        router.push(`/login?signup=success&check-linkedin=true`)
      }
    } catch (err) {
      setError("An unexpected error occurred. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-6">
          {/* Logo - Replace src with actual logo path */}
          <div className="flex justify-center items-center py-4">
            <div className="relative h-24 w-64">
              <Image
                src="/logo-white-small.png"
                alt="Lengrowth Logo"
                fill
                className="object-contain"
              />
            </div>
          </div>
          <div className="text-center space-y-2">
            <CardTitle className="text-3xl">Create an Account</CardTitle>
            <CardDescription className="text-lg">
              Enter your information to create a new account
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
              <Label htmlFor="fullName" className="text-base font-medium">Full Name</Label>
              <Input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter your full name"
                required
                className="h-11 px-4"
              />
            </div>
            <div className="space-y-3">
              <Label htmlFor="email" className="text-base font-medium">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                required
                className="h-11 px-4"
              />
            </div>
            <div className="space-y-3">
              <Label htmlFor="password" className="text-base font-medium">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a strong password"
                minLength={6}
                required
                className="h-11 px-4"
              />
              <p className="text-xs text-muted-foreground">
                Password must be at least 6 characters
              </p>
            </div>
            <Button type="submit" className="w-full h-11 text-base font-medium" disabled={isLoading}>
              {isLoading ? "Creating account..." : "Sign up"}
            </Button>
          </form>
          <div className="mt-6 text-center text-base">
            Already have an account?{" "}
            <Link href="/login" className="underline underline-offset-4 hover:text-primary font-medium transition-colors">
              Login
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}