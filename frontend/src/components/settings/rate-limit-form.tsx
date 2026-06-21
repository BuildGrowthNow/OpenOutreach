'use client'

import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Icons } from '@/lib/types/components'
import { updateSettings } from '@/lib/api/dashboard'
// Backend rate limit shape (snake_case)
interface BackendRateLimits {
  daily_connection_limit: number
  daily_follow_up_limit: number
  velocity: number
  cooldown_minutes: number
}

const rateLimitSchema = z.object({
  dailyConnectionLimit: z.number().min(1).max(100),
  dailyFollowUpLimit: z.number().min(1).max(100)
})

type RateLimitFormValues = z.infer<typeof rateLimitSchema>

interface RateLimitFormProps {
  initialData: BackendRateLimits
  onSuccess?: () => void
}

export default function RateLimitForm({ initialData, onSuccess }: RateLimitFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const form = useForm<RateLimitFormValues>({
    resolver: zodResolver(rateLimitSchema),
    defaultValues: {
      dailyConnectionLimit: initialData?.daily_connection_limit || 30,
      dailyFollowUpLimit: initialData?.daily_follow_up_limit || 25
    }
  })

  const onSubmit = async (values: RateLimitFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      setSuccess(false)

      const response = await updateSettings({
        rate_limits: {
          daily_connection_limit: values.dailyConnectionLimit,
          daily_follow_up_limit: values.dailyFollowUpLimit
        }
      })

      if (response.data) {
        setSuccess(true)
        if (onSuccess) onSuccess()
        setTimeout(() => setSuccess(false), 3000)
      } else {
        setError('Failed to update rate limits')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  const connectLimit = form.watch('dailyConnectionLimit')
  const followUpLimit = form.watch('dailyFollowUpLimit')

  const safetyLevel = () => {
    if (connectLimit <= 20 && followUpLimit <= 15) return { level: 'Very Safe', color: 'text-green-600', bg: 'bg-green-100' }
    if (connectLimit <= 30 && followUpLimit <= 25) return { level: 'Safe', color: 'text-green-500', bg: 'bg-green-50' }
    if (connectLimit <= 50 && followUpLimit <= 40) return { level: 'Moderate', color: 'text-yellow-600', bg: 'bg-yellow-100' }
    if (connectLimit <= 70 && followUpLimit <= 60) return { level: 'Risky', color: 'text-orange-600', bg: 'bg-orange-100' }
    return { level: 'High Risk', color: 'text-red-600', bg: 'bg-red-100' }
  }

  const safety = safetyLevel()

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        {error && (
          <Alert variant="destructive">
            <Icons.AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert>
            <Icons.CheckCircle className="h-4 w-4" />
            <AlertDescription>Rate limits updated successfully!</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="p-4 border rounded-lg bg-gray-50">
              <h3 className="font-semibold mb-2">Safety Assessment</h3>
              <div className="flex items-center space-x-2">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${safety.bg} ${safety.color}`}>
                  {safety.level}
                </span>
                 <span className="text-sm text-gray-600">
                   Connection Limit: {connectLimit} - Follow-up Limit: {followUpLimit}
                 </span>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Based on LinkedIn recommended limits to avoid account restrictions
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="p-4 border rounded-lg bg-blue-50">
              <h3 className="font-semibold mb-2 flex items-center">
                <Icons.AlertTriangle className="h-4 w-4 text-blue-600 mr-2" />
                LinkedIn Guidelines
              </h3>
              <ul className="text-sm space-y-1">
                <li className="flex items-start">
                  <Icons.CheckCircle className="h-3 w-3 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                  <span>Recommended: 20-30 connections per day</span>
                </li>
                <li className="flex items-start">
                  <Icons.CheckCircle className="h-3 w-3 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                  <span>Weekly maximum: 70 connections</span>
                </li>
                <li className="flex items-start">
                  <Icons.CheckCircle className="h-3 w-3 text-green-500 mt-0.5 mr-2 flex-shrink-0" />
                  <span>Space out activities throughout the day</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <FormField
            control={form.control}
            name="dailyConnectionLimit"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Daily Connection Limit</FormLabel>
                <div className="space-y-4">
                  <FormControl>
                    <div className="flex items-center space-x-4">
                      <Slider
                        min={1}
                        max={100}
                        step={1}
                        value={[field.value]}
                        onValueChange={(value) => field.onChange(value[0])}
                        className="flex-1"
                      />
                    <div className="w-16">
                      <Input
                        type="number"
                        min={1}
                        max={100}
                        value={field.value}
                        onChange={(e) => field.onChange(parseInt(e.target.value) || 0)}
                        className="text-center"
                      />
                    </div>
                    </div>
                  </FormControl>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Low Risk ({field.value <= 20 ? 'OK' : '->'})</span>
                    <span>Moderate Risk ({field.value <= 50 ? 'OK' : '->'})</span>
                    <span>High Risk ({field.value > 50 ? '!' : '->'})</span>
                  </div>
                </div>
                <FormDescription>
                  Maximum connection requests per day
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="dailyFollowUpLimit"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Daily Follow-up Limit</FormLabel>
                <div className="space-y-4">
                  <FormControl>
                    <div className="flex items-center space-x-4">
                      <Slider
                        min={1}
                        max={100}
                        step={1}
                        value={[field.value]}
                        onValueChange={(value) => field.onChange(value[0])}
                        className="flex-1"
                      />
                      <div className="w-16">
                        <Input
                          type="number"
                          min={1}
                          max={100}
                          value={field.value}
                          onChange={(e) => field.onChange(parseInt(e.target.value) || 0)}
                          className="text-center"
                        />
                      </div>
                    </div>
                  </FormControl>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Low Risk ({field.value <= 15 ? 'OK' : '->'})</span>
                    <span>Moderate Risk ({field.value <= 40 ? 'OK' : '->'})</span>
                    <span>High Risk ({field.value > 40 ? '!' : '->'})</span>
                  </div>
                </div>
                <FormDescription>
                  Maximum follow-up messages per day
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="border-t pt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="text-center p-4 border rounded-lg">
              <div className="text-2xl font-bold">{connectLimit}</div>
              <p className="text-sm text-gray-600">Connection Limit</p>
              <p className="text-xs text-gray-500">Per day</p>
            </div>
            <div className="text-center p-4 border rounded-lg">
              <div className="text-2xl font-bold">{followUpLimit}</div>
              <p className="text-sm text-gray-600">Follow-up Limit</p>
              <p className="text-xs text-gray-500">Per day</p>
            </div>
            <div className="text-center p-4 border rounded-lg">
              <div className="text-2xl font-bold">{connectLimit + followUpLimit}</div>
              <p className="text-sm text-gray-600">Total Actions</p>
              <p className="text-xs text-gray-500">Per day maximum</p>
            </div>
          </div>

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
                  Update Rate Limits
                </>
              )}
            </Button>
          </div>
        </div>
      </form>
    </Form>
  )
}
