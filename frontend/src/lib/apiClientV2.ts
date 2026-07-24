/**
 * Production API Client with JWT Auth
 *
 * Wrapper around fetch with automatic token injection and refresh.
 */

import { useAuthStore } from './authStoreV2'

const API_BASE = '/api'

export interface ApiResponse<T = unknown> {
  data?: T
  error?: string
  status: number
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  /**
   * Get authorization header
   */
  private getAuthHeaders(): Record<string, string> {
    const { accessToken } = useAuthStore.getState()
    if (accessToken) {
      return {
        'Authorization': `Bearer ${accessToken}`,
      }
    }
    return {}
  }

  /**
   * Make authenticated request with auto-refresh
   */
  private async request<T = unknown>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`

    try {
      // Add auth headers
      const headers = {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
        ...options.headers,
      }

      let response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include', // Send cookies (refresh token)
      })

      // If 401, try to refresh token and retry once
      if (response.status === 401) {
        const refreshed = await useAuthStore.getState().refreshToken()

        if (refreshed) {
          // Retry with new token
          const newHeaders = {
            'Content-Type': 'application/json',
            ...this.getAuthHeaders(),
            ...options.headers,
          }

          response = await fetch(url, {
            ...options,
            headers: newHeaders,
            credentials: 'include',
          })
        } else {
          // Refresh failed - logout user
          await useAuthStore.getState().logout()
          return {
            status: 401,
            error: 'Session expired. Please login again.',
          }
        }
      }

      // Parse response
      const contentType = response.headers.get('content-type')
      let data: unknown = null

      if (response.status === 204) {
        data = null
      } else if (contentType?.includes('application/json')) {
        data = await response.json()
      } else {
        data = await response.text()
      }

      if (!response.ok) {
        const errData = data as Record<string, string> | null
        return {
          status: response.status,
          error: errData?.detail || errData?.message || `Request failed with status ${response.status}`,
        }
      }

      return {
        status: response.status,
        data: data as T,
      }
    } catch (error) {
      console.error('API request error:', error)
      return {
        status: 0,
        error: error instanceof Error ? error.message : 'Network error',
      }
    }
  }

  /**
   * GET request
   */
  async get<T = unknown>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  /**
   * POST request
   */
  async post<T = unknown>(endpoint: string, data?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  /**
   * PUT request
   */
  async put<T = unknown>(endpoint: string, data?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  /**
   * PATCH request
   */
  async patch<T = unknown>(endpoint: string, data?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  /**
   * DELETE request
   */
  async delete<T = unknown>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }

  /**
   * Upload file (multipart/form-data)
   */
  async upload<T = unknown>(endpoint: string, formData: FormData): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`

    try {
      // Add auth headers (without Content-Type - browser will set it with boundary)
      const headers = {
        ...this.getAuthHeaders(),
      }

      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: formData,
        credentials: 'include',
      })

      const data: unknown = await response.json()

      if (!response.ok) {
        const errData = data as Record<string, string> | null
        return {
          status: response.status,
          error: errData?.detail || errData?.message || `Upload failed with status ${response.status}`,
        }
      }

      return {
        status: response.status,
        data: data as T,
      }
    } catch (error) {
      console.error('Upload error:', error)
      return {
        status: 0,
        error: error instanceof Error ? error.message : 'Upload failed',
      }
    }
  }
}

// Export singleton instance
export const apiClient = new ApiClient(API_BASE)

// Export type
export type { ApiClient }
