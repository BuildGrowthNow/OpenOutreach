'use client'

import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Icons } from '@/lib/types/components'
import { updateSettings } from '@/lib/api/dashboard'

const profileSchema = z.object({
  username: z.string().min(2).max(50),
  campaign: z.string().min(2).max(100)
})

type ProfileFormValues = z.infer<typeof profileSchema>

interface ProfileFormProps {
  initialData: {
    username: string
    campaign: string
  }
  onSuccess?: () => void
}

export default function ProfileForm({ initialData, onSuccess }: ProfileFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      username: initialData?.username || '',
      campaign: initialData?.campaign || ''
    }
  })

  const onSubmit = async (values: ProfileFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      setSuccess(false)

      // Update settings with profile data
      const response = await updateSettings({
        linkedin_profile: {
          username: values.username,
          campaign: values.campaign
        }
      })

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
                          <div className="flex items-center justify-center px-3 border border-r-0 rounded-l-md bg-gray-50">
                            <span className="text-gray-500">@</span>
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
              </div>

              <div className="border-t pt-6">
                <div className="flex justify-end space-x-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => form.reset()}
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
                    <div className="h-10 w-10 rounded-full bg-gray-100 flex items-center justify-center">
                      <Icons.User className="h-5 w-5 text-gray-500" />
                    </div>
                    <div>
                      <p className="font-medium">@{username || 'username'}</p>
                      <p className="text-xs text-gray-500">LinkedIn Profile</p>
                    </div>
                  </div>
                  
                  <div className="border-t pt-3">
                    <div className="text-sm">
                      <div className="flex justify-between mb-1">
                        <span className="text-gray-600">Campaign:</span>
                          <span className="font-medium">{campaign || 'No campaign set'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Profile Status:</span>
                        <span className="font-medium text-green-600">Active</span>
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
                <h3 className="font-semibold flex items-center">
                  <Icons.AlertCircle className="h-4 w-4 text-blue-600 mr-2" />
                  Profile Guidelines
                </h3>
                <ul className="text-sm space-y-2">
                  <li className="flex items-start">
                    <Icons.CheckCircle className="h-3 w-3 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                    <span>Ensure your LinkedIn profile is 100% complete</span>
                  </li>
                  <li className="flex items-start">
                    <Icons.CheckCircle className="h-3 w-3 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                    <span>Use a professional profile photo</span>
                  </li>
                  <li className="flex items-start">
                    <Icons.CheckCircle className="h-3 w-3 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                    <span>Write a compelling headline and summary</span>
                  </li>
                  <li className="flex items-start">
                    <Icons.CheckCircle className="h-3 w-3 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                    <span>Keep your campaign name descriptive and relevant</span>
                  </li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}