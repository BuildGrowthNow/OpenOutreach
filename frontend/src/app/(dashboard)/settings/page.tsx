'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { getSettings, type Settings } from '@/lib/api/dashboard'
import ProfileForm from '@/components/settings/profile-form'
import RateLimitForm from '@/components/settings/rate-limit-form'
import LinkedInCredentialForm from '@/components/settings/linkedin-credential-form'
import LinkedInCredentialCard from '@/components/settings/linkedin-credential-card'
import { Settings as SettingsIcon } from 'lucide-react'
import { 
  getLinkedInCredentials, 
  createLinkedInCredentials, 
  updateLinkedInCredentials,
  deleteLinkedInCredentials,
  type LinkedInCredentials 
} from '@/lib/api/dashboard'
import { useToast } from '@/components/ui/use-toast'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [linkedinCredentials, setLinkedinCredentials] = useState<LinkedInCredentials[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'rate-limits' | 'profile' | 'linkedin-credentials' | 'system'>('rate-limits')
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [editingCredential, setEditingCredential] = useState<LinkedInCredentials | null>(null)
  const { toast } = useToast()

  const loadLinkedInCredentials = useCallback(async () => {
    try {
      const response = await getLinkedInCredentials()
      if (response.data) {
        setLinkedinCredentials(response.data.credentials || [])
      }
    } catch (err) {
      // Fail silently - credentials may not exist yet
      console.debug('Failed to load LinkedIn credentials:', err)
    }
  }, [])

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true)
      const response = await getSettings()
      if (response.data) {
        setSettings(response.data)
      } else {
        setError('Failed to load settings')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      await loadSettings()
      await loadLinkedInCredentials()
    })()
  }, [loadSettings, loadLinkedInCredentials])

  const handleSettingsUpdate = () => {
    loadSettings()
  }

  const handleLinkedInCredentialsUpdate = () => {
    loadLinkedInCredentials()
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
        <div className="grid gap-6">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <Icons.AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Failed to load settings: {error}
          <Button variant="outline" className="ml-4" onClick={loadSettings}>
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
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Configure system settings, rate limits, and your profile
          </p>
        </div>
        <Button variant="outline" onClick={loadSettings}>
          <Icons.RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Tabs defaultValue="rate-limits" className="space-y-6">
        <TabsList>
          <TabsTrigger value="rate-limits">
            <Icons.SlidersHorizontal className="h-4 w-4 mr-2" />
            Rate Limits
          </TabsTrigger>
           <TabsTrigger value="profile">
             <Icons.User className="h-4 w-4 mr-2" />
             Profile
           </TabsTrigger>
            <TabsTrigger value="linkedin-credentials">
               <Icons.Link className="h-4 w-4 mr-2" />
              LinkedIn Credentials
            </TabsTrigger>
            <TabsTrigger value="system">
              <SettingsIcon className="h-4 w-4 mr-2" />
              System Info
            </TabsTrigger>
          </TabsList>

        <TabsContent value="rate-limits" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Connection Rate Limits</CardTitle>
              <CardDescription>
                Configure daily limits for connection requests and follow-up messages
              </CardDescription>
            </CardHeader>
            <CardContent>
              {settings && (
                <RateLimitForm 
                  initialData={settings.rate_limits}
                  onSuccess={handleSettingsUpdate}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="profile" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Profile Settings</CardTitle>
              <CardDescription>
                Update your LinkedIn profile information and campaign preferences
              </CardDescription>
            </CardHeader>
            <CardContent>
              {settings && (
                <ProfileForm 
                  initialData={settings.linkedin_profile}
                  onSuccess={handleSettingsUpdate}
                />
              )}
            </CardContent>
          </Card>
         </TabsContent>

         <TabsContent value="linkedin-credentials" className="space-y-6">
           <Card>
             <CardHeader>
               <CardTitle>LinkedIn Credentials Management</CardTitle>
               <CardDescription>
                 Securely stored and managed LinkedIn account credentials
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
                         <Icons.Plus className="h-4 w-4 mr-2" />
                         Add Credential
                       </Button>
                     </DialogTrigger>
                     <DialogContent>
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
                 <div className="text-center py-12 bg-muted rounded-lg">
                   <Icons.Lock className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                   <h3 className="text-lg font-medium mb-2">No LinkedIn Credentials</h3>
                   <p className="text-sm text-muted-foreground mb-4">
                     Add your first LinkedIn account to start managing campaigns
                   </p>
                   <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
                     <DialogTrigger asChild>
                       <Button>
                         <Icons.Plus className="h-4 w-4 mr-2" />
                         Add Your First Credential
                       </Button>
                     </DialogTrigger>
                     <DialogContent>
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

        <TabsContent value="system" className="space-y-6">
         <Card>
           <CardHeader>
             <CardTitle>System Configuration</CardTitle>
             <CardDescription>
               Current system configuration and LLM settings
             </CardDescription>
           </CardHeader>
           <CardContent className="space-y-4">
             {settings && (
               <>
                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                   <div>
                     <h3 className="font-semibold mb-2">LLM Configuration</h3>
                     <div className="space-y-2">
                       <div className="flex justify-between">
                         <span className="text-muted-foreground">Provider:</span>
                         <span className="font-medium">{settings.llm.provider}</span>
                       </div>
                       <div className="flex justify-between">
                         <span className="text-muted-foreground">Model:</span>
                         <span className="font-medium">{settings.llm.model}</span>
                       </div>
                       <div className="flex justify-between">
                         <span className="text-muted-foreground">API Base:</span>
                         <span className="font-medium truncate">{settings.llm.api_base}</span>
                       </div>
                     </div>
                   </div>
                   
                   <div>
                     <h3 className="font-semibold mb-2">LinkedIn Profile</h3>
                     <div className="space-y-2">
                       <div className="flex justify-between">
                         <span className="text-muted-foreground">Username:</span>
                         <span className="font-medium">@{settings.linkedin_profile.username}</span>
                       </div>
                       <div className="flex justify-between">
                         <span className="text-muted-foreground">Campaign:</span>
                         <span className="font-medium">{settings.linkedin_profile.campaign}</span>
                       </div>
                     </div>
                   </div>
                 </div>

                 <div>
                   <h3 className="font-semibold mb-2">Current Rate Limits</h3>
                   <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                     <Card>
                       <CardContent className="pt-6">
                         <div className="text-center">
                           <div className="text-2xl font-bold">
                             0 / {settings.rate_limits.daily_connection_limit}
                           </div>
                           <p className="text-sm text-muted-foreground">Connections Today</p>
                         </div>
                       </CardContent>
                     </Card>
                     <Card>
                       <CardContent className="pt-6">
                         <div className="text-center">
                           <div className="text-2xl font-bold">
                             0 / {settings.rate_limits.daily_follow_up_limit}
                           </div>
                           <p className="text-sm text-muted-foreground">Follow-ups Today</p>
                         </div>
                       </CardContent>
                     </Card>
                     <Card>
                       <CardContent className="pt-6">
                         <div className="text-center">
                           <div className="text-2xl font-bold">
                             {settings.rate_limits.velocity}
                           </div>
                           <p className="text-sm text-muted-foreground">Velocity</p>
                         </div>
                       </CardContent>
                     </Card>
                     <Card>
                       <CardContent className="pt-6">
                         <div className="text-center">
                           <div className="text-2xl font-bold">
                             {settings.rate_limits.cooldown_minutes} min
                           </div>
                           <p className="text-sm text-muted-foreground">Cooldown</p>
                         </div>
                       </CardContent>
                     </Card>
                   </div>
                 </div>
               </>
             )}
           </CardContent>
         </Card>
       </TabsContent>
      </Tabs>
    </div>
  )
}
