'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { X, MapPin, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { getLinkedInSetupStatus, type LinkedInSetupStatus } from '@/lib/api/dashboard'

interface LinkedinBannerProps {
  /** If true, the banner will always show regardless of LinkedIn status - for testing/demo purposes */
  alwaysShow?: boolean
  /** Custom callback after connection is established */
  onConnect?: () => void
}

export function LinkedinBanner({ alwaysShow = false, onConnect }: LinkedinBannerProps) {
  const router = useRouter()
  const [isVisible, setIsVisible] = useState(false)
  const [isLinkedInSetup, setIsLinkedInSetup] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)

  const checkLinkedInSetup = useCallback(async () => {
    try {
      setLoading(true)
      const response = await getLinkedInSetupStatus()
      if (response.data) {
        const isSetupComplete = response.data.status.setup_complete
        setIsLinkedInSetup(isSetupComplete)
        // Show banner only if LinkedIn is NOT set up
        setIsVisible(!isSetupComplete || alwaysShow)
      }
    } catch (error) {
      console.error('Failed to check LinkedIn setup status:', error)
      // Show banner on error to encourage setup
      setIsVisible(true)
    } finally {
      setLoading(false)
    }
  }, [alwaysShow])

  // Check LinkedIn setup status on mount
  useEffect(() => {
    void checkLinkedInSetup()
  }, [checkLinkedInSetup])

  const handleDismiss = useCallback(() => {
    setIsVisible(false)
    // Optionally store in localStorage to persist dismissal
    if (typeof window !== 'undefined') {
      localStorage.setItem('openoutreach_linkedin_banner_dismissed', 'true')
    }
  }, [])

  const handleConnect = () => {
    // Navigate to settings page with LinkedIn tab
    if (typeof window !== 'undefined') {
      window.location.href = '/settings?tab=linkedin-credentials'
    }
  }

  // Don't show if already dismissed - use a separate state for dismissed status
  const [isDismissed, setIsDismissed] = useState(false)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const isDismissedLocal = localStorage.getItem('openoutreach_linkedin_banner_dismissed')
      if (isDismissedLocal) {
        setIsDismissed(true)
      }
    }
  }, [])

  // Don't render while loading
  if (loading || isLinkedInSetup === null) {
    return null
  }

  // Don't show if LinkedIn is set up or banner is dismissed
  if (!isVisible || isDismissed) {
    return null
  }

  return (
    <div className="fixed bottom-4 right-4 z-[60] w-[600px] max-w-[90vw] animate-slide-up">
      <div className="bg-amber-500 text-white border border-amber-600 rounded-lg shadow-lg overflow-hidden">
        <div className="px-4 py-3" style={{ minHeight: '200px', maxHeight: '300px' }}>
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 pt-0.5">
              <AlertCircle className="h-5 w-5 text-amber-100" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <h3 className="font-semibold text-sm">LinkedIn Not Connected</h3>
                <Badge variant="secondary" className="bg-amber-600 text-white border-0 text-xs">
                  Action Required
                </Badge>
                <button 
                  onClick={handleDismiss}
                  className="text-amber-100 hover:text-white hover:bg-white/10 rounded p-1 transition-colors flex-shrink-0 ml-2"
                  type="button"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <p className="text-sm text-amber-50 mb-3 line-clamp-2">
                Your OpenOutreach account requires LinkedIn configuration to function properly.
                Without LinkedIn credentials, you cannot run campaigns or connect with leads.
              </p>
              <div className="flex flex-wrap gap-2">
               <Button 
                   variant="secondary" 
                   size="sm"
                   onClick={handleConnect}
                   className="bg-white text-amber-600 hover:bg-amber-50 dark:bg-zinc-800 dark:text-amber-400 dark:hover:bg-zinc-700 border border-white/20 dark:border-zinc-700"
                  type="button"
                >
                  <MapPin className="h-3.5 w-3.5 mr-1.5" />
                  Connect LinkedIn
                </Button>
                <Button 
                   variant="ghost" 
                   size="sm"
                   onClick={handleDismiss}
                   className="text-amber-100 hover:text-white hover:bg-white/10 dark:text-amber-300 dark:hover:bg-zinc-800"
                  type="button"
                >
                  <X className="h-3.5 w-3.5 mr-1" />
                  Dismiss
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LinkedinBanner