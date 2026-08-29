"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useAuthStore } from "@/lib/authStoreV2"

export default function ImpersonatePage() {
  const router = useRouter()
  const adoptAccessToken = useAuthStore((state) => state.adoptAccessToken)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const opener = window.opener
    if (!opener) {
      setError("This impersonation window must be opened from the admin panel.")
      return
    }

    const origin = window.location.origin
    const onMessage = (event: MessageEvent) => {
      if (event.source !== opener || event.origin !== origin || event.data?.type !== "lengrowth-impersonation-token") return
      const token = event.data.token
      if (typeof token !== "string") {
        setError("Invalid impersonation handoff.")
        return
      }
      void adoptAccessToken(token).then((accepted) => {
        if (accepted) router.replace("/dashboard")
        else setError("The impersonation session could not be established.")
      })
    }

    window.addEventListener("message", onMessage)
    opener.postMessage({ type: "lengrowth-impersonation-ready" }, origin)
    return () => window.removeEventListener("message", onMessage)
  }, [adoptAccessToken, router])

  return (
    <main className="min-h-screen flex items-center justify-center bg-background px-4">
      <p role="status">{error || "Opening secure impersonation session…"}</p>
    </main>
  )
}
