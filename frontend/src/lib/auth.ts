"use server"

import { cookies } from "next/headers"

const SESSION_COOKIE_NAME = "openoutreach_session"

/**
 * Checks if the user is authenticated by looking for a valid session cookie
 */
export async function isAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies()
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME)
  return !!sessionCookie
}

/**
 * Creates a session for the user by setting a cookie
 * @param _password - Password parameter (reserved for future use)
 * @deprecated - Password-based auth is deprecated. Use session cookie directly.
 */
export async function createSession(_password: string) {
  const cookieStore = await cookies()
  cookieStore.set(SESSION_COOKIE_NAME, "authenticated", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7, // 1 week
    path: "/",
  })
}

/**
 * Destroys the user's session by deleting the cookie
 */
export async function destroySession() {
  const cookieStore = await cookies()
  cookieStore.delete(SESSION_COOKIE_NAME)
}

/**
 * Validates the password against the configured password
 */
export async function validatePassword(password: string): Promise<boolean> {
  const environmentPassword = process.env.APP_PASSWORD
  return password === environmentPassword
}