"use client"

import { LoginForm } from "@/components/auth/login-form"
import { useAuthStore } from "@/lib/authStore"
import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { getLinkedInSetupStatus } from "@/lib/api/dashboard"

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const session = useAuthStore((state) => state.session)
  const isAuthenticated = !!session
  const [checkingLinkedIn, setCheckingLinkedIn] = useState(false)

  const message = (() => {
    const signupSuccess = searchParams.get("signup")
    const error = searchParams.get("error")
    const success = searchParams.get("success")
    const passwordReset = searchParams.get("password-reset")
    const checkLinkedIn = searchParams.get("check-linkedin")

    if (signupSuccess === "success") {
      return "Account created! Please check your email for verification."
    }
    if (error === "verification_failed") {
      return "Email verification failed. Please try again."
    }
    if (success === "email_verified") {
      return "Email verified successfully! You can now login."
    }
    if (passwordReset === "success") {
      return "Password reset successful! You can now login with your new password."
    }
    return null
  })()

  // Check if LinkedIn setup is required after email verification
  useEffect(() => {
    const checkLinkedInAfterSignup = async () => {
      const shouldCheck = searchParams.get("check-linkedin") === "true"
      
      if (shouldCheck && !checkingLinkedIn) {
        try {
          setCheckingLinkedIn(true)
          const response = await getLinkedInSetupStatus()
          
          if (response.data && !response.data.status.setupComplete) {
            // LinkedIn is NOT configured - show modal
            sessionStorage.setItem('openoutreach_linkedin_setup_pending', 'true')
            router.push('/settings')
          }
        } catch (err) {
          console.error('Failed to check LinkedIn status:', err)
        } finally {
          setCheckingLinkedIn(false)
        }
      }
    }
    
    checkLinkedInAfterSignup()
  }, [searchParams, checkingLinkedIn, router])

  useEffect(() => {
    if (isAuthenticated) {
      // Check if this is a desktop app login
      const isDesktop = searchParams.get("desktop") === "true"
      const callback = searchParams.get("callback") || "lengrowth://auth"

      if (isDesktop && session) {
        // Desktop app login - redirect back with credentials
        const redirectToDesktop = async () => {
          try {
            // Fetch user's LinkedIn profiles
            const response = await fetch('/api/linkedin-profiles/', {
              headers: {
                Authorization: `Bearer ${session.access_token}`
              }
            })

            if (!response.ok) {
              throw new Error('Failed to fetch profiles')
            }

            const data = await response.json()

            if (data.profiles && data.profiles.length > 0) {
              // Use first profile (or show picker if multiple in future)
              const profileId = data.profiles[0].id

              // Redirect back to desktop app with credentials
              window.location.href = `${callback}?token=${session.access_token}&profile_id=${profileId}`
            } else {
              // No profiles - auto-create one for desktop setup
              const createResponse = await fetch('/api/linkedin-profiles/', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  Authorization: `Bearer ${session.access_token}`
                },
                body: JSON.stringify({
                  linkedin_username: '',
                  active: true
                })
              })

              if (!createResponse.ok) {
                throw new Error('Failed to create profile')
              }

              const newProfile = await createResponse.json()
              // Redirect back to desktop app with new profile
              window.location.href = `${callback}?token=${session.access_token}&profile_id=${newProfile.id}`
            }
          } catch (err) {
            console.error('Failed to redirect to desktop:', err)
            // Fallback: redirect to dashboard
            router.push('/')
          }
        }

        redirectToDesktop()
      } else {
        // Normal web login - check if LinkedIn setup is required
        const checkLinkedIn = async () => {
          try {
            const response = await getLinkedInSetupStatus()

            if (response.data && !response.data.status.setupComplete) {
              // LinkedIn is NOT configured - show modal
              sessionStorage.setItem('openoutreach_linkedin_setup_pending', 'true')
              router.push('/settings')
            }
          } catch (err) {
            console.error('Failed to check LinkedIn status:', err)
          }
        }

        checkLinkedIn()
      }
    }
  }, [isAuthenticated, session, searchParams, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      {message && (
        <div className="fixed top-4 right-4 bg-green-500 text-white px-4 py-2 rounded shadow-lg">
          {message}
        </div>
      )}
      <LoginForm />
    </div>
  )
}
