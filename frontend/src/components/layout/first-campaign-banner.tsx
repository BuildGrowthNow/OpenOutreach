'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Rocket, X } from 'lucide-react'
import { apiClient } from '@/lib/apiClientV2'

export function FirstCampaignBanner() {
  const router = useRouter()
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const check = async () => {
      const dismissed = localStorage.getItem('first_campaign_banner_dismissed')
      if (dismissed) return

      const res = await apiClient.get<{ data: unknown[]; pagination: { total: number } }>('/campaigns?limit=1')
      if (res.data && (res.data.pagination?.total === 0 || res.data.data?.length === 0)) {
        setVisible(true)
      } else if (res.data) {
        localStorage.setItem('first_campaign_banner_dismissed', '1')
      }
    }
    void check()
  }, [])

  if (!visible) return null

  return (
    <div className="flex items-center justify-between gap-4 bg-emerald-600 px-5 py-2.5 text-white">
      <div className="flex items-center gap-3 text-sm font-medium">
        <Rocket className="h-4 w-4 shrink-0" />
        <span>
          You&apos;re all set - launch your first outreach campaign.{' '}
          <button
            onClick={() => router.push('/campaigns')}
            className="underline underline-offset-2 hover:text-emerald-100 transition-colors"
          >
            Create your first campaign →
          </button>
        </span>
      </div>
      <button
        onClick={() => {
          localStorage.setItem('first_campaign_banner_dismissed', '1')
          setVisible(false)
        }}
        className="shrink-0 rounded p-0.5 hover:bg-emerald-700 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
