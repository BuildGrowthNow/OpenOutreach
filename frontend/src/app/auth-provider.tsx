/**
 * Authentication Provider - Supabase Integration
 * 
 * This provider manages authentication state using Supabase as the canonical identity provider.
 * It handles:
 * - Session initialization on app load
 * - Route protection and redirects
 * - Periodic token refresh
 */

"use client"

import { createContext, useContext, useEffect, Suspense } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useAuthStore } from "@/lib/authStore"
import type { User } from "@supabase/supabase-js"

interface AuthContextType {
  isAuthenticated: boolean
  isLoading: boolean
  user: User | null
  login: (email: string, password: string) => Promise<{ error: string | null }>
  logout: () => Promise<void>
  signup: (email: string, password: string, fullName: string) => Promise<{ error: string | null; user?: User }>
  resetPassword: (email: string) => Promise<{ error: string | null }>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const AuthProviderImpl = ({ children }: { children: React.ReactNode }) => {
  const { 
    isLoading, 
    user, 
    initialize: initializeAuth,
    logout: storeLogout,
  } = useAuthStore()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const callbackUrl = searchParams.get("callbackUrl") || "/dashboard"

  // Initialize auth state on component mount
  useEffect(() => {
    initializeAuth()
  }, [initializeAuth])

  // Redirect to login if not authenticated (but allow auth pages to pass through)
  useEffect(() => {
    // If auth is still loading, don't redirect yet
    if (isLoading) return
    
    // Public pages that don't require authentication (landing page, auth pages)
    const publicPages = ["/"]
    const authPages = ["/login", "/signup", "/reset-password", "/verify-email"]
    const isPublicPage = publicPages.some(page => pathname === page)
    const isAuthPage = authPages.some(page => pathname.startsWith(page))
    
    // If not authenticated and not on a public or auth page, redirect to login
    if (!user && !isAuthPage && !isPublicPage) {
      // Preserve current path for callback after login
      const redirectUrl = `${pathname}${searchParams.toString() ? `?${searchParams}` : ""}`
      router.push(`/login?callbackUrl=${encodeURIComponent(redirectUrl)}`)
    }
    
    // If authenticated and on an auth page (except reset-password which needs a token), redirect to dashboard
    if (user && isAuthPage && pathname !== "/reset-password") {
      router.push(callbackUrl)
    }
  }, [user, isLoading, pathname, searchParams, router, callbackUrl])

  // Check for email verification token in URL (Sent from Supabase)
  useEffect(() => {
    const type = searchParams.get("type")
    const token = searchParams.get("token")
    
    if (type === "email" && token) {
      // Handle email verification
      useAuthStore.getState().verifyEmail(token).then(({ error }) => {
        if (error) {
          console.error("Email verification failed:", error)
          router.push(`/login?error=verification_failed`)
        } else {
          router.push(`/login?success=email_verified`)
        }
      })
    }
  }, [searchParams, router])

  const login = async (email: string, password: string) => {
    try {
      const result = await useAuthStore.getState().login(email, password)
      if (result.error) {
        return result
      }
      // Redirect to callback URL after successful login
      router.push(callbackUrl)
      return { error: null }
    } catch (error) {
      console.error("Login error:", error)
      return { error: "An unexpected error occurred" }
    }
  }

  const logout = async () => {
    try {
      await storeLogout()
      router.push("/login")
    } catch (error) {
      console.error("Logout error:", error)
      router.push("/login")
    }
  }

  const signup = async (email: string, password: string, fullName: string) => {
    try {
      return await useAuthStore.getState().signup(email, password, fullName)
    } catch (error) {
      console.error("Signup error:", error)
      return { error: "An unexpected error occurred" }
    }
  }

  const resetPassword = async (email: string) => {
    try {
      return await useAuthStore.getState().resetPassword(email)
    } catch (error) {
      console.error("Reset password error:", error)
      return { error: "An unexpected error occurred" }
    }
  }

  // For public pages (landing page), render immediately without waiting for auth
  const publicPages = ["/"]
  const authPages = ["/login", "/signup", "/reset-password", "/verify-email"]
  const isPublicPage = publicPages.some(page => pathname === page)
  const isAuthPage = authPages.some(page => pathname.startsWith(page))

  // Don't render children until auth state is loaded (except for public/auth pages)
  if (isLoading && !isPublicPage && !isAuthPage) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-sm text-muted-foreground">Loading authentication...</p>
        </div>
      </div>
    )
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!user, isLoading, user, login, logout, signup, resetPassword }}>
      {children}
    </AuthContext.Provider>
  )
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div></div>}>
      <AuthProviderImpl>{children}</AuthProviderImpl>
    </Suspense>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
