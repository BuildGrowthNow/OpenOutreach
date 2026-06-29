'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Icons } from '@/lib/types/components'
import { 
  getCampaignTemplates, 
  createCampaignTemplate, 
  updateCampaignTemplate,
  deleteCampaignTemplate,
  cloneCampaignTemplate
} from '@/lib/api/dashboard'
import { 
  CampaignTemplate, 
  CampaignTemplateCreateData 
} from '@/lib/types/components'
import { TemplateCard } from '@/components/campaigns/template-card'
import { TemplateForm } from '@/components/campaigns/template-form'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export default function CampaignTemplatesPage() {
  const router = useRouter()
  const [templates, setTemplates] = useState<CampaignTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<CampaignTemplate | null>(null)
  const [filterPublic, setFilterPublic] = useState(false)

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getCampaignTemplates(filterPublic ? 'true' : undefined)
      if (response.data) {
        setTemplates(response.data.data || [])
      } else {
        setError(response.error || response.message || 'Failed to fetch templates')
      }
    } catch (err) {
      setError('An error occurred while fetching templates')
      console.error('Error fetching templates:', err)
    } finally {
      setLoading(false)
    }
  }, [filterPublic])

  useEffect(() => {
    void (async () => {
      await fetchTemplates()
    })()
  }, [fetchTemplates])

  const filteredTemplates = useCallback(() => {
    let filtered = [...templates]

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim()
      filtered = filtered.filter(
        template =>
          template.name.toLowerCase().includes(query) ||
          template.description?.toLowerCase().includes(query) ||
          template.campaign_objective?.toLowerCase().includes(query)
      )
    }

    // Filter by public/private
    if (filterPublic) {
      filtered = filtered.filter(template => template.is_public)
    }

    return filtered
  }, [templates, searchQuery, filterPublic])

  const handleCreateTemplate = async (data: CampaignTemplateCreateData) => {
    try {
      setError(null)
      const response = await createCampaignTemplate(data)
      if (response.data) {
        setShowCreateForm(false)
        fetchTemplates() // Refresh list
      } else {
        setError(response.error || response.message || 'Failed to create template')
      }
    } catch (error) {
      setError('An error occurred while creating the template')
      console.error('Error creating template:', error)
    }
  }

  const handleUpdateTemplate = async (id: string, data: Partial<CampaignTemplateCreateData>) => {
    try {
      setError(null)
      const response = await updateCampaignTemplate(id, data)
      if (response.data) {
        setEditingTemplate(null)
        fetchTemplates() // Refresh list
      } else {
        setError(response.error || response.message || 'Failed to update template')
      }
    } catch (error) {
      setError('An error occurred while updating the template')
      console.error('Error updating template:', error)
    }
  }

  const handleDeleteTemplate = async (template: CampaignTemplate) => {
    try {
      setError(null)
      const response = await deleteCampaignTemplate(template.id.toString())
      if (response.data) {
        fetchTemplates() // Refresh list
      } else {
        setError(response.error || response.message || 'Failed to delete template')
      }
    } catch (error) {
      console.error('Error deleting template:', error)
      setError('An error occurred while deleting the template')
    }
  }

  const handleCloneTemplate = async (template: CampaignTemplate) => {
    try {
      setError(null)
      const response = await cloneCampaignTemplate(template.id.toString())
      if (response.data) {
        fetchTemplates() // Refresh list
      } else {
        setError(response.error || response.message || 'Failed to clone template')
      }
    } catch (error) {
      console.error('Error cloning template:', error)
      setError('An error occurred while cloning the template')
    }
  }

  const handleCreateCampaignFromTemplate = async (template: CampaignTemplate) => {
    try {
      setError(null)
      router.push(`/campaigns/new?templateId=${template.id}`)
    } catch (error) {
      console.error('Error navigating to create campaign:', error)
      setError('An error occurred while navigating to create campaign')
    }
  }

  const handleEditTemplate = (template: CampaignTemplate) => {
    setEditingTemplate(template)
  }

  const stats = {
    total: templates.length,
    public: templates.filter(t => t.is_public).length,
    private: templates.filter(t => !t.is_public).length,
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
          <Skeleton className="h-10 w-32" />
        </div>

        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-8 w-full mb-2" />
                <Skeleton className="h-4 w-3/4" />
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Card key={i} className="h-48">
              <CardContent className="p-6">
                <Skeleton className="h-6 w-3/4 mb-4" />
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-5/6 mb-2" />
                <Skeleton className="h-4 w-4/6" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Campaign Templates</h1>
          <p className="text-muted-foreground">
            Manage and reuse your campaign configurations
          </p>
        </div>
        <Button onClick={() => setShowCreateForm(true)}>
          <Icons.Plus className="mr-2 h-4 w-4" />
          New Template
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Total Templates" value={stats.total} />
        <StatCard title="Public Templates" value={stats.public} />
        <StatCard title="Private Templates" value={stats.private} />
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search templates..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="max-w-sm"
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant={filterPublic ? 'default' : 'outline'}
            onClick={() => setFilterPublic(!filterPublic)}
          >
            <Icons.Globe className="mr-2 h-4 w-4" />
            {filterPublic ? 'Public' : 'All'}
          </Button>
          <Button
            variant={filterPublic ? 'outline' : 'default'}
            onClick={() => setFilterPublic(false)}
          >
            <Icons.User className="mr-2 h-4 w-4" />
            {filterPublic ? 'All' : 'Mine'}
          </Button>
        </div>
      </div>

      {filteredTemplates().length === 0 && !loading ? (
        <EmptyState
          title="No templates found"
          description={searchQuery ? 'Try changing your search terms' : 'Create a template to get started'}
          action={
            <Button onClick={() => setShowCreateForm(true)}>
              <Icons.Plus className="mr-2 h-4 w-4" />
              Create Template
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates().map(template => (
            <TemplateCard
              key={template.id}
              template={template}
              onClick={() => router.push(`/campaigns/templates/${template.id}`)}
              onEdit={handleEditTemplate}
              onDelete={handleDeleteTemplate}
              onClone={handleCloneTemplate}
              onCreateCampaign={handleCreateCampaignFromTemplate}
            />
          ))}
        </div>
      )}

      {showCreateForm && (
        <TemplateForm
          open={showCreateForm}
          onOpenChange={setShowCreateForm}
          onSubmit={handleCreateTemplate}
        />
      )}

      {editingTemplate && (
        <TemplateForm
          open={!!editingTemplate}
          onOpenChange={open => !open && setEditingTemplate(null)}
          template={editingTemplate}
          onSubmit={data => handleUpdateTemplate(editingTemplate.id.toString(), data)}
          isEditing
        />
      )}
    </div>
  )
}

interface StatCardProps {
  title: string
  value: number
}

function StatCard({ title, value }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="text-3xl font-bold">{value}</div>
        </div>
      </CardContent>
    </Card>
  )
}