'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Icons } from '@/lib/types/components'
import { 
  getLinkedInSetupGuide, 
  getLinkedInSetupStatus, 
  getLinkedInCookieInstructions, 
  getLinkedInCredentials, 
  createLinkedInCredentials,
  updateLinkedInCredentials,
  deleteLinkedInCredentials,
  type LinkedInSetupGuide, 
  type LinkedInSetupStatus, 
  type LinkedInCookieInstructions,
  type LinkedInCredentials
} from '@/lib/api/dashboard'
import LinkedInCredentialForm from '@/components/settings/linkedin-credential-form'
import LinkedInCredentialCard from '@/components/settings/linkedin-credential-card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/use-toast'
import { 
  Plus, 
  RefreshCw, 
  Lock, 
  Info, 
  Zap, 
  Shield, 
  AlertCircle,
  Link,
  ListTodo,
  CheckCircle
} from 'lucide-react'

interface LinkedInSetupStatusData {
  linkedin_profile: {
    exists: boolean
    count: number
    requires_attention?: boolean
  }
  linkedin_credentials: {
    exists: boolean
    count: number
    active_count?: number
    requires_attention?: boolean
  }
  setup_complete: boolean
  setup_progress: {
    current: number
    total: number
  }
}

interface LinkedInConnectionTabProps {
  onSetupComplete?: () => void
}

