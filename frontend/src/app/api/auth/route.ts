/**
 * Supabase Integration Auth API Routes
 * 
 * This API route handles authentication operations by proxying to Supabase.
 * It verifies Supabase JWT tokens on each request and creates/links Django users as needed.
 */

import { NextRequest, NextResponse } from "next/server"
import { supabase } from "@/lib/supabase/client"
import { cookies } from "next/headers"
import type { User } from "@supabase/supabase-js"
import { verifySession } from "./utils/verify-session"

/**
 * GET /api/auth - Check authentication status
 * Verifies Supabase session and Django user link
 */
export async function GET(request: NextRequest) {
  try {
    const { session, user } = await verifySession(request)
    
    if (!session || !user) {
      return NextResponse.json({ 
        authenticated: false,
        user: null,
      }, { status: 200 })
    }
    
    // Get Django user info if linked
    const djangoUser = await getLinkedDjangoUser(user.id)
    
    return NextResponse.json({ 
      authenticated: true,
      user: {
        id: user.id,
        email: user.email,
        full_name: user.user_metadata?.full_name,
        ...djangoUser,
      },
    }, { status: 200 })
  } catch (error) {
    console.error("Auth status error:", error)
    return NextResponse.json({ 
      authenticated: false,
      error: "Internal server error",
    }, { status: 500 })
  }
}

/**
 * POST /api/auth - Login with email and password
 * Uses Supabase for authentication
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { email, password } = body

    if (!email || !password) {
      return NextResponse.json(
        { error: "Email and password are required" },
        { status: 400 },
      )
    }

    // Authenticate with Supabase
    const { data: authData, error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    if (authError || !authData.session || !authData.user) {
      return NextResponse.json(
        { error: authError?.message || "Invalid credentials" },
        { status: 401 },
      )
    }

    const { session, user } = authData

    // Check if user's email is verified
    if (!user.email_confirmed_at) {
      return NextResponse.json(
        { error: "Please verify your email before logging in" },
        { status: 403 },
      )
    }

    // Link or create Django user
    const djangoUser = await linkOrCreateDjangoUser(user, session.access_token)

    // Create session cookie for Django backend
    const cookieStore = await cookies()
    cookieStore.set("openoutreach_session", "authenticated", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      maxAge: 60 * 60 * 24 * 7, // 1 week
      path: "/",
    })

    return NextResponse.json({ 
      success: true,
      user: {
        id: user.id,
        email: user.email,
        full_name: user.user_metadata?.full_name,
        ...djangoUser,
      },
    }, { status: 200 })
  } catch (error) {
    console.error("Auth error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

/**
 * DELETE /api/auth - Logout
 * Sign out from Supabase and clear Django session
 */
