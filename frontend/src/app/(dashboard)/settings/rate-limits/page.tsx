'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { getRateLimits, type Settings } from '@/lib/api/dashboard'
import RateLimitForm from '@/components/settings/rate-limit-form'

export default function RateLimitsPage() {
  const [rateLimits, setRateLimits] = useState<Settings['rate_limits'] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadRateLimits = useCallback(async () => {
    try {
      setLoading(true)
      const response = await getRateLimits()
      if (response.data) {
        setRateLimits(response.data)
      } else {
        setError('Failed to load rate limits')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      await loadRateLimits()
    })()
  }, [loadRateLimits])

  const handleRateLimitsUpdate = () => {
    loadRateLimits()
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
          <Skeleton className="h-10 w-24" />
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <Icons.AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Failed to load rate limits: {error}
          <Button variant="outline" className="ml-4" onClick={loadRateLimits}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Rate Limits</h1>
          <p className="text-muted-foreground">
            Configure daily limits for connection requests and follow-up messages
          </p>
        </div>
        <Button variant="outline" onClick={loadRateLimits}>
          <Icons.RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Daily Rate Limits</CardTitle>
          <CardDescription>
            Manage your connection and follow-up message limits to stay within LinkedIn recommended guidelines
          </CardDescription>
        </CardHeader>
        <CardContent>
          {rateLimits && (
            <RateLimitForm 
              initialData={rateLimits}
              onSuccess={handleRateLimitsUpdate}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
