/**
 * Production Multi-Tenant Auth Store
 *
 * Manages authentication state using local JWT tokens (not Supabase).
 * Stores access token in memory, refresh token in HTTP-only cookie.
 */

import { create } from 'zustand'

export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
}

interface AuthState {
  // State
  isLoading: boolean
  isAuthenticated: boolean
  error: string | null
  user: User | null
  accessToken: string | null

  // Actions
  initialize: () => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<{ error: string | null }>
  login: (email: string, password: string) => Promise<{ error: string | null }>
  logout: () => Promise<void>
  refreshToken: () => Promise<boolean>
  clearError: () => void
  updateUser: (user: User) => void
}

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'

export const useAuthStore = create<AuthState>((set, get) => ({
  // Initial state
  isLoading: true,
  isAuthenticated: false,
  error: null,
  user: null,
  accessToken: null,

  /**
   * Initialize auth state - fetch current user if token exists
   */
  initialize: async () => {
    try {
      set({ isLoading: true, error: null })

      // Try to get current user (will use refresh token cookie if access token expired)
      const response = await fetch(`${API_BASE}/auth/me/`, {
        credentials: 'include', // Send cookies
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        const user = await response.json()

        // Get token from Authorization header if returned
        const token = response.headers.get('Authorization')?.replace('Bearer ', '')

        set({
          isAuthenticated: true,
          user,
          accessToken: token || null,
          isLoading: false,
          error: null,
        })
      } else {
        // Not authenticated - try refresh
        const refreshed = await get().refreshToken()
        if (refreshed) {
          // Retry getting user
          await get().initialize()
        } else {
          set({
            isAuthenticated: false,
            user: null,
            accessToken: null,
            isLoading: false,
            error: null,
          })
        }
      }
    } catch (error) {
      console.error('Initialize error:', error)
      set({
        isLoading: false,
        isAuthenticated: false,
        user: null,
        accessToken: null,
        error: null, // Silent failure on init
      })
    }
  },

  /**
   * Register new user
   */
  register: async (email: string, password: string, fullName: string) => {
    set({ isLoading: true, error: null })

    try {
      const response = await fetch(`${API_BASE}/auth/register/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        const errorMessage = data.detail || 'Registration failed'
        set({ isLoading: false, error: errorMessage })
        return { error: errorMessage }
      }

      // Registration successful - now login
      set({ isLoading: false, error: null })
      return await get().login(email, password)
    } catch (error) {
      console.error('Register error:', error)
      const errorMessage = 'Network error. Please try again.'
      set({ isLoading: false, error: errorMessage })
      return { error: errorMessage }
    }
  },

  /**
   * Login with email and password
   */
  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null })

    try {
      const response = await fetch(`${API_BASE}/auth/login/`, {
        method: 'POST',
        credentials: 'include', // Important: send/receive cookies
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()

      if (!response.ok) {
        const errorMessage = data.detail || 'Login failed'
        set({ isLoading: false, error: errorMessage })
        return { error: errorMessage }
      }

      // Store access token
      const accessToken = data.access_token

      // Fetch user info
      const userResponse = await fetch(`${API_BASE}/auth/me/`, {
        credentials: 'include',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      })

      if (userResponse.ok) {
        const user = await userResponse.json()

        set({
          isAuthenticated: true,
          user,
          accessToken,
          isLoading: false,
          error: null,
        })

        return { error: null }
      } else {
        set({ isLoading: false, error: 'Failed to fetch user info' })
        return { error: 'Failed to fetch user info' }
      }
    } catch (error) {
      console.error('Login error:', error)
      const errorMessage = 'Network error. Please try again.'
      set({ isLoading: false, error: errorMessage })
      return { error: errorMessage }
    }
  },

  /**
   * Logout user
   */
  logout: async () => {
    const { accessToken } = get()

    try {
      // Call logout endpoint to clear refresh token cookie
      await fetch(`${API_BASE}/auth/logout/`, {
        method: 'POST',
        credentials: 'include',
        headers: accessToken ? {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        } : {
          'Content-Type': 'application/json',
        },
      })
    } catch (error) {
      console.error('Logout error:', error)
    }

    // Clear local state
    set({
      isAuthenticated: false,
      user: null,
      accessToken: null,
      error: null,
      isLoading: false,
    })
  },

  /**
   * Refresh access token using refresh token cookie
   */
  refreshToken: async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh/`, {
        method: 'POST',
        credentials: 'include', // Send refresh token cookie
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        return false
      }

      const data = await response.json()
      const accessToken = data.access_token

      // Update access token
      set({ accessToken })

      return true
    } catch (error) {
      console.error('Token refresh error:', error)
      return false
    }
  },

  /**
   * Clear error message
   */
  clearError: () => {
    set({ error: null })
  },

  /**
   * Update user info (after profile update)
   */
  updateUser: (user: User) => {
    set({ user })
  },
}))

// Axios interceptor helper - auto-refresh on 401
export const setupAuthInterceptor = () => {
  // This will be called by the API client to setup automatic token refresh
  return async (response: Response) => {
    if (response.status === 401) {
      // Try to refresh token
      const refreshed = await useAuthStore.getState().refreshToken()
      if (refreshed) {
        // Retry the request with new token
        return true
      } else {
        // Refresh failed - logout
        await useAuthStore.getState().logout()
        return false
      }
    }
    return false
  }
}

// Export utility functions for convenience
export const authActions = {
  initialize: () => useAuthStore.getState().initialize(),
  register: (email: string, password: string, fullName: string) =>
    useAuthStore.getState().register(email, password, fullName),
  login: (email: string, password: string) =>
    useAuthStore.getState().login(email, password),
  logout: () => useAuthStore.getState().logout(),
  refreshToken: () => useAuthStore.getState().refreshToken(),
  clearError: () => useAuthStore.getState().clearError(),
}