export async function DELETE(request: NextRequest) {
  try {
    const { session } = await verifySession(request)

    if (session) {
      // Sign out from Supabase
      await supabase.auth.signOut()
      
      // Clear Django session cookie
      const cookieStore = await cookies()
      cookieStore.delete("openoutreach_session")
    }
    
    return NextResponse.json({ success: true }, { status: 200 })
  } catch (error) {
    console.error("Logout error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

/**
 * POST /api/auth/verify-email - Verify email token
 * Handles email verification after signup
 */
export async function POST_VERIFY_EMAIL(request: NextRequest) {
  try {
    const { token, type, email } = await request.json()

    if (!token || !type) {
      return NextResponse.json(
        { error: "Token and type are required" },
        { status: 400 },
      )
    }

    // Build OTP options based on type
    let options: { token: string; type: "email" | "signup" | "email_link" | "phone" | "sms" | "invite" | "magiclink" | "recovery" | "signup" | "email_change" | "phone_change" } & { email?: string }
    
    if (type === 'email' || type === 'signup') {
      // email verification requires email parameter
      if (!email) {
        return NextResponse.json(
          { error: "Email is required for this verification type" },
          { status: 400 },
        )
      }
      options = { token, type, email: email! }
    } else {
      // other OTP types don't require email
      options = { token, type }
    }

    // Verify the token with Supabase
    // We need to use type assertion here because Supabase's VerifyOtpParams
    // requires email for all types, but some types don't actually need it
    if (type === 'email' || type === 'signup') {
      const { error } = await supabase.auth.verifyOtp(
        { token, type, email: email! } as const
      )
      if (error) {
        return NextResponse.json(
          { error: error.message },
          { status: 400 },
        )
      }
    } else {
      // For other OTP types (phone, sms, invite, magiclink, recovery), 
      // use a direct cast since email is not required
      const { error } = await supabase.auth.verifyOtp(
        { token, type } as import('@supabase/supabase-js').VerifyOtpParams
      )
      if (error) {
        return NextResponse.json(
          { error: error.message },
          { status: 400 },
        )
      }
    }

    return NextResponse.json({ success: true }, { status: 200 })
  } catch (error) {
    console.error("Email verification error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

/**
 * POST /api/auth/signup - Create a new user account
 * Uses Supabase for user registration
 */
export async function POST_SIGNUP(request: NextRequest) {
  try {
    const body = await request.json()
    const { email, password, fullName } = body

    if (!email || !password) {
      return NextResponse.json(
        { error: "Email and password are required" },
        { status: 400 },
      )
    }

    // Sign up with Supabase
    const { data: authData, error: authError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
        },
        emailRedirectTo: `${process.env.NEXT_PUBLIC_APP_URL}/auth/verify-email`,
      },
    })

    if (authError) {
      return NextResponse.json(
        { error: authError.message },
        { status: 400 },
      )
    }

    const { user, session } = authData

    // If user was created (not already existing)
    if (user && session) {
      // Link or create Django user
      await linkOrCreateDjangoUser(user, session.access_token)
    }

    return NextResponse.json({ 
      success: true,
      user: user ? {
        id: user.id,
        email: user.email,
        full_name: user.user_metadata?.full_name,
      } : null,
      message: user 
        ? "Account created successfully! Please check your email for verification."
        : "Account already exists. Please check your email for verification.",
    }, { status: 200 })
  } catch (error) {
    console.error("Signup error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

/**
 * POST /api/auth/reset-password - Request password reset
 * Uses Supabase for password reset
 */
export async function POST_RESET_PASSWORD(request: NextRequest) {
  try {
    const body = await request.json()
    const { email } = body

    if (!email) {
      return NextResponse.json(
        { error: "Email is required" },
        { status: 400 },
      )
    }

    // Request password reset with Supabase
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${process.env.NEXT_PUBLIC_APP_URL}/auth/reset-password`,
    })

    if (error) {
      return NextResponse.json(
        { error: error.message },
        { status: 400 },
      )
    }

    // Don't reveal if user exists
    return NextResponse.json({ 
      success: true,
      message: "Password reset link sent to your email",
    }, { status: 200 })
  } catch (error) {
    console.error("Reset password error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

/**
 * POST /api/auth/update-password - Update user password
 * Requires authentication
 */
export async function POST_UPDATE_PASSWORD(request: NextRequest) {
  try {
    const { session, user } = await verifySession(request)

    if (!session || !user) {
      return NextResponse.json(
        { error: "Not authenticated" },
        { status: 401 },
      )
    }

    const body = await request.json()
    const { newPassword } = body

    if (!newPassword) {
      return NextResponse.json(
        { error: "New password is required" },
        { status: 400 },
      )
    }

    // Update password with Supabase
    const { error } = await supabase.auth.updateUser({
      password: newPassword,
    })

    if (error) {
      return NextResponse.json(
        { error: error.message },
        { status: 400 },
      )
    }

    return NextResponse.json({ 
      success: true,
      message: "Password updated successfully",
    }, { status: 200 })
  } catch (error) {
    console.error("Update password error:", error)
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

/**
 * Helper: Get Django user linked to Supabase user
 */
async function getLinkedDjangoUser(supabaseUserId: string) {
  try {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    const response = await fetch(`${apiBaseUrl}/api/auth/supabase-user/${supabaseUserId}/`, {
      method: "GET",
      credentials: "include",
    })

    if (response.ok) {
      return await response.json()
    }
    return null
  } catch (error) {
    console.error("Error getting Django user:", error)
    return null
  }
}

/**
 * Helper: Link existing Django user or create new one for Supabase user
 */
async function linkOrCreateDjangoUser(supabaseUser: User, accessToken: string) {
  try {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    
    const response = await fetch(`${apiBaseUrl}/api/auth/link-supabase-user/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        supabase_user_id: supabaseUser.id,
        email: supabaseUser.email,
        full_name: supabaseUser.user_metadata?.full_name,
      }),
      credentials: "include",
    })

    if (response.ok) {
      return await response.json()
    }
    return null
  } catch (error) {
    console.error("Error linking Django user:", error)
    return null
  }
}

// Export route handlers for individual methods
export const POST_verify_email = POST_VERIFY_EMAIL
export const POST_signup = POST_SIGNUP
export const POST_reset_password = POST_RESET_PASSWORD
export const POST_update_password = POST_UPDATE_PASSWORD
