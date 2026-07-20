"use client"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useAuthStore } from "@/lib/authStoreV2"
import { Logo } from "@/components/ui/logo"

export function LoginFormV2() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login, isLoading, error, clearError } = useAuthStore()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [localError, setLocalError] = useState("")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError("")
    clearError()

    // Basic validation
    if (!email || !password) {
      setLocalError("Please enter both email and password")
      return
    }

    // Attempt login
    const result = await login(email, password)

    if (result.error) {
      setLocalError(result.error)
    } else {
      const returnUrl = searchParams.get("returnUrl") || "/dashboard"
      router.push(returnUrl)
    }
  }

  const displayError = localError || error
  const isUnverifiedError = displayError?.toLowerCase().includes("verify your email")

  return (
    <div className="w-full max-w-md space-y-8 p-8 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl">
      <div className="flex flex-col items-center gap-4">
        <Logo variant="dark" iconSize={40} className="text-lg" />
        <div className="text-center">
          <h1 className="text-2xl font-bold text-foreground">Welcome Back</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Sign in to your Lengrowth account
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        {displayError && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded text-sm">
            <p>{displayError}</p>
            {isUnverifiedError && (
              <p className="mt-2">
                <a
                  href={`/verify-email?email=${encodeURIComponent(email)}`}
                  className="underline font-medium hover:text-red-300"
                >
                  Resend verification email
                </a>
              </p>
            )}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-zinc-300">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-foreground placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-zinc-300">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-foreground placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
              placeholder="••••••••"
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="text-sm">
            <Link
              href="/reset-password"
              className="font-medium text-primary hover:text-primary/80"
            >
              Forgot your password?
            </Link>
          </div>
        </div>

        <div>
          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary focus:ring-offset-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? "Signing in..." : "Sign in"}
          </button>
        </div>

        <div className="text-center text-sm">
          <span className="text-zinc-500">Don't have an account? </span>
          <Link
            href="/signup"
            className="font-medium text-primary hover:text-primary/80"
          >
            Sign up
          </Link>
        </div>
      </form>
    </div>
  )
}
