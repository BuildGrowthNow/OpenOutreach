const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

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

function getHeaders() {
  // Note: We don't need to manually add cookies because they're sent automatically
  // by the browser when making same-origin requests
  return {
    "Content-Type": "application/json",
  }
}

async function handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new ApiError(response.status, errorData.error || errorData.message || "An error occurred")
  }
  const data = await response.json()
  return { data }
}

export async function get<T>(path: string, params?: Record<string, string>): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.append(key, value)
      }
    })
  }
  const response = await fetch(url.toString(), {
    headers: getHeaders(),
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  return handleResponse<T>(response)
}

export async function post<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const response = await fetch(url.toString(), {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(body),
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  return handleResponse<T>(response)
}

export async function patch<T>(path: string, body?: Record<string, unknown>): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const response = await fetch(url.toString(), {
    method: "PATCH",
    headers: getHeaders(),
    body: JSON.stringify(body),
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  return handleResponse<T>(response)
}

export async function del<T>(path: string): Promise<ApiResponse<T>> {
  const url = new URL(path, API_URL)
  const response = await fetch(url.toString(), {
    method: "DELETE",
    headers: getHeaders(),
    cache: "no-store",
    credentials: 'include', // Include cookies for cross-origin requests
  })
  return handleResponse<T>(response)
}
