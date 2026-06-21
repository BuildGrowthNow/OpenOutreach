/**
 * Zustand Auth Store - Supabase Integration
 * 
 * Manages authentication state using Supabase as the canonical identity provider.
 */

import { create } from 'zustand'
import { supabase } from './supabase/client'
import { Session, User } from '@supabase/supabase-js'

interface AuthState {
  // State
  isLoading: boolean
  error: string | null
  session: Session | null
  user: User | null
  
  // Actions
  initialize: () => Promise<void>
  login: (email: string, password: string) => Promise<{ error: string | null }>
  logout: () => Promise<void>
  signup: (email: string, password: string, fullName: string) => Promise<{ error: string | null; user?: User }>
  verifyEmail: (token: string) => Promise<{ error: string | null }>
  resendEmailVerification: (email: string) => Promise<{ error: string | null }>
  resetPassword: (email: string) => Promise<{ error: string | null }>
  updatePassword: (newPassword: string) => Promise<{ error: string | null }>
  updateProfile: (data: { full_name?: string; avatar_url?: string }) => Promise<{ error: string | null }>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // Initial state
  isLoading: true,
  error: null,
  session: null,
  user: null,

  /**
   * Initialize auth state from Supabase session
   * Called on app startup to restore auth state
   */
  initialize: async () => {
    try {
      const { data: { session }, error } = await supabase.auth.getSession()
      
      if (error) {
        console.error('Error getting session:', error)
        set({ 
          isLoading: false, 
          error: error.message,
          session: null,
          user: null,
        })
        return
      }
      
      set({ 
        isLoading: false,
        session: session,
        user: session?.user ?? null,
        error: null,
      })
    } catch (error) {
      console.error('Initialize error:', error)
      set({ 
        isLoading: false,
        error: 'Failed to initialize authentication',
        session: null,
        user: null,
      })
    }
  },

