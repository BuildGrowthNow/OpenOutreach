'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { getSettings } from '@/lib/api/dashboard'
import ProfileForm from '@/components/settings/profile-form'
import { Breadcrumb } from '@/components/layout/breadcrumb'

interface ProfileData {
  username: string
  campaign: string
}

export default function ProfilePage() {
  const [profileData, setProfileData] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true)
      const response = await getSettings()
      if (response.data) {
        setProfileData(response.data.linkedin_profile)
      } else {
        setError('Failed to load profile')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      await loadProfile()
    })()
  }, [loadProfile])

  const handleProfileUpdate = () => {
    loadProfile()
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Breadcrumb 
          items={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Settings', href: '/settings' },
            { label: 'Profile', href: '/settings/profile', isActive: true }
          ]}
        />
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
      <>
        <Breadcrumb 
          items={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Settings', href: '/settings' },
            { label: 'Profile', href: '/settings/profile', isActive: true }
          ]}
        />
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Failed to load profile: {error}
            <Button variant="outline" className="ml-4" onClick={loadProfile}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </>
    )
  }

  return (
    <div className="space-y-6">
      <Breadcrumb 
        items={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Settings', href: '/settings' },
          { label: 'Profile', href: '/settings/profile', isActive: true }
        ]}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Profile Settings</h1>
          <p className="text-muted-foreground">
            Manage your LinkedIn profile information and campaign preferences
          </p>
        </div>
        <Button variant="outline" onClick={loadProfile}>
          <Icons.RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>
                Update your LinkedIn username and campaign preferences
              </CardDescription>
            </CardHeader>
            <CardContent>
              {profileData && (
                <ProfileForm 
                  initialData={profileData}
                  onSuccess={handleProfileUpdate}
                />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Current Profile</CardTitle>
              <CardDescription>
                Your current LinkedIn profile configuration
              </CardDescription>
            </CardHeader>
            <CardContent>
              {profileData && (
                <div className="space-y-4">
                  <div className="flex items-center space-x-4">
                    <div className="h-12 w-12 rounded-full bg-gray-100 flex items-center justify-center">
                      <Icons.User className="h-6 w-6 text-gray-500" />
                    </div>
                    <div>
                      <p className="font-semibold">@{profileData.username}</p>
                      <p className="text-sm text-muted-foreground">LinkedIn Username</p>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div>
                      <p className="text-sm font-medium mb-1">Campaign</p>
                      <div className="flex items-center space-x-2">
                        <Icons.Users className="h-4 w-4 text-gray-500" />
                        <span>{profileData.campaign}</span>
                      </div>
                    </div>
                    
                    <div>
                      <p className="text-sm font-medium mb-1">Profile Status</p>
                      <div className="flex items-center">
                        <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full bg-green-500 w-3/4" />
                        </div>
                        <span className="ml-2 text-sm font-medium">75% Complete</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Profile Guidelines</CardTitle>
              <CardDescription>
                Best practices for LinkedIn profile optimization
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <h4 className="font-semibold">Profile Completeness</h4>
                <p className="text-sm text-muted-foreground">
                  Ensure your LinkedIn profile is 100% complete with:
                  Profile photo, headline, summary, experience, and education.
                </p>
              </div>
              
              <div className="space-y-2">
                <h4 className="font-semibold">Campaign Alignment</h4>
                <p className="text-sm text-muted-foreground">
                  Your campaign messaging should align with your professional
                  background and target audience for better connection rates.
                </p>
              </div>
              
              <div className="space-y-2">
                <h4 className="font-semibold">Engagement Best Practices</h4>
                <p className="text-sm text-muted-foreground">
                  Regularly engage with your connections&apos; content.
                  Post relevant industry updates to maintain profile activity.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile Analytics</CardTitle>
          <CardDescription>
            Performance metrics for your current profile configuration
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Connection Accept Rate</p>
              <p className="text-2xl font-bold">28%</p>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-green-500 w-1/4" />
              </div>
            </div>
            
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Profile Views</p>
              <p className="text-2xl font-bold">1,247</p>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 w-2/3" />
              </div>
            </div>
            
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Engagement Rate</p>
              <p className="text-2xl font-bold">12%</p>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-yellow-500 w-1/8" />
              </div>
            </div>
            
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Search Appearances</p>
              <p className="text-2xl font-bold">892</p>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-purple-500 w-3/4" />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
