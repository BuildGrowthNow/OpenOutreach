'use client'

import { useState, useEffect, useCallback } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Icons } from '@/lib/types/components'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getCampaigns } from '@/lib/api/dashboard'
import { Campaign } from '@/lib/types/components'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface AddToCampaignModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  leadId: string
  leadName?: string
  onSuccess?: () => void
}

export function AddToCampaignModal({ open, onOpenChange, leadId, leadName, onSuccess }: AddToCampaignModalProps) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  const fetchCampaigns = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await getCampaigns()
      if (response.data) {
        setCampaigns(response.data.data || [])
      } else {
        setError(response.error || 'Failed to fetch campaigns')
      }
    } catch (err) {
      setError('Failed to load campaigns')
      console.error('Error fetching campaigns:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      void fetchCampaigns()
    }
  }, [open, fetchCampaigns])

  const handleAddToCampaign = async () => {
    if (!selectedCampaignId) {
      setError('Please select a campaign')
      return
    }

    try {
      setAdding(true)
      setError(null)

      const response = await fetch(`/api/leads/${leadId}/add-to-campaign/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ campaign_id: selectedCampaignId }),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        onOpenChange(false)
        if (onSuccess) {
          onSuccess()
        }
      } else {
        setError(data.error || 'Failed to add lead to campaign')
      }
    } catch (err) {
      setError('An error occurred while adding lead to campaign')
      console.error('Error adding to campaign:', err)
    } finally {
      setAdding(false)
    }
  }

  const handleClose = () => {
    onOpenChange(false)
    setSelectedCampaignId(null)
    setError(null)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Lead to Campaign</DialogTitle>
          <DialogDescription>
            Add {leadName || 'this lead'} to an existing campaign to enable outreach automation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {error && (
            <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="campaign" className="text-sm font-medium">
                Select Campaign
              </Label>
              <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
                {campaigns.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No campaigns found. Create a campaign first.
                  </div>
                ) : (
                  campaigns.map(campaign => (
                    <Card
                      key={campaign.id}
                      className={`cursor-pointer transition-all duration-200 ${
                        selectedCampaignId === campaign.id
                          ? 'border-primary ring-1 ring-primary'
                          : 'hover:bg-accent'
                      }`}
                      onClick={() => setSelectedCampaignId(campaign.id)}
                    >
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">
                          {campaign.name}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {campaign.description || 'No description'}
                        </p>
                        {campaign.status && (
                          <div className="mt-2 flex items-center gap-2">
                            <span
                              className={`h-2 w-2 rounded-full ${
                                campaign.status === 'active'
                                  ? 'bg-emerald-500'
                                  : campaign.status === 'paused'
                                    ? 'bg-amber-500'
                                    : 'bg-slate-500'
                              }`}
                            />
                            <span className="text-xs capitalize text-muted-foreground">
                              {campaign.status}
                            </span>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={adding}>
            Cancel
          </Button>
          <Button onClick={handleAddToCampaign} disabled={!selectedCampaignId || adding}>
            {adding ? (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Adding...
              </>
            ) : (
              'Add to Campaign'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}