'use client'

import { useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/lib/types/components'
import { 
  LinkedInCredentials, 
  verifyLinkedInCredentials, 
  deleteLinkedInCredentials,
  rotateLinkedInCredentials,
  getLinkedInCredentialsHealth,
  getLinkedInCredentialsLogs,
  LinkedInCredentialsLogsResponse
} from '@/lib/api/dashboard'
import { useToast } from '@/components/ui/use-toast'
import LinkedInCredentialForm from './linkedin-credential-form'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { LinkedInCredentialsHealth } from '@/lib/api/dashboard'

interface LinkedInCredentialCardProps {
  credential: LinkedInCredentials
  onRefresh: () => void
}

export default function LinkedInCredentialCard({ credential, onRefresh }: LinkedInCredentialCardProps) {
  const [isVerifying, setIsVerifying] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isRotating, setIsRotating] = useState(false)
  const [showHealthDetails, setShowHealthDetails] = useState(false)
  const [healthData, setHealthData] = useState<LinkedInCredentialsHealth['health_status'] | null>(null)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showLogsDialog, setShowLogsDialog] = useState(false)
  const [logsData, setLogsData] = useState<LinkedInCredentialsLogsResponse['logs'] | null>(null)
  const [isLoadingLogs, setIsLoadingLogs] = useState(false)
  const { toast } = useToast()

  const handleVerify = async () => {
    try {
      setIsVerifying(true)
      const response = await verifyLinkedInCredentials(credential.id)
      
      if (response.data) {
        toast({
          title: 'Success',
          description: 'Credentials verified successfully',
        })
        onRefresh()
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to verify credentials',
          variant: 'destructive',
        })
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'An unexpected error occurred',
        variant: 'destructive',
      })
    } finally {
      setIsVerifying(false)
    }
  }

  const handleRotate = async () => {
    try {
      setIsRotating(true)
      const response = await rotateLinkedInCredentials(credential.id)
      
      if (response.data) {
        toast({
          title: 'Success',
          description: 'Credentials rotated successfully. A backup has been created.',
        })
        onRefresh()
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to rotate credentials',
          variant: 'destructive',
        })
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'An unexpected error occurred',
        variant: 'destructive',
      })
    } finally {
      setIsRotating(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to deactivate this credential? This will prevent it from being used in campaigns.`)) {
      return
    }

    try {
      setIsDeleting(true)
      const response = await deleteLinkedInCredentials(credential.id)
      
      if (response.data) {
        toast({
          title: 'Success',
          description: 'Credential deactivated successfully',
        })
        onRefresh()
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
    } finally {
      setIsDeleting(false)
    }
  }

  const handleLoadHealth = async () => {
    try {
      const response = await getLinkedInCredentialsHealth(credential.id)
      if (response.data) {
        setHealthData(response.data.health_status)
        setShowHealthDetails(true)
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Failed to load health details',
        variant: 'destructive',
      })
    }
  }

  const handleLoadLogs = async () => {
    try {
      setIsLoadingLogs(true)
      const response = await getLinkedInCredentialsLogs(credential.id)
      if (response.data) {
        setLogsData(response.data.logs)
        setShowLogsDialog(true)
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to load logs',
          variant: 'destructive',
        })
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Failed to load logs',
        variant: 'destructive',
      })
    } finally {
      setIsLoadingLogs(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-500'
      case 'invalid': return 'bg-red-500'
      case 'expired': return 'bg-yellow-500'
      case 'locked': return 'bg-gray-500'
      case 'backup': return 'bg-blue-500'
      default: return 'bg-gray-500'
    }
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex flex-col space-y-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-4">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center ${credential.is_primary ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground'}`}>
                <Icons.User className="h-6 w-6" />
              </div>
              <div>
                <div className="flex items-center space-x-2 mb-1">
                  <span className="font-medium">@{credential.username}</span>
                  {credential.is_primary && (
                    <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded-full">Primary</span>
                  )}
                  {credential.is_backup && (
                    <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">Backup</span>
                  )}
                </div>
                <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                  <Icons.Mail className="h-3 w-3" />
                  <span>{credential.public_email}</span>
                  <span className="px-2">•</span>
                  <span className={`w-2 h-2 rounded-full ${getStatusColor(credential.status)}`} />
                  <span className="capitalize">{credential.status}</span>
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium">
                {credential.health_status.health_score}/100 Health Score
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {credential.usage_count} actions used
              </div>
            </div>
          </div>

          {showHealthDetails && healthData && (
            <div className="bg-muted/50 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Days Until Expiry:</span>
                <span>{healthData.days_until_expiry !== null ? healthData.days_until_expiry : 'Unknown'}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Days Since Rotation:</span>
                <span>{healthData.days_since_rotation}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Verification Failures:</span>
                <span className={healthData.verification_failures > 0 ? 'text-red-600' : 'text-green-600'}>
                  {healthData.verification_failures}
                </span>
              </div>
              {healthData.last_verified && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Last Verified:</span>
                  <span>{new Date(healthData.last_verified).toLocaleDateString()}</span>
                </div>
              )}
              {healthData.last_used && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Last Used:</span>
                  <span>{new Date(healthData.last_used).toLocaleDateString()}</span>
                </div>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2 mt-2">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={handleVerify}
              disabled={isVerifying || credential.status === 'active'}
            >
              {credential.status === 'active' ? (
                <>
                  <Icons.Check className="h-3 w-3 mr-2" />
                  Verified
                </>
              ) : (
                <>
                  <Icons.RefreshCw className="h-3 w-3 mr-2" />
                  Verify
                </>
              )}
            </Button>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={handleRotate}
              disabled={isRotating}
            >
              <Icons.RefreshCw className="h-3 w-3 mr-2" />
              Rotate
            </Button>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setShowEditDialog(true)}
              disabled={isRotating || isVerifying || isDeleting}
            >
              <Icons.Edit className="h-3 w-3 mr-2" />
              Edit
            </Button>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={handleLoadHealth}
              disabled={isRotating}
            >
              <Icons.Activity className="h-3 w-3 mr-2" />
              {showHealthDetails ? 'Hide Details' : 'View Details'}
            </Button>
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={handleLoadLogs}
              disabled={isLoadingLogs || isRotating}
            >
              <Icons.FileText className="h-3 w-3 mr-2" />
              {isLoadingLogs ? 'Loading...' : 'View Logs'}
            </Button>
            
            <Button 
              variant="destructive" 
              size="sm" 
              onClick={handleDelete}
              disabled={isDeleting}
            >
              <Icons.Trash2 className="h-3 w-3 mr-2" />
              Deactivate
            </Button>
          </div>
        </div>

        <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit LinkedIn Credential</DialogTitle>
              <DialogDescription>
                Update your LinkedIn account credentials
              </DialogDescription>
            </DialogHeader>
            <LinkedInCredentialForm 
              initialData={credential}
              onSuccess={() => {
                setShowEditDialog(false)
                onRefresh()
                toast({
                  title: 'Success',
                  description: 'Credential updated successfully',
                })
              }}
              onCancel={() => setShowEditDialog(false)}
            />
          </DialogContent>
        </Dialog>

        <Dialog open={showLogsDialog} onOpenChange={setShowLogsDialog}>
          <DialogContent className="max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Credential Audit Logs</DialogTitle>
              <DialogDescription>
                History of actions performed on this credential
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
              {logsData && logsData.length > 0 ? (
                logsData.map((log) => (
                  <div key={log.id} className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="font-medium capitalize">{log.action.replace('_', ' ')}</div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>
                    {log.details && Object.keys(log.details).length > 0 && (
                      <div className="bg-muted/50 rounded p-2 text-xs font-mono">
                        <pre className="whitespace-pre-wrap text-muted-foreground">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      </div>
                    )}
                    {log.ip_address && (
                      <div className="text-xs text-muted-foreground">
                        IP: {log.ip_address}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-center text-muted-foreground py-8">
                  <Icons.FileText className="h-10 w-10 mx-auto mb-2 opacity-20" />
                  <p>No logs found for this credential</p>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  )
}
