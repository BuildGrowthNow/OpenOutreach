const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

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

export function keysToCamel<T>(obj: any): T {
  if (Array.isArray(obj)) {
    return obj.map((v) => keysToCamel(v)) as any
  } else if (obj !== null && obj !== undefined && obj.constructor === Object) {
    return Object.keys(obj).reduce(
      (result, key) => ({
        ...result,
        [toCamelCase(key)]: keysToCamel(obj[key]),
      }),
      {}
    ) as T
  }
  return obj
}

export function keysToSnake(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map((v) => keysToSnake(v))
  } else if (obj !== null && obj !== undefined && obj.constructor === Object) {
    return Object.keys(obj).reduce(
      (result, key) => ({
        ...result,
        [toSnakeCase(key)]: keysToSnake(obj[key]),
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

async function handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorData.error || errorData.message || "An error occurred")
  }
  const data = await response.json()
  return { data: keysToCamel<T>(data) }
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
  return handleResponse<T>(response)
}

export async function post<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const headers = await getHeaders()
  
  let finalBody: any = body
  let finalHeaders: any = { ...headers }
  
  if (body instanceof FormData) {
    delete finalHeaders["Content-Type"]
  } else {
    finalBody = JSON.stringify(keysToSnake(body))
  }
  
  const response = await fetch(url.toString(), {
    method: "POST",
    headers: finalHeaders,
    body: finalBody,
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  return handleResponse<T>(response)
}

export async function patch<T>(path: string, body?: Record<string, unknown>): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const headers = await getHeaders()
  const response = await fetch(url.toString(), {
    method: "PATCH",
    headers,
    body: JSON.stringify(keysToSnake(body)),
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  return handleResponse<T>(response)
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
  return handleResponse<T>(response)
}

