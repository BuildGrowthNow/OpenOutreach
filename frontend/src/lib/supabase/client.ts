/**
 * Supabase Client Configuration
 * 
 * This file creates and exports a configured Supabase client instance
 * for use in the frontend application.
 */

import { createClient } from '@supabase/supabase-js'

// Supabase configuration - these should be set in .env.local
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('❌ Supabase configuration is missing!')
  console.error('   Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local')
  console.error('   See .env.local.example for more information')
}

/**
 * Creates and returns a Supabase client instance
 * 
 * @returns Supabase client configured with the project URL and anon key
 */
export const supabase = createClient(supabaseUrl!, supabaseAnonKey!, {
  auth: {
    // Auto-refresh tokens before they expire
    autoRefreshToken: true,
    // Persist session to localStorage
    persistSession: true,
    // Handle refresh tokens silently across tabs
    detectSessionInUrl: true,
    // Storage for session persistence
    storage: {
      getItem: (key: string) => {
        if (typeof window !== 'undefined') {
          return localStorage.getItem(key)
        }
        return null
      },
      setItem: (key: string, value: string) => {
        if (typeof window !== 'undefined') {
          localStorage.setItem(key, value)
        }
      },
      removeItem: (key: string) => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem(key)
        }
      },
    },
  },
  global: {
    // Add request headers with X- prefix to match Supabase's standard
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
  },
})

/**
 * Utility function to check if user is signed in
 * 
 * @returns Promise<boolean> - True if user is signed in
 */
export async function isSignedIn(): Promise<boolean> {
  const { data: { session } } = await supabase.auth.getSession()
  return session !== null
}

/**
 * Utility function to get the current user
 * 
 * @returns Promise<SupabaseUser | null> - The current user object or null
 */
export async function getCurrentUser() {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.user ?? null
}

/**
 * Utility function to sign out the current user
 * 
 * @returns Promise<void>
 */
export async function signOutUser() {
  await supabase.auth.signOut()
}