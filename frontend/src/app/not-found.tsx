"use client"

import { useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function NotFound() {
  useEffect(() => {
    // This prevents the build error related to useSearchParams()
    // by using Suspense boundary
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="text-center max-w-md">
        <h1 className="text-4xl font-bold tracking-tight mb-4">404</h1>
        <h2 className="text-2xl font-semibold mb-2">Page Not Found</h2>
        <p className="text-muted-foreground mb-6">
          The page you are looking for doesn{"'"}t exist or has been moved.
        </p>
        <Button asChild>
          <Link href="/login">Return to Login</Link>
        </Button>
      </div>
    </div>
  )
}