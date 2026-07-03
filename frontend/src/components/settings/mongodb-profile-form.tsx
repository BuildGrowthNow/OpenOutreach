'use client'

import { useState, useEffect, useCallback } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Icons } from '@/lib/types/components'
import { getMongoUserProfile, updateMongoUserProfile } from '@/lib/api/dashboard'

const profileSchema = z.object({
  username: z.string().min(2).max(50),
  campaign: z.string().min(2).max(100),
  email: z.string().email().optional().or(z.string().max(0)),
  first_name: z.string().max(100).optional().or(z.string().max(0)),
  last_name: z.string().max(100).optional().or(z.string().max(0))
})

type ProfileFormValues = z.infer<typeof profileSchema>

interface MongoDbProfileFormProps {
  onSuccess?: () => void
}

export default function MongoDbProfileForm({ onSuccess }: MongoDbProfileFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      username: '',
      campaign: '',
      email: '',
      first_name: '',
      last_name: ''
    }
  })

  const loadProfile = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      const response = await getMongoUserProfile()
      if (response.data) {
        form.reset({
          username: response.data.username || '',
          campaign: response.data.campaign || '',
          email: response.data.email || '',
          first_name: response.data.first_name || '',
          last_name: response.data.last_name || ''
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile')
    } finally {
      setIsLoading(false)
    }
  }, [form])

  useEffect(() => {
    loadProfile()
  }, [loadProfile])

  const onSubmit = async (values: ProfileFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      setSuccess(false)

      // Update MongoDB profile
      const response = await updateMongoUserProfile(values)

      if (response.data) {
        setSuccess(true)
        if (onSuccess) onSuccess()
        setTimeout(() => setSuccess(false), 3000)
      } else {
        setError('Failed to update profile')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Use watch() outside JSX to avoid React Compiler warning
  const username = form.watch('username')
  const campaign = form.watch('campaign')
  const firstName = form.watch('first_name')
  const lastName = form.watch('last_name')

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-12">
        <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert>
          <Icons.CheckCircle className="h-4 w-4" />
          <AlertDescription>Profile updated successfully!</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <div className="space-y-4">
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>LinkedIn Username</FormLabel>
                      <FormControl>
                        <div className="flex">
                          <div className="flex items-center justify-center px-3 border border-r-0 rounded-l-md bg-zinc-900 dark:bg-zinc-800">
                            <span className="text-zinc-500 dark:text-zinc-400">@</span>
                          </div>
                          <Input
                            placeholder="username"
                            {...field}
                            className="rounded-l-none"
                          />
                        </div>
                      </FormControl>
                      <FormDescription>
                        Your LinkedIn profile username (without @ symbol)
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="campaign"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Campaign</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="e.g., Tech Sales Outreach 2024"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        Name of your current LinkedIn outreach campaign
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="first_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>First Name</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="First name"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="last_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Last Name</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="Last name"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="email@example.com"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="border-t pt-6">
                <div className="flex justify-end space-x-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      form.reset()
                      loadProfile()
                    }}
                    disabled={isSubmitting}
                  >
                    Reset
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <>
                        <Icons.RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                        Updating...
                      </>
                    ) : (
                      <>
                        <Icons.CheckCircle className="h-4 w-4 mr-2" />
                        Update Profile
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </form>
          </Form>
        </div>

        <div className="space-y-4">
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <h3 className="font-semibold">Profile Preview</h3>
                <div className="space-y-3">
                  <div className="flex items-center space-x-3">
                    <div className="h-10 w-10 rounded-full bg-zinc-800 dark:bg-zinc-700 flex items-center justify-center">
                      <Icons.User className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />
                    </div>
                    <div>
                      <p className="font-medium text-zinc-100">
                        @{username || 'username'}
                      </p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        {(firstName || lastName) ? `${firstName} ${lastName}` : 'No name set'}
                      </p>
                    </div>
                  </div>
                  
                  <div className="border-t pt-3">
                    <div className="text-sm">
                      <div className="flex justify-between mb-1">
                        <span className="text-zinc-500 dark:text-zinc-400">Campaign:</span>
                        <span className="font-medium text-zinc-100">
                          {campaign || 'No campaign set'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500 dark:text-zinc-400">Profile Status:</span>
                        <span className="font-medium text-green-500 dark:text-green-400">
                          Active
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="space-y-3">
                <h3 className="font-semibold flex items-center dark:text-zinc-200">
                  <Icons.Database className="h-4 w-4 text-blue-500 mr-2 dark:text-blue-500" />
                  MongoDB Storage
                </h3>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Your profile data is securely stored in MongoDB for faster access and better scalability.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}