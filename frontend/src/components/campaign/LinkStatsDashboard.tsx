'use client'

import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { TrackedLink, getLinkAnalytics } from '@/lib/api/dashboard'

export function LinkStatsDashboard({ link, campaignId, onClose }: { link: TrackedLink; campaignId: string; onClose: () => void }) {
  const [analytics, setAnalytics] = useState<{ total_clicks: number; unique_clicks: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getLinkAnalytics(link.id, campaignId).then((response) => {
      if (response.error) setError(response.error)
      else if (response.data?.analytics) setAnalytics(response.data.analytics)
      else setAnalytics({ total_clicks: link.total_clicks ?? 0, unique_clicks: link.unique_clicks ?? 0 })
    })
  }, [link, campaignId])

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <Card className="w-full max-w-lg">
      <CardHeader className="flex flex-row items-center justify-between"><CardTitle>{link.name ?? link.key ?? 'Link analytics'}</CardTitle><Button variant="ghost" size="icon" onClick={onClose} aria-label="Close analytics"><X className="h-4 w-4" /></Button></CardHeader>
      <CardContent>{error ? <p className="text-destructive">{error}</p> : <div className="grid grid-cols-2 gap-4"><div><p className="text-sm text-muted-foreground">Clicks</p><p className="text-2xl font-semibold">{analytics?.total_clicks ?? '—'}</p></div><div><p className="text-sm text-muted-foreground">Unique recipients</p><p className="text-2xl font-semibold">{analytics?.unique_clicks ?? '—'}</p></div></div>}</CardContent>
    </Card>
  </div>
}
