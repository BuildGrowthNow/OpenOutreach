'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

// Campaign Templates is a deferred feature (Phase 6) - redirect to campaigns
export default function CampaignTemplatesPage() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/campaigns')
  }, [router])
  return null
}
