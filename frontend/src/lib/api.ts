const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://linkedin-api.lengrowth.com"

import { supabase } from './supabase/client'

export interface ApiResponse<T> {
  data?: T
  error?: string
  message?: string
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

function toCamelCase(str: string): string {
  return str.replace(/([-_][a-z])/g, (group) =>
    group.toUpperCase().replace('-', '').replace('_', '')
  )
}

function toSnakeCase(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

function keysToCamelDeep(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map((v) => keysToCamelDeep(v))
  } else if (obj !== null && obj !== undefined && typeof obj === 'object' && obj.constructor === Object) {
    return Object.keys(obj).reduce(
      (result, key) => ({
        ...result,
        [toCamelCase(key)]: keysToCamelDeep((obj as Record<string, unknown>)[key]),
      }),
      {}
    )
  }
  return obj
}

function keysToSnakeDeep(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map((v) => keysToSnakeDeep(v))
  } else if (obj !== null && obj !== undefined && typeof obj === 'object' && obj.constructor === Object) {
    return Object.keys(obj).reduce(
      (result, key) => ({
        ...result,
        [toSnakeCase(key)]: keysToSnakeDeep((obj as Record<string, unknown>)[key]),
      }),
      {}
    )
  }
  return obj
}

async function getHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  
  // Note: We don't need to manually add cookies because they're sent automatically
  // by the browser when making same-origin requests
  return {
    "Content-Type": "application/json",
    ...(session?.access_token ? { "Authorization": `Bearer ${session.access_token}` } : {}),
  }
}

function handleResponse<T>(data: unknown): ApiResponse<T> {
  return { data: data as T }
}

export async function get<T>(path: string, params?: Record<string, string>): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  if (params) {
    // Map params keys to snake_case if they are camelCase
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.append(toSnakeCase(key), value)
      }
    })
  }
  const headers = await getHeaders()
  const response = await fetch(url.toString(), {
    headers,
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorData.error || errorData.message || "An error occurred")
  }
  const data = await response.json()
  return handleResponse<T>(keysToCamelDeep(data))
}

export async function put<T>(path: string, body?: Record<string, unknown>): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const headers = await getHeaders()
  const response = await fetch(url.toString(), {
    method: "PUT",
    headers,
    body: body ? JSON.stringify(keysToSnakeDeep(body)) : undefined,
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorData.error || errorData.message || "An error occurred")
  }
  const data = await response.json()
  return handleResponse<T>(keysToCamelDeep(data))
}

export async function post<T>(path: string, body?: Record<string, unknown> | FormData): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const headers = await getHeaders()
  
  let finalBody: BodyInit | undefined = undefined
  const finalHeaders: Record<string, string> = { ...headers }
  
  if (body instanceof FormData) {
    delete finalHeaders["Content-Type"]
    finalBody = body
  } else if (body !== undefined) {
    finalBody = JSON.stringify(keysToSnakeDeep(body))
  }
  
  const response = await fetch(url.toString(), {
    method: "POST",
    headers: finalHeaders,
    body: finalBody,
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorData.error || errorData.message || "An error occurred")
  }
  const data = await response.json()
  return handleResponse<T>(keysToCamelDeep(data))
}

export async function patch<T>(path: string, body?: Record<string, unknown>): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const headers = await getHeaders()
  const response = await fetch(url.toString(), {
    method: "PATCH",
    headers,
    body: body ? JSON.stringify(keysToSnakeDeep(body)) : undefined,
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorData.error || errorData.message || "An error occurred")
  }
  const data = await response.json()
  return handleResponse<T>(keysToCamelDeep(data))
}

export async function del<T>(path: string): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const headers = await getHeaders()
  const response = await fetch(url.toString(), {
    method: "DELETE",
    headers,
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorData.error || errorData.message || "An error occurred")
  }
  const data = await response.json()
  return handleResponse<T>(keysToCamelDeep(data))
}