export function LinkedInConnectionTab({ onSetupComplete }: LinkedInConnectionTabProps) {
  const [guide, setGuide] = useState<LinkedInSetupGuide | null>(null)
  const [statusData, setStatusData] = useState<LinkedInSetupStatus | null>(null)
  const [instructions, setInstructions] = useState<LinkedInCookieInstructions | null>(null)
  const [linkedinCredentials, setLinkedinCredentials] = useState<LinkedInCredentials[]>([])
  
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCookieInstructions, setShowCookieInstructions] = useState(false)
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [editingCredential, setEditingCredential] = useState<LinkedInCredentials | null>(null)
  
  const { toast } = useToast()

  useEffect(() => {
    void (async () => {
      try {
        setLoading(true)
        const [guideRes, statusRes, instructionsRes, credsRes] = await Promise.all([
          getLinkedInSetupGuide(),
          getLinkedInSetupStatus(),
          getLinkedInCookieInstructions(),
          getLinkedInCredentials()
        ])
        
        if (guideRes.data) setGuide(guideRes.data)
        if (statusRes.data) setStatusData(statusRes.data)
        if (instructionsRes.data) setInstructions(instructionsRes.data)
        if (credsRes.data) setLinkedinCredentials(credsRes.data.credentials || [])
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load LinkedIn connection data')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const handleLinkedInCredentialsUpdate = () => {
    void (async () => {
      try {
        const response = await getLinkedInCredentials()
        if (response.data) {
          setLinkedinCredentials(response.data.credentials || [])
        }
      } catch (err) {
        console.debug('Failed to load LinkedIn credentials:', err)
      }
    })()
  }

  const handleAddCredential = async (email: string, password: string, username: string) => {
    try {
      const response = await createLinkedInCredentials({ email, password, username })
      if (response.data) {
        toast({
          title: 'Success',
          description: 'LinkedIn credential added successfully',
        })
        setIsAddDialogOpen(false)
        handleLinkedInCredentialsUpdate()
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to add credential',
          variant: 'destructive',
        })
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'An unexpected error occurred',
        variant: 'destructive',
      })
    }
  }

  const handleUpdateCredential = async (id: number, email: string, password: string, username: string) => {
    try {
      const response = await updateLinkedInCredentials(id, { email, password, username })
      if (response.data) {
        toast({
          title: 'Success',
          description: 'LinkedIn credential updated successfully',
        })
        setEditingCredential(null)
        handleLinkedInCredentialsUpdate()
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to update credential',
          variant: 'destructive',
        })
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'An unexpected error occurred',
        variant: 'destructive',
      })
    }
  }

  const handleDeleteCredential = async (id: number) => {
    if (!confirm('Are you sure you want to deactivate this credential? This action cannot be undone.')) {
      return
    }
    try {
      const response = await deleteLinkedInCredentials(id)
      if (response.data) {
        toast({
          title: 'Success',
          description: 'Credential deactivated successfully',
        })
        handleLinkedInCredentialsUpdate()
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to deactivate credential',
          variant: 'destructive',
        })
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'An unexpected error occurred',
        variant: 'destructive',
      })
    }
  }

  const handleStartSetup = () => {
    // The setup is done through the credentials form
    toast({
      title: 'LinkedIn Setup',
      description: 'Add your LinkedIn credentials to configure LinkedIn for your outreach campaigns',
    })
  }

  if (loading) {
    return (
      <div className="flex-1 p-4 md:p-6 lg:p-8">
        <div className="flex items-center justify-center h-96">
          <div className="flex flex-col items-center gap-4">
            <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <div className="text-muted-foreground">Loading LinkedIn connection data...</div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 p-4 md:p-6 lg:p-8">
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertTitle>Failed to load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!guide || !instructions || !statusData) {
    return (
      <div className="flex-1 p-4 md:p-6 lg:p-8">
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertTitle>Invalid Data</AlertTitle>
          <AlertDescription>Failed to load LinkedIn connection data. Please try again.</AlertDescription>
        </Alert>
      </div>
    )
  }

  const getStatusValue = (key: string, defaultValue: unknown = null): unknown => {
    if (!statusData) return defaultValue
    const statusObj = (statusData as LinkedInSetupStatus).status as Record<string, unknown>
    return statusObj[key] ?? ((statusData as unknown) as Record<string, unknown>)[key] ?? defaultValue
  }

  const linkedinProfile = (statusData?.status?.linkedin_profile ?? {}) as LinkedInSetupStatusData['linkedin_profile']
  const linkedinCredentialsData = (statusData?.status?.linkedin_credentials ?? {}) as LinkedInSetupStatusData['linkedin_credentials']
  const setupComplete = Boolean(statusData?.status?.setup_complete ?? false)
  const setupProgress = (statusData?.status?.setup_progress ?? { current: 0, total: 0 }) as LinkedInSetupStatusData['setup_progress']

  const getProperty = (obj: Record<string, unknown>, key: string, defaultValue: unknown = null) => {
    return obj[key] ?? defaultValue
  }

  const profileExists = Boolean(getProperty(linkedinProfile, 'exists', false))
  const credExists = Boolean(getProperty(linkedinCredentialsData, 'exists', false))
  const profileCount = Number(getProperty(linkedinProfile, 'count', 0))
  const credCount = Number(getProperty(linkedinCredentialsData, 'count', 0))
  const progressCurrent = Number(getProperty(setupProgress, 'current', 0))
  const progressTotal = Number(getProperty(setupProgress, 'total', 0))

  return (
    <div className="flex-1 space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">LinkedIn Connection</h1>
          <p className="text-muted-foreground mt-1">
            Configure your LinkedIn account for outreach campaigns
          </p>
        </div>
        <div className="flex items-center gap-4">
          {setupComplete ? (
            <Badge variant="outline" className="bg-emerald-950/30 text-emerald-400 border-emerald-800/50 dark:bg-emerald-900/20 dark:text-emerald-400">
              <Icons.CheckCircle className="mr-2 h-3.5 w-3.5" />
              LinkedIn Connected
            </Badge>
          ) : (
            <Badge variant="outline" className="bg-blue-950/30 text-blue-400 border-blue-800/50 dark:bg-blue-900/20 dark:text-blue-400">
              <Icons.AlertCircle className="mr-2 h-3.5 w-3.5" />
              Setup Required
            </Badge>
          )}
          <Button variant="outline" onClick={handleLinkedInCredentialsUpdate}>
            <Icons.RefreshCw className="mr-2 h-4 w-4" />
            Refresh Status
          </Button>
        </div>
      </div>

      {/* Setup Status Card */}
      <Card>
        <CardHeader>
          <CardTitle>Setup Status</CardTitle>
          <CardDescription>
            Your current LinkedIn configuration status
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className={`p-4 rounded-lg border ${profileExists ? 'bg-green-950/30 border-green-900/50 dark:bg-green-900/20 dark:border-green-800/50' : 'bg-red-950/30 border-red-900/50 dark:bg-red-900/20 dark:border-red-800/50'}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icons.User className={`h-5 w-5 ${profileExists ? 'text-green-400' : 'text-red-400'}`} />
                <span className="font-medium text-zinc-100">LinkedIn Profile</span>
              </div>
              <div className="text-sm text-muted-foreground">
                {profileExists ? 'Configured' : 'Not Configured'}
              </div>
              <div className="text-xs mt-1 text-zinc-400">
                {profileCount} profile(s) found
              </div>
            </div>
            <div className={`p-4 rounded-lg border ${credExists ? 'bg-green-950/30 border-green-900/50 dark:bg-green-900/20 dark:border-green-800/50' : 'bg-red-950/30 border-red-900/50 dark:bg-red-900/20 dark:border-red-800/50'}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icons.Lock className={`h-5 w-5 ${credExists ? 'text-green-400' : 'text-red-400'}`} />
                <span className="font-medium text-zinc-100">LinkedIn Credentials</span>
              </div>
              <div className="text-sm text-muted-foreground">
                {credExists ? 'Configured' : 'Not Configured'}
              </div>
              <div className="text-xs mt-1 text-zinc-400">
                {credCount} credential(s) found
              </div>
            </div>
            <div className={`p-4 rounded-lg border ${setupComplete ? 'bg-green-950/30 border-green-900/50 dark:bg-green-900/20 dark:border-green-800/50' : 'bg-amber-950/30 border-amber-900/50 dark:bg-amber-900/20 dark:border-amber-800/50'}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icons.CheckCircle className={`h-5 w-5 ${setupComplete ? 'text-green-400' : 'text-amber-400'}`} />
                <span className="font-medium text-zinc-100">Overall Status</span>
              </div>
              <div className="text-sm text-muted-foreground">
                {setupComplete ? 'Ready' : 'In Progress'}
              </div>
              <div className="text-xs mt-1 text-zinc-400">
                {progressCurrent} / {progressTotal} steps complete
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content Tabs */}
      <Tabs defaultValue="credentials" className="space-y-6">
        <TabsList className="grid grid-cols-2">
          <TabsTrigger value="credentials">
            <Icons.Link className="mr-2 h-4 w-4" />
            Credentials
          </TabsTrigger>
          <TabsTrigger value="setup-guide">
            <Icons.ListTodo className="mr-2 h-4 w-4" />
            Setup Guide
          </TabsTrigger>
        </TabsList>

        {/* Credentials Tab */}
        <TabsContent value="credentials" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>LinkedIn Credentials</CardTitle>
              <CardDescription>
                Add and manage your LinkedIn account credentials for outreach campaigns
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Your LinkedIn credentials are encrypted at rest using AES-256.
                  Each credential includes usage tracking, health monitoring, and automatic rotation alerts.
                </p>
                <div className="flex items-center space-x-2">
                  <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="h-4 w-4 mr-2" />
                        Add Credential
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-3xl">
                      <DialogHeader>
                        <DialogTitle>Add LinkedIn Credential</DialogTitle>
                        <DialogDescription>
                          Add a new LinkedIn account for your outreach campaigns
                        </DialogDescription>
                      </DialogHeader>
                      <LinkedInCredentialForm 
                        onSuccess={() => {
                          setIsAddDialogOpen(false)
                          handleLinkedInCredentialsUpdate()
                        }}
                        onCancel={() => setIsAddDialogOpen(false)}
                      />
                    </DialogContent>
                  </Dialog>
                  <Button variant="outline" onClick={handleLinkedInCredentialsUpdate}>
                    <Icons.RefreshCw className="h-4 w-4 mr-2" />
                    Refresh
                  </Button>
                </div>
              </div>

              {linkedinCredentials.length === 0 ? (
                <div className="text-center py-12 bg-muted rounded-lg border-2 border-dashed border-muted-foreground/20">
                  <Lock className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">No LinkedIn Credentials</h3>
                  <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
                    Add your first LinkedIn account to start managing campaigns. Your credentials are securely encrypted and never shared.
                  </p>
                  <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
                    <DialogTrigger asChild>
                      <Button>
                        <Plus className="h-4 w-4 mr-2" />
                        Add Your First Credential
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-3xl">
                      <DialogHeader>
                        <DialogTitle>Add LinkedIn Credential</DialogTitle>
                        <DialogDescription>
                          Add a new LinkedIn account for your outreach campaigns
                        </DialogDescription>
                      </DialogHeader>
                      <LinkedInCredentialForm 
                        onSuccess={() => {
                          setIsAddDialogOpen(false)
                          handleLinkedInCredentialsUpdate()
                        }}
                        onCancel={() => setIsAddDialogOpen(false)}
                      />
                    </DialogContent>
                  </Dialog>
                </div>
              ) : (
                <div className="space-y-4">
                  <h4 className="font-medium">{linkedinCredentials.length} Stored {linkedinCredentials.length === 1 ? 'Credential' : 'Credentials'}</h4>
                  {linkedinCredentials.map(cred => (
                    <LinkedInCredentialCard 
                      key={cred.id} 
                      credential={cred}
                      onRefresh={handleLinkedInCredentialsUpdate}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Setup Guide Tab */}
        <TabsContent value="setup-guide" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-5 w-5 text-blue-600" />
                  How LinkedIn Connection Works
                </CardTitle>
                <CardDescription>
                  Understand how LinkedIn credentials work in OpenOutreach
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                    1
                  </div>
                  <div>
                    <h4 className="font-medium text-blue-900 dark:text-blue-100">Add Your Credentials</h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                      Enter your LinkedIn email and password. We use these to authenticate on your behalf.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                    2
                  </div>
                  <div>
                    <h4 className="font-medium text-blue-900 dark:text-blue-100">Credentials Are Encrypted</h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                      Your credentials are encrypted with AES-256 and stored securely.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                    3
                  </div>
                  <div>
                    <h4 className="font-medium text-blue-900 dark:text-blue-100">Manage Multiple Accounts</h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                      Add multiple LinkedIn accounts to rotate between them for your campaigns.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-green-600" />
                  Security & Best Practices
                </CardTitle>
                <CardDescription>
                  Keep your LinkedIn account secure
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-start gap-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-100 dark:border-green-800">
                  <Icons.Shield className="h-5 w-5 text-green-700 dark:text-green-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-green-900 dark:text-green-100">AES-256 Encryption</h4>
                    <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                      All credentials are encrypted at rest using industry-standard encryption.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-100 dark:border-green-800">
                  <Icons.Shield className="h-5 w-5 text-green-700 dark:text-green-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-green-900 dark:text-green-100">Never Shared</h4>
                    <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                      Your credentials are never shared with third parties.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-100 dark:border-green-800">
                  <Icons.Shield className="h-5 w-5 text-green-700 dark:text-green-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-green-900 dark:text-green-100">Health Monitoring</h4>
                    <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                      We monitor credential health and notify you of any issues.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Setup Steps */}
          <Card>
            <CardHeader>
              <CardTitle>Step-by-Step Setup</CardTitle>
              <CardDescription>
                Follow these steps to configure LinkedIn for your campaigns
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                {/* Method 1: Direct Credentials */}
                <div className="border rounded-lg p-6 hover:border-blue-300 transition-colors">
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-lg">
                      1
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-medium">Add LinkedIn Credentials</h3>
                      <p className="text-muted-foreground mt-1 mb-4">
                        The simplest way to get started. Add your LinkedIn email and password directly.
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline" className="bg-green-950/30 text-green-400 border-green-800/50 dark:bg-green-900/20 dark:border-green-800/50">
                          <CheckCircle className="mr-1 h-3 w-3" /> Easy Setup
                        </Badge>
                        <Badge variant="outline" className="bg-green-950/30 text-green-400 border-green-800/50 dark:bg-green-900/20 dark:border-green-800/50">
                          <CheckCircle className="mr-1 h-3 w-3" /> No Browser Required
                        </Badge>
                        <Badge variant="outline" className="bg-amber-950/30 text-amber-400 border-amber-800/50 dark:bg-amber-900/20 dark:border-amber-800/50">
                          <AlertCircle className="mr-1 h-3 w-3" /> Password Required
                        </Badge>
                      </div>
                      <div className="mt-4 pt-4 border-t">
                        <p className="text-sm text-muted-foreground mb-3">What you need:</p>
                        <ul className="space-y-1 text-sm">
                          <li className="flex items-start gap-2">
                            <Icons.CheckCircle className="h-4 w-4 text-green-400 flex-shrink-0 mt-0.5" />
                            <span>A LinkedIn account</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <Icons.CheckCircle className="h-4 w-4 text-green-400 flex-shrink-0 mt-0.5" />
                            <span>Your LinkedIn email and password</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Method 2: Cookie Authentication */}
                <div className="border rounded-lg p-6 hover:border-blue-300 transition-colors">
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-lg">
                      2
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-medium">Get LinkedIn Session Cookies</h3>
                      <p className="text-muted-foreground mt-1 mb-4">
                        Advanced method for those who prefer not to enter their password.
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline" className="bg-green-950/30 text-green-400 border-green-800/50 dark:bg-green-900/20 dark:border-green-800/50">
                          <CheckCircle className="mr-1 h-3 w-3" /> No Password Needed
                        </Badge>
                        <Badge variant="outline" className="bg-amber-950/30 text-amber-400 border-amber-800/50 dark:bg-amber-900/20 dark:border-amber-800/50">
                          <AlertCircle className="mr-1 h-3 w-3" /> Browser Required
                        </Badge>
                        <Badge variant="outline" className="bg-amber-950/30 text-amber-400 border-amber-800/50 dark:bg-amber-900/20 dark:border-amber-800/50">
                          <AlertCircle className="mr-1 h-3 w-3" /> More Complex
                        </Badge>
                      </div>
                      <div className="mt-4 pt-4 border-t">
                        <Button 
                          variant="outline"
                          onClick={() => setShowCookieInstructions(true)}
                          className="w-full md:w-auto"
                        >
                          <Icons.ListTodo className="mr-2 h-4 w-4" />
                          View Cookie Instructions
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <Alert className="bg-amber-950/30 border-amber-900/50 dark:bg-amber-900/20 dark:border-amber-800/50">
                <AlertCircle className="h-5 w-5 text-amber-400" />
                <h4 className="font-medium text-amber-400 dark:text-amber-300">Important</h4>
                <p className="text-sm text-amber-400 dark:text-amber-300 mt-1">
                  Both methods are secure. Choose the one that best fits your comfort level.
                  Once credentials are added, the system will automatically verify them.
                </p>
              </Alert>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Cookie Instructions Dialog */}
      <Dialog open={showCookieInstructions} onOpenChange={setShowCookieInstructions}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>How to Get LinkedIn Session Cookies</DialogTitle>
            <DialogDescription>
              Follow these steps to extract your LinkedIn session cookies
            </DialogDescription>
          </DialogHeader>
          
          {instructions.instructions && (
            <div className="space-y-6">
              {instructions.instructions.steps.map((step) => (
                <div key={step.step} className="space-y-2">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-zinc-800 text-zinc-100 font-semibold text-sm">
                      {step.step}
                    </div>
                    <h4 className="font-medium">{step.title}</h4>
                  </div>
                  <p className="text-sm text-muted-foreground ml-11">{step.description}</p>
                  {step.note && (
                    <div className="ml-11 p-2 bg-amber-950/30 border border-amber-900/50 rounded text-sm text-amber-400 dark:bg-amber-900/20 dark:border-amber-800/50">
                      <Icons.AlertCircle className="h-4 w-4 inline mr-2 text-amber-400" />
                      {step.note}
                    </div>
                  )}
                </div>
              ))}

              {instructions.instructions.alternative_method && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <h4 className="font-medium flex items-center">
                      <Icons.Globe className="mr-2 h-4 w-4" />
                      {instructions.instructions.alternative_method.title}
                    </h4>
                    <p className="text-sm text-muted-foreground">
                      {instructions.instructions.alternative_method.description}
                    </p>
                    <ol className="list-decimal list-inside space-y-1 ml-5 text-sm">
                      {instructions.instructions.alternative_method.steps.map((s, idx) => (
                        <li key={idx}>{s}</li>
                      ))}
                    </ol>
                  </div>
                </>
              )}

              {instructions.instructions.security_note && (
                <Alert className="border-amber-900/50 bg-amber-950/30 dark:border-amber-800/50 dark:bg-amber-900/20">
                  <Icons.Lock className="h-4 w-4 text-amber-400" />
                  <AlertDescription className="text-amber-400 dark:text-amber-300">
                    {instructions.instructions.security_note}
                  </AlertDescription>
                </Alert>
              )}

              {instructions.instructions.verification && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Icons.CheckCircle className="h-5 w-5 text-green-400" />
                    <h4 className="font-medium text-zinc-100">{instructions.instructions.verification.title}</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {instructions.instructions.verification.description}
                  </p>
                  <div className="p-2 bg-green-950/30 border border-green-900/50 rounded text-sm text-green-400 dark:bg-green-900/20 dark:border-green-800/50">
                    <Icons.CheckCircle className="h-4 w-4 inline mr-2 text-green-400" />
                    {instructions.instructions.verification.success}
                  </div>
                </div>
              )}
            </div>
          )}
          
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setShowCookieInstructions(false)}>
              Close
            </Button>
            <Button onClick={() => {
              setShowCookieInstructions(false)
              handleStartSetup()
            }}>
              Go to Credentials Setup
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default LinkedInConnectionTab