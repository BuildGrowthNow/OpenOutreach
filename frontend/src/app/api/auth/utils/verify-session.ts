/**
 * Session Verification Utilities
 * 
 * Utilities for verifying Supabase sessions in API routes.
 */

import { NextRequest } from "next/server"
import { supabase } from "@/lib/supabase/client"

/**
 * Extract and verify the session from the request
 * 
 * @param request - The Next.js request object
 * @returns Object containing session and user if verified, or error message
 */
export async function verifySession(request: NextRequest) {
  try {
    // Try to get session from Authorization header
    const authHeader = request.headers.get("authorization")
    let accessToken: string | null = null

    if (authHeader && authHeader.startsWith("Bearer ")) {
      accessToken = authHeader.substring(7)
    }

    // If no access token in header, try cookies
    // Note: For Next.js cookie access, we need to use cookies() which returns a Promise
    if (!accessToken) {
      // We'll need to handle cookies differently in Next.js 16
      // For now, we rely on the Authorization header
      return { session: null, user: null }
    }

    // Verify the access token with Supabase
    const { data: { session }, error } = await supabase.auth.setSession({ access_token: accessToken, refresh_token: '' })

    if (error || !session) {
      return { 
        session: null, 
        user: null,
        error: error?.message || "Invalid session",
      }
    }

    return { session, user: session.user }
  } catch (error) {
    console.error("Session verification error:", error)
    return { session: null, user: null }
  }
}

/**
 * Check if the current user is authenticated
 * 
 * @param request - The Next.js request object
 * @returns Boolean indicating if user is authenticated
 */
export async function isUserAuthenticated(request: NextRequest): Promise<boolean> {
  const { session } = await verifySession(request)
  return session !== null
}

/**
 * Get the current authenticated user
 * 
 * @param request - The Next.js request object
 * @returns The user object or null if not authenticated
 */
export async function getCurrentUser(request: NextRequest) {
  const { session, user } = await verifySession(request)
  return user
}