  /**
   * Login with email and password
   * Uses Supabase auth.signInWithPassword
   */
  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null })
    
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      })
      
      if (error) {
        set({ 
          isLoading: false, 
          error: error.message,
        })
        return { error: error.message }
      }
      
      set({ 
        isLoading: false,
        session: data.session,
        user: data.user ?? null,
        error: null,
      })
      return { error: null }
    } catch (error) {
      console.error('Login error:', error)
      set({ 
        isLoading: false,
        error: 'Network error. Please try again.',
      })
      return { error: 'Network error' }
    }
  },

  /**
   * Sign out the current user
   * Removes session from Supabase and clears local state
   */
  logout: async () => {
    try {
      // Sign out from Supabase
      const { error } = await supabase.auth.signOut()
      
      if (error) {
        console.error('Sign out error:', error)
      }
      
      // Clear all stored data
      set({
        isLoading: false,
        error: null,
        session: null,
        user: null,
      })
    } catch (error) {
      console.error('Logout error:', error)
      // Fallback: still clear local state
      set({
        isLoading: false,
        error: null,
        session: null,
        user: null,
      })
    }
  },

  /**
   * Create a new user account
   * Uses Supabase auth.signUp
   */
  signup: async (email: string, password: string, fullName: string) => {
    set({ isLoading: true, error: null })
    
    try {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: fullName,
          },
        },
      })
      
      if (error) {
        set({ 
          isLoading: false, 
          error: error.message,
        })
        return { error: error.message }
      }
      
      set({ 
        isLoading: false,
        session: data.session,
        user: data.user ?? null,
        error: null,
      })
      
      return { error: null, user: data.user ?? undefined }
    } catch (error) {
      console.error('Signup error:', error)
      set({ 
        isLoading: false,
        error: 'Failed to create account. Please try again.',
      })
      return { error: 'Signup failed' }
    }
  },

  /**
   * Verify email using token
   * Used for email verification after signup
   */
  verifyEmail: async (token: string, email?: string) => {
    set({ isLoading: true, error: null })
    
    try {
      // The token verification happens via URL callback,
      // but we can also use the verifyOtp method for custom flows
      // Note: Supabase SDK requires email for email verification OTP
      if (!email) {
        return { error: 'Email is required for email verification' }
      }
      const { data, error } = await supabase.auth.verifyOtp({
        token,
        type: 'email',
        email,
      })
      
      if (error) {
        set({ 
          isLoading: false, 
          error: error.message,
        })
        return { error: error.message }
      }
      
      set({ 
        isLoading: false,
        session: data.session,
        user: data.user ?? null,
        error: null,
      })
      return { error: null }
    } catch (error) {
      console.error('Email verification error:', error)
      set({ 
        isLoading: false,
        error: 'Failed to verify email. Please try again.',
      })
      return { error: 'Verification failed' }
    }
  },

  /**
   * Resend email verification
   * Sends a new verification email to the user
   */
  resendEmailVerification: async (email: string) => {
    set({ isLoading: true, error: null })
    
    try {
      const { error } = await supabase.auth.resend({
        type: 'signup',
        email,
      })
      
      if (error) {
        set({ 
          isLoading: false, 
          error: error.message,
        })
        return { error: error.message }
      }
      
      set({ 
        isLoading: false,
        error: null,
      })
      return { error: null }
    } catch (error) {
      console.error('Resend verification error:', error)
      set({ 
        isLoading: false,
        error: 'Failed to resend verification email.',
      })
      return { error: 'Resend failed' }
    }
  },

  /**
   * Request password reset
   * Sends a password reset email to the user
   */
  resetPassword: async (email: string) => {
    set({ isLoading: true, error: null })
    
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        // Redirect to frontend for password reset completion
        // The frontend should handle the callback and call updatePassword
        redirectTo: `${window.location.origin}/auth/reset-password`,
      })
      
      if (error) {
        set({ 
          isLoading: false, 
          error: error.message,
        })
        return { error: error.message }
      }
      
      set({ 
        isLoading: false,
        error: null,
      })
      return { error: null }
    } catch (error) {
      console.error('Reset password error:', error)
      set({ 
        isLoading: false,
        error: 'Failed to send password reset email.',
      })
      return { error: 'Reset failed' }
    }
  },

  /**
   * Update the current user's password
   * Requires the user to be authenticated
   */
  updatePassword: async (newPassword: string) => {
    const { session } = get()
    
    if (!session) {
      return { error: 'Not authenticated' }
    }
    
    set({ isLoading: true, error: null })
    
    try {
      const { error } = await supabase.auth.updateUser({
        password: newPassword,
      })
      
      if (error) {
        set({ 
          isLoading: false, 
          error: error.message,
        })
        return { error: error.message }
      }
      
      set({ 
        isLoading: false,
        error: null,
      })
      return { error: null }
    } catch (error) {
      console.error('Update password error:', error)
      set({ 
        isLoading: false,
        error: 'Failed to update password.',
      })
      return { error: 'Password update failed' }
    }
  },

  /**
   * Update the current user's profile
   */
  updateProfile: async (data: { full_name?: string; avatar_url?: string }) => {
    const { session } = get()
    
    if (!session) {
      return { error: 'Not authenticated' }
    }
    
    set({ isLoading: true, error: null })
    
    try {
      // Build UserAttributes object for Supabase
      const updateData: { data?: { full_name?: string } } = {}
      if (data.full_name !== undefined) {
        updateData.data = { full_name: data.full_name }
      }
      const { error } = await supabase.auth.updateUser(updateData)
      
      if (error) {
        set({ 
          isLoading: false, 
          error: error.message,
        })
        return { error: error.message }
      }
      
      // Update user in state
      const updatedUser = { ...session.user, ...data } as User
      set({ 
        isLoading: false,
        user: updatedUser,
        error: null,
      })
      return { error: null }
    } catch (error) {
      console.error('Update profile error:', error)
      set({ 
        isLoading: false,
        error: 'Failed to update profile.',
      })
      return { error: 'Profile update failed' }
    }
  },
}))

// Export utility functions for convenience
export const authActions = {
  initialize: () => useAuthStore.getState().initialize(),
  login: (email: string, password: string) => useAuthStore.getState().login(email, password),
  logout: () => useAuthStore.getState().logout(),
  signup: (email: string, password: string, fullName: string) => useAuthStore.getState().signup(email, password, fullName),
  verifyEmail: (token: string) => useAuthStore.getState().verifyEmail(token),
  resendEmailVerification: (email: string) => useAuthStore.getState().resendEmailVerification(email),
  resetPassword: (email: string) => useAuthStore.getState().resetPassword(email),
  updatePassword: (newPassword: string) => useAuthStore.getState().updatePassword(newPassword),
  updateProfile: (data: { full_name?: string; avatar_url?: string }) => useAuthStore.getState().updateProfile(data),
}
