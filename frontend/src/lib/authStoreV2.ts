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
  status: string
  admin_notes: string | null
  is_admin: boolean
  admin_role: string | null
}

interface AuthState {
  // State
  isLoading: boolean
  isInitialized: boolean
  isAuthenticated: boolean
  error: string | null
  user: User | null
  accessToken: string | null
  refreshTokenValue: string | null

  // Derived
  isAdmin: () => boolean

  // Actions
  initialize: () => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<{ error: string | null }>
  login: (email: string, password: string) => Promise<{ error: string | null }>
  logout: () => Promise<void>
  refreshToken: () => Promise<boolean>
  clearError: () => void
  updateUser: (user: User) => void
  resetPassword: (email: string) => Promise<{ error: string | null }>
  resendVerification: (email: string) => Promise<{ error: string | null }>
}

// API base URL - use relative path so requests go through the Next.js proxy
// (avoids CORS issues when the backend is on a different domain)
const API_BASE = '/api'

function notifyDesktopAuth(userId: string) {
  if (typeof window === 'undefined') return
  const pywebview = (window as unknown as { pywebview?: { api?: { confirm_auth?: (id: string) => void } } }).pywebview
  if (pywebview?.api?.confirm_auth) {
    pywebview.api.confirm_auth(userId)
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // Initial state
  isLoading: true,
  isInitialized: false,
  isAuthenticated: false,
  error: null,
  user: null,
  accessToken: null,
  refreshTokenValue: null,

  isAdmin: () => get().user?.is_admin === true,

  /**
   * Initialize auth state - fetch current user if token exists
   */
  initialize: async () => {
    try {
      set({ isLoading: true, error: null })

      // Desktop restart: the exe passes a fresh access token in the URL so we
      // don't need to race the pywebview bridge for the keychain refresh token.
      if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search)
        const desktopToken = params.get('desktop_token')
        if (desktopToken) {
          set({ accessToken: desktopToken })
          const url = new URL(window.location.href)
          url.searchParams.delete('desktop_token')
          window.history.replaceState({}, '', url.pathname + url.search)
        }
      }

      // If we already have an access token (from desktop_token or prior session),
      // validate it directly before falling through to the refresh flow.
      const existingToken = get().accessToken
      if (existingToken) {
        const response = await fetch(`${API_BASE}/auth/me/`, {
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${existingToken}`,
          },
        })
        if (response.ok) {
          const user = await response.json()
          set({ isAuthenticated: true, user, isLoading: false, isInitialized: true, error: null })
          notifyDesktopAuth(user.id)
          return
        }
      }

      // Step 1: try to get a fresh access token via the refresh cookie
      const refreshed = await get().refreshToken()
      if (!refreshed) {
        set({ isAuthenticated: false, user: null, accessToken: null, isLoading: false, isInitialized: true, error: null })
        return
      }

      // Step 2: fetch user with the newly-obtained access token
      const accessToken = get().accessToken
      const response = await fetch(`${API_BASE}/auth/me/`, {
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
        },
      })

      if (response.ok) {
        const user = await response.json()
        set({ isAuthenticated: true, user, isLoading: false, isInitialized: true, error: null })
        notifyDesktopAuth(user.id)
      } else {
        set({ isAuthenticated: false, user: null, accessToken: null, isLoading: false, isInitialized: true, error: null })
      }
    } catch (error) {
      console.error('Initialize error:', error)
      set({ isLoading: false, isInitialized: true, isAuthenticated: false, user: null, accessToken: null, error: null })
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

      // Registration successful - email verification required
      set({ isLoading: false, error: null })
      return { error: null }
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

      // Store tokens
      const accessToken = data.access_token
      const refreshTokenValue = data.refresh_token || null

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
          refreshTokenValue: refreshTokenValue,
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
      refreshTokenValue: null,
      error: null,
      isLoading: false,
    })
  },

  /**
   * Refresh access token using refresh token cookie (or keychain on desktop restart)
   */
  refreshToken: async () => {
    try {
      // On desktop, try to get the refresh token from the system keychain if the
      // HTTP-only cookie is gone (i.e. after the webview is restarted).
      // Poll briefly for pywebview.api - it's injected by pywebview's bridge but
      // may not be fully registered when the first useEffect fires.
      let body: string | undefined
      if (typeof window !== 'undefined' && typeof (window as unknown as { pywebview?: unknown }).pywebview !== 'undefined') {
        const keychainToken = await new Promise<string | null>((resolve) => {
          const poll = (tries: number) => {
            const api = (window as unknown as { pywebview?: { api?: { get_keychain_refresh_token?: () => string | null | Promise<string | null> } } }).pywebview?.api
            if (api?.get_keychain_refresh_token) {
              Promise.resolve(api.get_keychain_refresh_token()).then(resolve).catch(() => resolve(null))
            } else if (tries > 0) {
              setTimeout(() => poll(tries - 1), 50)
            } else {
              resolve(null)
            }
          }
          poll(20) // up to 1s
        })
        if (keychainToken) {
          body = JSON.stringify({ refresh_token: keychainToken })
        }
      }

      const response = await fetch(`${API_BASE}/auth/refresh/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        ...(body ? { body } : {}),
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

  resetPassword: async (email: string) => {
    try {
      await fetch(`${API_BASE}/auth/password-reset/request/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      // Backend always returns success to prevent enumeration
      return { error: null }
    } catch {
      return { error: 'Network error. Please try again.' }
    }
  },

  resendVerification: async (email: string) => {
    try {
      await fetch(`${API_BASE}/auth/resend-verification/?email=${encodeURIComponent(email)}`, {
        method: 'POST',
      })
      return { error: null }
    } catch {
      return { error: 'Network error. Please try again.' }
    }
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
  resetPassword: (email: string) => useAuthStore.getState().resetPassword(email),
  resendVerification: (email: string) => useAuthStore.getState().resendVerification(email),
}
