'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
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
import { Icons } from '@/lib/types/components'
import { Campaign, CampaignTemplate, LinkedInSetupStatus } from '@/lib/types/components'
import { getLinkedInSetupStatus, getCampaignTemplates } from '@/lib/api/dashboard'

const formSchema = z.object({
  name: z.string().min(3, 'Name must be at least 3 characters').max(100, 'Name is too long'),
  description: z.string().max(500, 'Description is too long').optional(),
  productDocs: z.string().url('Must be a valid URL').optional().or(z.literal('')),
  campaignObjective: z.string().max(200, 'Objective is too long').optional(),
  bookingLink: z.string().url('Must be a valid URL').optional().or(z.literal('')),
  isFreemium: z.boolean(),
  ghostModeEnabled: z.boolean(),
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
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [linkedinSetupStatus, setLinkedinSetupStatus] = useState<LinkedInSetupStatus | null>(null)
  const [checkingLinkedin, setCheckingLinkedin] = useState(false)
  const [templates, setTemplates] = useState<CampaignTemplate[]>([])
  const [templateLoading, setTemplateLoading] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<CampaignTemplate | null>(null)
  const [showTemplateList, setShowTemplateList] = useState(!isEditing)

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: undefined,
      productDocs: undefined,
      campaignObjective: undefined,
      bookingLink: undefined,
      isFreemium: false,
      ghostModeEnabled: false,
      velocity: 10,
      cooldownMinutes: 60,
      status: 'draft',
    },
  })

  // Check LinkedIn setup status when form opens (for new campaigns)
  useEffect(() => {
    if (open && !isEditing && !campaign) {
      void (async () => {
        try {
          setCheckingLinkedin(true)
          const response = await getLinkedInSetupStatus()
          if (response.data) {
            setLinkedinSetupStatus(response.data)
          }
        } catch (err) {
          console.error('Error checking LinkedIn setup status:', err)
        } finally {
          setCheckingLinkedin(false)
        }
      })()
    } else {
      setLinkedinSetupStatus(null)
      setCheckingLinkedin(false)
    }
  }, [open, isEditing, campaign])

  // Fetch templates when opening the form for a new campaign
  useEffect(() => {
    if (!isEditing && !campaign && !templates.length) {
      void (async () => {
        try {
          setTemplateLoading(true)
          const response = await getCampaignTemplates()
          if (response.data && response.data.data) {
            setTemplates(response.data.data)
          }
        } catch (err) {
          console.error('Error fetching templates:', err)
        } finally {
          setTemplateLoading(false)
        }
      })()
    }
  }, [isEditing, campaign, templates.length])

  // Clone template when selected
  useEffect(() => {
    if (selectedTemplate && !campaign) {
      form.reset({
        name: selectedTemplate.name,
        description: selectedTemplate.description || undefined,
        campaignObjective: selectedTemplate.campaign_objective || undefined,
        ghostModeEnabled: selectedTemplate.ghost_mode_enabled,
        velocity: selectedTemplate.velocity,
        cooldownMinutes: selectedTemplate.cooldown_minutes,
        status: 'draft',
        isFreemium: false,
        productDocs: undefined,
        bookingLink: undefined,
      })
    }
  }, [selectedTemplate, campaign, form])

  useEffect(() => {
    if (campaign) {
      form.reset({
        name: campaign.name,
        description: campaign.description || undefined,
        productDocs: campaign.productDocs || undefined,
        campaignObjective: campaign.campaignObjective || undefined,
        bookingLink: campaign.bookingLink || undefined,
        isFreemium: campaign.isFreemium,
        ghostModeEnabled: campaign.ghostModeEnabled || false,
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
        ghostModeEnabled: false,
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

  // Check if LinkedIn is configured before allowing campaign creation
  if (checkingLinkedin) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Checking Setup Status</DialogTitle>
            <DialogDescription>
              Verifying your LinkedIn configuration before creating a campaign.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-center py-12 space-x-4">
            <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <span className="text-muted-foreground">Checking setup status...</span>
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  // If LinkedIn is not configured (no credentials or count is 0), show an informative message
  if (!isEditing && !campaign && !linkedinSetupStatus?.status.linkedin_credentials?.count) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>LinkedIn Not Configured</DialogTitle>
            <DialogDescription>
              You must set up LinkedIn credentials before creating a campaign.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col items-center justify-center py-8 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
              <Icons.AlertCircle className="h-8 w-8 text-red-600" />
            </div>
            <p className="text-sm text-muted-foreground">
              You must set up LinkedIn credentials before creating a campaign.
            </p>
            <Button
              variant="secondary"
              onClick={() => {
                window.location.href = '/settings?tab=linkedin-credentials'
                onOpenChange(false)
              }}
            >
              <Icons.Settings className="h-4 w-4 mr-2" />
              Go to LinkedIn Settings
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    )
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
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Basic Info</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
                <TabsTrigger value="advanced">Advanced</TabsTrigger>
                <TabsTrigger value="templates">Templates</TabsTrigger>
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
                      <FormLabel>Daily Connection Limit</FormLabel>
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
                        Maximum number of connections to send per day
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

                <FormField
                  control={form.control}
                  name="ghostModeEnabled"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">Ghost Mode</FormLabel>
                        <FormDescription>
                          Enable ghost mode to test campaign without sending real LinkedIn actions
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

              <TabsContent value="templates" className="space-y-4">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <h4 className="font-medium">Use Template</h4>
                      <p className="text-sm text-muted-foreground">
                        Select a campaign template to clone its configuration
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setShowTemplateList(!showTemplateList)}
                    >
                      Browse Templates
                    </Button>
                  </div>

                  {showTemplateList && (
                    <div className="rounded-lg border border-dashed p-6 bg-muted/30">
                      {templateLoading ? (
                        <div className="text-center py-4">
                          <Icons.RefreshCw className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
                          <p className="text-sm text-muted-foreground mt-2">Loading templates...</p>
                        </div>
                      ) : templates.length === 0 ? (
                        <div className="text-center py-6">
                          <p className="text-sm text-muted-foreground">No templates found</p>
                          <Button
                            size="sm"
                            variant="outline"
                            className="mt-2"
                            onClick={() => router.push('/campaigns/templates')}
                          >
                            Create Template
                          </Button>
                        </div>
                      ) : (
                        <div className="space-y-2 max-h-60 overflow-y-auto">
                          {templates.map(template => (
                            <div
                              key={template.id}
                              className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                                selectedTemplate?.id === template.id
                                  ? 'bg-primary/10 border-primary'
                                  : 'hover:bg-muted/50'
                              }`}
                              onClick={() => setSelectedTemplate(template)}
                            >
                              <div className="space-y-1">
                                <div className="font-medium">{template.name}</div>
                                <div className="text-xs text-muted-foreground line-clamp-1">
                                  {template.description || 'No description'}
                                </div>
                              </div>
                              {selectedTemplate?.id === template.id && (
                                <Icons.CheckCircle className="h-5 w-5 text-primary" />
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {selectedTemplate && (
                    <div className="rounded-lg bg-blue-500/5 border border-blue-500/20 p-4">
                      <div className="flex items-center justify-between">
                        <div className="space-y-1">
                          <p className="text-sm font-medium text-blue-600 dark:text-blue-400">
                            Template Selected: {selectedTemplate.name}
                          </p>
                          <p className="text-xs text-blue-600/80 dark:text-blue-400/80">
                            Click "Create Campaign" to apply template settings
                          </p>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedTemplate(null)}
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
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
