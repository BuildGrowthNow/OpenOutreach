'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Icons } from '@/lib/types/components'
import { getLinkedInSetupStatus, type LinkedInSetupStatus } from '@/lib/api/dashboard'
import { useToast } from '@/components/ui/use-toast'

interface LinkedInSetupModalProps {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  onSetupComplete?: () => void
}

export function LinkedInSetupModal({ isOpen, onOpenChange, onSetupComplete }: LinkedInSetupModalProps) {
  const router = useRouter()
  const { toast } = useToast()
  const [status, setStatus] = useState<LinkedInSetupStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      void (async () => {
        try {
          setLoading(true)
          const response = await getLinkedInSetupStatus()
          if (response.data) {
            setStatus(response.data)
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Failed to load setup status')
        } finally {
          setLoading(false)
        }
      })()
    }
  }, [isOpen])

  const handleGoToSettings = () => {
    // Navigate to settings page and open the LinkedIn tab
    if (typeof window !== 'undefined') {
      window.location.href = '/settings?tab=linkedin-credentials'
    }
  }

  const handleOpenChange = (open: boolean) => {
    if (!open && status?.status.setup_complete) {
      if (onSetupComplete) {
        onSetupComplete()
      }
    }
    onOpenChange(open)
  }

  if (!isOpen) return null

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icons.Globe className="h-6 w-6 text-blue-700" />
            LinkedIn Setup Required
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Your OpenOutreach platform requires LinkedIn configuration to function properly.
            Without LinkedIn credentials, you cannot run campaigns or connect with leads.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12 space-x-4">
            <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <span className="text-muted-foreground">Checking setup status...</span>
          </div>
        ) : error ? (
          <Alert variant="destructive">
            <Icons.AlertCircle className="h-4 w-4" />
            <AlertTitle>Setup Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : status?.status ? (
          <div className="space-y-6">
            {/* Setup Status Overview */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className={`border-l-4 ${
                status.status.linkedin_credentials.exists
                  ? 'border-green-500 bg-green-50/50 dark:bg-green-900/20'
                  : 'border-red-500 bg-red-50/50 dark:bg-red-900/20'
              }`}>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Icons.Lock className={`h-4 w-4 ${
                      status.status.linkedin_credentials.exists
                        ? 'text-green-600'
                        : 'text-red-600'
                    }`} />
                    LinkedIn Credentials
                  </CardTitle>
                  <CardDescription>
                    {status.status.linkedin_credentials.exists
                      ? 'You have configured LinkedIn credentials'
                      : 'LinkedIn credentials are NOT configured'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {status.status.linkedin_credentials.exists
                      ? 'Configured'
                      : 'Missing'}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {status.status.linkedin_credentials.count} credential(s) found
                  </p>
                </CardContent>
              </Card>

              <Card className={`border-l-4 ${
                status.status.linkedin_profile.exists
                  ? 'border-green-500 bg-green-50/50 dark:bg-green-900/20'
                  : 'border-red-500 bg-red-50/50 dark:bg-red-900/20'
              }`}>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Icons.User className={`h-4 w-4 ${
                      status.status.linkedin_profile.exists
                        ? 'text-green-600'
                        : 'text-red-600'
                    }`} />
                    LinkedIn Profile
                  </CardTitle>
                  <CardDescription>
                    {status.status.linkedin_profile.exists
                      ? 'Your LinkedIn profile is configured'
                      : 'Your LinkedIn profile is NOT configured'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {status.status.linkedin_profile.exists
                      ? 'Configured'
                      : 'Missing'}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {status.status.linkedin_profile.count} profile(s) found
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* What You Need to Do - Step by Step */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <Icons.ListTodo className="h-5 w-5 text-blue-600" />
                Step-by-Step Setup
              </h3>
              <div className="space-y-3">
                <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                    1
                  </div>
                  <div>
                    <h4 className="font-medium text-blue-900 dark:text-blue-100">
                      Set Up Your LinkedIn Profile
                    </h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                      Go to <strong className="text-blue-900 dark:text-blue-100">Settings {'>'} LinkedIn Credentials</strong> tab and add your LinkedIn email and password
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                    2
                  </div>
                  <div>
                    <h4 className="font-medium text-blue-900 dark:text-blue-100">
                      Confirm Setup
                    </h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                      After adding your credentials, the system will automatically verify them
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                    3
                  </div>
                  <div>
                    <h4 className="font-medium text-blue-900 dark:text-blue-100">
                      Create Your First Campaign
                    </h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                      Once LinkedIn is set up, you can create and run outreach campaigns
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <p className="text-xs text-blue-700 dark:text-blue-300">
                  <strong>Note:</strong> You only need to set up LinkedIn once. The same profile will work for all your campaigns.
                </p>
              </div>
            </div>

            {/* Important Notes */}
            <Alert className="bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800">
              <Icons.AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              <AlertTitle className="text-amber-700 dark:text-amber-300">Important Security Notice</AlertTitle>
              <AlertDescription className="text-amber-600 dark:text-amber-400 text-sm">
                Your LinkedIn credentials are encrypted at rest using AES-256 encryption.
                We never share your credentials with third parties. Your security is our priority.
              </AlertDescription>
            </Alert>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Button
                variant="outline"
                size="lg"
                onClick={() => {
                  // Open LinkedIn login in a new tab
                  if (typeof window !== 'undefined') {
                    window.open('https://www.linkedin.com/login', '_blank')
                  }
                }}
              >
                <Icons.Link className="h-5 w-5 mr-2" />
                Sign in to LinkedIn
              </Button>

              <Button
                variant="secondary"
                size="lg"
                onClick={() => {
                  // Navigate to settings page and show LinkedIn credentials tab
                  if (typeof window !== 'undefined') {
                    const settingsUrl = '/settings?tab=linkedin-credentials'
                    window.location.href = settingsUrl
                  }
                }}
              >
                <Icons.Settings className="h-5 w-5 mr-2" />
                Go to LinkedIn Settings
              </Button>
            </div>

            <p className="text-center text-xs text-muted-foreground pt-2">
              By configuring LinkedIn, you agree to our Terms of Service and Privacy Policy.
            </p>
          </div>
        ) : (
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 mb-4">
              <Icons.AlertCircle className="h-8 w-8 text-red-600" />
            </div>
            <h3 className="text-lg font-medium mb-2">Setup Incomplete</h3>
            <p className="text-sm text-muted-foreground">
              Your LinkedIn configuration is not complete. Please set up LinkedIn credentials to use the platform.
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default LinkedInSetupModal