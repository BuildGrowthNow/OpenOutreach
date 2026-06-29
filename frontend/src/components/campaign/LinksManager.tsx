'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Plus, Terminal } from 'lucide-react'
import { TrackedLink } from '@/lib/api/dashboard'
import { LinkList } from './LinkList'
import { LinkForm } from './LinkForm'
import { LinkStatsDashboard } from './LinkStatsDashboard'
import { getLinks, createLink, updateLink, deleteLink } from '@/lib/api/dashboard'

interface LinksManagerProps {
  campaignId: string
}

export function LinksManager({ campaignId }: LinksManagerProps) {
  const [links, setLinks] = useState<TrackedLink[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingLink, setEditingLink] = useState<TrackedLink | null>(null)
  const [showStats, setShowStats] = useState(false)
  const [selectedLink, setSelectedLink] = useState<TrackedLink | null>(null)

  const fetchLinks = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getLinks(campaignId)
      if (response.data) {
        setLinks(response.data.data || [])
      } else if (response.error) {
        setError(response.error)
      }
    } catch (err) {
      setError('Failed to load links. Please try again.')
      console.error('Error fetching links:', err)
    } finally {
      setLoading(false)
    }
  }, [campaignId])

  useEffect(() => {
    if (campaignId) {
      void fetchLinks()
    }
  }, [campaignId, fetchLinks])

  const handleCreateLink = async (data: Partial<TrackedLink>) => {
    try {
      const response = await createLink({
        ...data,
        campaign_id: campaignId,
      })
      if (response.data) {
        await fetchLinks()
        return { success: true }
      }
      return { success: false, error: response.error || 'Failed to create link' }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : 'Failed to create link' }
    }
  }

  const handleUpdateLink = async (data: Partial<TrackedLink>) => {
    if (!editingLink?.id) return
    try {
      const response = await updateLink(editingLink.id, data)
      if (response.data) {
        await fetchLinks()
        setEditingLink(null)
        return { success: true }
      }
      return { success: false, error: response.error || 'Failed to update link' }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : 'Failed to update link' }
    }
  }

  const handleDeleteLink = async (link: TrackedLink) => {
    if (!confirm('Are you sure you want to delete this link?')) return
    try {
      const response = await deleteLink(link.id)
      if (response.data) {
        await fetchLinks()
        return { success: true }
      }
      return { success: false, error: response.error || 'Failed to delete link' }
    } catch (err) {
      return { success: false, error: err instanceof Error ? err.message : 'Failed to delete link' }
    }
  }

  const handleEdit = (link: TrackedLink) => {
    setEditingLink(link)
    setShowCreateModal(true)
  }

  const handleViewStats = (link: TrackedLink) => {
    setSelectedLink(link)
    setShowStats(true)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight">Tracked Links</h2>
          <p className="text-muted-foreground">
            Manage and track links for this campaign
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Link
        </Button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchLinks} className="mt-2">
            Retry
          </Button>
        </div>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Links
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{links.length}</div>
            <p className="text-xs text-muted-foreground">Tracked URLs</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Clicks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {links.reduce((sum, link) => sum + (link.total_clicks || 0), 0).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">All time clicks</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Links
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">
              {links.filter(link => link.is_active).length}
            </div>
            <p className="text-xs text-muted-foreground">Currently active</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Click-through Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {links.length > 0 ? '...' : '0%'}
            </div>
            <p className="text-xs text-muted-foreground">Est. conversion rate</p>
          </CardContent>
        </Card>
      </div>

      {/* Loading State */}
      {loading ? (
        <div className="space-y-4">
          <div className="h-32 rounded-lg bg-muted/50 animate-pulse" />
          <div className="h-4 rounded-lg bg-muted/50 animate-pulse w-1/3" />
        </div>
      ) : (
        <>
          {/* Link List */}
          <Card>
            <CardHeader>
              <CardTitle>All Tracked Links</CardTitle>
              <CardDescription>
                View and manage all links associated with this campaign
              </CardDescription>
            </CardHeader>
            <CardContent>
              <LinkList 
                links={links} 
                onEdit={handleEdit}
                onDelete={handleDeleteLink}
                onViewStats={handleViewStats}
              />
            </CardContent>
          </Card>
        </>
      )}

      {/* Create Link Modal */}
      <LinkForm
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
        link={editingLink}
        campaignId={campaignId}
        onSubmit={editingLink ? handleUpdateLink : handleCreateLink}
        isEditing={!!editingLink}
      />

      {/* Link Stats Dashboard */}
      {showStats && selectedLink && (
        <LinkStatsDashboard 
          link={selectedLink}
          onClose={() => setShowStats(false)}
        />
      )}
    </div>
  )
}