'use client'

import { useState, useEffect } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Campaign } from '@/lib/types/components'

const formSchema = z.object({
  name: z.string().min(3, 'Name must be at least 3 characters').max(100, 'Name is too long'),
  description: z.string().max(500, 'Description is too long').optional(),
  productDocs: z.string().url('Must be a valid URL').optional().or(z.literal('')),
  campaignObjective: z.string().max(200, 'Objective is too long').optional(),
  bookingLink: z.string().url('Must be a valid URL').optional().or(z.literal('')),
  isFreemium: z.boolean(),
  velocity: z.number().min(1).max(100),
  cooldownMinutes: z.number().min(1).max(1440),
  status: z.enum(['draft', 'active', 'paused']),
})

type FormValues = z.infer<typeof formSchema>

interface CampaignFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  campaign?: Campaign | null
  onSubmit: (data: Partial<Campaign>) => void
  isEditing?: boolean
}

export function CampaignForm({
  open,
  onOpenChange,
  campaign,
  onSubmit,
  isEditing = false,
}: CampaignFormProps) {
  const [loading, setLoading] = useState(false)

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: undefined,
      productDocs: undefined,
      campaignObjective: undefined,
      bookingLink: undefined,
      isFreemium: false,
      velocity: 10,
      cooldownMinutes: 60,
      status: 'draft',
    },
  })

  useEffect(() => {
    if (campaign) {
      form.reset({
        name: campaign.name,
        description: campaign.description || undefined,
        productDocs: campaign.productDocs || undefined,
        campaignObjective: campaign.campaignObjective || undefined,
        bookingLink: campaign.bookingLink || undefined,
        isFreemium: campaign.isFreemium,
        velocity: campaign.velocity,
        cooldownMinutes: campaign.cooldownMinutes,
        status: campaign.status as 'draft' | 'active' | 'paused',
      })
    } else {
      form.reset({
        name: '',
        description: undefined,
        productDocs: undefined,
        campaignObjective: undefined,
        bookingLink: undefined,
        isFreemium: false,
        velocity: 10,
        cooldownMinutes: 60,
        status: 'draft',
      })
    }
  }, [campaign, form])

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      await onSubmit(values)
      form.reset()
      onOpenChange(false)
    } catch (error) {
      console.error('Error submitting form:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Campaign' : 'Create New Campaign'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update your campaign details and settings.'
              : 'Create a new outreach campaign to start connecting with leads.'}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            <Tabs defaultValue="basic" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="basic">Basic Info</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
                <TabsTrigger value="advanced">Advanced</TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Campaign Name</FormLabel>
                      <FormControl>
                        <Input placeholder="Enter campaign name" {...field} />
                      </FormControl>
                      <FormDescription>
                        A descriptive name for your campaign
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Description</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Describe what this campaign is about..."
                          className="resize-none"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        Optional: Brief description of the campaign
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="campaignObjective"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Campaign Objective</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="What are you trying to achieve?"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        The primary goal of this campaign
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </TabsContent>

              <TabsContent value="settings" className="space-y-4">
                <FormField
                  control={form.control}
                  name="status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Status</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select status" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="draft">Draft</SelectItem>
                          <SelectItem value="active">Active</SelectItem>
                          <SelectItem value="paused">Paused</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        Set campaign status
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="velocity"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Daily Velocity</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min="1"
                            max="100"
                            placeholder="10"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Max daily connects
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="cooldownMinutes"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Cooldown (minutes)</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min="1"
                            max="1440"
                            placeholder="60"
                            {...field}
                          />
                        </FormControl>
                        <FormDescription>
                          Between actions
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="isFreemium"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">Freemium Model</FormLabel>
                        <FormDescription>
                          Offers free trial/product
                        </FormDescription>
                      </div>
                      <FormControl>
                        <Switch
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </TabsContent>

              <TabsContent value="advanced" className="space-y-4">
                <FormField
                  control={form.control}
                  name="productDocs"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Product Documentation URL</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="https://example.com/docs"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        Link to product documentation
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="bookingLink"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Booking Link</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="https://calendly.com/your-link"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        Meeting booking link
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </TabsContent>
            </Tabs>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? 'Saving...' : isEditing ? 'Update Campaign' : 'Create Campaign'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}