/**
 * Login Form - Supabase Integration
 * 
 * A login form that uses email and password authentication via Supabase.
 */

"use client"

import { useState } from "react"
import { useSearchParams, useRouter } from "next/navigation"
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

export function LoginForm() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const login = useAuthStore((state) => state.login)
  const searchParams = useSearchParams()
  const router = useRouter()
  const callbackUrl = searchParams.get("callbackUrl") || "/dashboard"

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const result = await login(email, password)
      
      if (result.error) {
        setError(result.error)
      } else {
        router.push(callbackUrl)
      }
    } catch {
      setError("An unexpected error occurred. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className="mx-auto max-w-sm w-full">
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
          <CardTitle className="text-3xl">Login</CardTitle>
          <CardDescription className="text-lg">
            Enter your email and password to access your account
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
              placeholder="Enter your password"
              required
              className="h-11 px-4"
            />
          </div>
          <Button type="submit" className="w-full h-11 text-base font-medium" disabled={isLoading}>
            {isLoading ? "Logging in..." : "Login"}
          </Button>
        </form>
        <div className="mt-6 text-center text-base space-y-3">
          <p>
            Don't have an account?{" "}
            <Link href="/signup" className="underline underline-offset-4 hover:text-primary font-medium transition-colors">
              Sign up
            </Link>
          </p>
          <p>
            <Link href="/reset-password" className="underline underline-offset-4 hover:text-primary font-medium transition-colors">
              Forgot your password?
            </Link>
          </p>
        </div>
      </CardContent>
    </Card>
  )
}