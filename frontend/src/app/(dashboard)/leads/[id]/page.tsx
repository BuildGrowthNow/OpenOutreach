'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Icons } from '@/lib/types/components'
import { LeadStatusBadge } from '@/components/leads/lead-status-badge'
import { LeadNotes } from '@/components/leads/lead-notes'
import { MessageThread } from '@/components/messages/message-thread'
import { LeadForm } from '@/components/leads/lead-form'
import { AddToCampaignModal } from '@/components/modals/add-to-campaign-modal'
import {
  getLead,
  updateLead,
  reScrapeLeadProfile,
  getMessages,
  sendMessageToLead,
  getLeadNotes,
  createLeadNote,
  updateLeadNote,
  deleteLeadNote,
  getCampaigns,
  type Note as ApiNote,
  type Campaign
} from '@/lib/api/dashboard'
import { Lead, DealState, DealOutcome, Message } from '@/lib/types/components'
import { formatDistanceToNow } from 'date-fns'

interface LeadProfile {
  firstName?: string
  lastName?: string
  headline?: string
  summary?: string
  location?: string
  experience?: Array<{
    company?: string
    title?: string
    duration?: string
  }>
  education?: Array<{
    school?: string
    degree?: string
    year?: string
  }>
}

const LeadDetailsPage = () => {
  const router = useRouter()
  const params = useParams()
  const leadId = params.id as string
  
  const [lead, setLead] = useState<Lead | null>(null)
  const [profile, setProfile] = useState<LeadProfile | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [notes, setNotes] = useState<Array<{
    id: string
    content: string
    createdBy: string
    createdAt: string
    updatedAt?: string
  }>>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [notesLoading, setNotesLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [messageLoading, setMessageLoading] = useState(false)
  const [sendingMessage, setSendingMessage] = useState(false)
  const [savingNote, setSavingNote] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showAddToCampaign, setShowAddToCampaign] = useState(false)

  const fetchProfileData = useCallback(async (id: string) => {
    try {
      const response = await reScrapeLeadProfile(id)
      if (response.data?.profile) {
        setProfile(response.data.profile)
      } else if (response.data?.success && response.data?.profile) {
        setProfile(response.data.profile)
      }
    } catch (err) {
      console.error('Failed to fetch profile data:', err)
    }
  }, [])

  const fetchLeadDetails = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await getLead(leadId)
      
      if (response.data) {
        setLead(response.data)
        
        // Fetch full profile data from separate endpoint
        await fetchProfileData(leadId)
      } else {
        setError(response.error || 'Failed to fetch lead details')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch lead details')
    } finally {
      setLoading(false)
    }
  }, [leadId, fetchProfileData])

  const fetchCampaigns = useCallback(async () => {
    try {
      const response = await getCampaigns()
      if (response.data?.data) {
        setCampaigns(response.data.data)
      }
    } catch (err) {
      console.error('Failed to fetch campaigns:', err)
    }
  }, [])

  useEffect(() => {
    if (!leadId) return
    void (async () => {
      await fetchLeadDetails()
      await fetchCampaigns()
    })()
  }, [leadId, fetchLeadDetails, fetchCampaigns])

  const handleReScrape = async () => {
    if (!lead) return
    
    try {
      const response = await reScrapeLeadProfile(lead.id)
      if (response.data?.success) {
        alert('Profile re-scraped successfully!')
        await fetchLeadDetails()
        await fetchCampaigns()
      } else {
        alert(`Failed to re-scrape profile: ${response.error || 'Unknown error'}`)
      }
    } catch (err) {
      alert(`Failed to re-scrape profile: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleDisqualify = async () => {
    if (!lead) return
    
    if (!confirm(`Are you sure you want to disqualify ${lead.name || 'this lead'}?`)) {
      return
    }

    try {
      await updateLead(lead.id, { disqualified: true })
      alert('Lead disqualified successfully!')
      router.push('/leads')
    } catch (err) {
      alert(`Failed to disqualify lead: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleEditSubmit = async (data: Partial<Lead>) => {
    if (!lead) return
    
    try {
      setShowEditModal(false)
      setLoading(true)
      const response = await updateLead(lead.id, data)
      
      if (response.data) {
        setLead(response.data)
        alert('Lead updated successfully!')
        await fetchProfileData(lead.id)
      } else {
        alert(`Failed to update lead: ${response.error || 'Unknown error'}`)
      }
    } catch (err) {
      console.error('Failed to update lead:', err)
      alert('Failed to update lead. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleAddToCampaign = async (campaignId: string) => {
    if (!lead) return
    
    try {
      const response = await fetch(`/api/leads/${lead.id}/add-to-campaign/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ campaign_id: parseInt(campaignId) }),
      })

      const data = await response.json()
      
      if (response.ok && data.success) {
        alert('Lead added to campaign successfully!')
        setShowAddToCampaign(false)
        await fetchLeadDetails()
        await fetchCampaigns()
      } else {
        alert(`Failed to add to campaign: ${data.error || 'Unknown error'}`)
      }
    } catch (err) {
      console.error('Failed to add to campaign:', err)
      alert('Failed to add to campaign. Please try again.')
    }
  }

  const handleBack = () => {
    router.push('/leads')
  }

  // Fetch messages for the lead
  const fetchMessages = useCallback(async (silent = false) => {
    if (!leadId) return
    
    try {
      if (!silent) setMessageLoading(true)
      const response = await getMessages(undefined, undefined, leadId)
      if (response.data?.data) {
        setMessages(response.data.data)
      }
    } catch (err) {
      console.error('Failed to fetch messages:', err)
    } finally {
      if (!silent) setMessageLoading(false)
    }
  }, [leadId])

  // Fetch messages when tab changes to messages, and poll
  useEffect(() => {
    if (activeTab !== 'messages' || !leadId) return
    void (async () => {
      await fetchMessages(false)
    })()

    const interval = setInterval(() => {
      void fetchMessages(true)
    }, 10000)

    return () => clearInterval(interval)
  }, [activeTab, leadId, fetchMessages])

  // Fetch notes on component mount
  useEffect(() => {
    const fetchNotes = async () => {
      try {
        setNotesLoading(true)
        const response = await getLeadNotes(leadId)
        if (response.data?.data) {
          // Transform API notes to component format
          const transformedNotes = response.data.data.map((apiNote: ApiNote) => ({
            id: apiNote.id,
            content: apiNote.content,
            createdBy: apiNote.created_by,
            createdAt: apiNote.created_at,
            updatedAt: apiNote.updated_at
          }))
          setNotes(transformedNotes)
        }
      } catch (error) {
        console.error('Failed to fetch notes:', error)
      } finally {
        setNotesLoading(false)
      }
    }

    if (leadId) {
      fetchNotes()
    }
  }, [leadId])

  const handleSendMessage = async (content: string) => {
    if (!lead) return
    
    try {
      setSendingMessage(true)
      const response = await sendMessageToLead(lead.id, content)
      
      if (response.data?.success && response.data?.message) {
        // Add the sent message to the list
        setMessages(prev => [...prev, response.data!.message])
        alert('Message sent successfully!')
      } else {
        alert(`Failed to send message: ${response.error || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      alert('Failed to send message. Please try again.')
    } finally {
      setSendingMessage(false)
    }
  }

  // Note handlers
  const handleAddNote = async (content: string) => {
    try {
      setSavingNote(true)
      const response = await createLeadNote(leadId, content)
      
      if (response.data) {
        // Transform and add the new note to the list
        const newNote = {
          id: response.data.id,
          content: response.data.content,
          createdBy: response.data.created_by,
          createdAt: response.data.created_at,
          updatedAt: response.data.updated_at
        }
        
        setNotes(prev => [...prev, newNote])
        alert('Note added successfully!')
      } else {
        alert(`Failed to add note: ${response.error || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Failed to add note:', error)
      alert('Failed to add note. Please try again.')
    } finally {
      setSavingNote(false)
    }
  }

  const handleEditNote = async (noteId: string, content: string) => {
    try {
      setSavingNote(true)
      const response = await updateLeadNote(leadId, noteId, content)
      
      if (response.data) {
        // Update the note in the list
        setNotes(prev => prev.map(note => 
          note.id === noteId 
            ? { 
                ...note, 
                content: response.data!.content,
                updatedAt: response.data!.updated_at || response.data!.created_at
              }
            : note
        ))
        alert('Note updated successfully!')
      } else {
        alert(`Failed to update note: ${response.error || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Failed to update note:', error)
      alert('Failed to update note. Please try again.')
    } finally {
      setSavingNote(false)
    }
  }

  const handleDeleteNote = async (noteId: string) => {
    try {
      setSavingNote(true)
      const response = await deleteLeadNote(leadId, noteId)
      
      if (response.data?.success) {
        // Remove the note from the list
        setNotes(prev => prev.filter(note => note.id !== noteId))
        alert('Note deleted successfully!')
      } else {
        alert(`Failed to delete note: ${response.error || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Failed to delete note:', error)
      alert('Failed to delete note. Please try again.')
    } finally {
      setSavingNote(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-center h-96">
          <div className="flex flex-col items-center gap-4">
            <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <div className="text-muted-foreground">Loading lead details...</div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !lead) {
    return (
      <div className="space-y-6">
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-96 gap-4">
            <Icons.AlertCircle className="h-12 w-12 text-red-500" />
            <div className="text-center space-y-2">
              <div className="text-lg font-semibold">{error || 'Lead not found'}</div>
              <div className="text-muted-foreground">
                {error 
                  ? 'Failed to load lead details. Please try again.'
                  : 'The lead you\'re looking for doesn\'t exist or has been removed.'
                }
              </div>
              <Button onClick={handleBack} className="mt-4">
                <Icons.ChevronRight className="mr-2 h-4 w-4 rotate-180" />
                Back to Leads
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleBack}
              className="mb-2"
            >
              <Icons.ChevronRight className="mr-1 h-4 w-4 rotate-180" />
              Back to Leads
            </Button>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">{lead.name || 'Unnamed Lead'}</h1>
          <p className="text-muted-foreground mt-1">
            Lead ID: {lead.id} • Added {formatDistanceToNow(new Date(lead.creationDate), { addSuffix: true })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="px-3 py-1">
            <Icons.Globe className="mr-2 h-3.5 w-3.5" />
            {lead.publicIdentifier}
          </Badge>
          <Button variant="outline" onClick={handleReScrape}>
            <Icons.RefreshCw className="mr-2 h-4 w-4" />
            Re-scrape Profile
          </Button>
          <Button variant="destructive" onClick={handleDisqualify}>
            <Icons.Trash2 className="mr-2 h-4 w-4" />
            Disqualify
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column - Overview */}
        <div className="lg:col-span-2">
          <Tabs defaultValue="overview" value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="profile">Profile</TabsTrigger>
              <TabsTrigger value="messages">Messages</TabsTrigger>
              <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview" className="space-y-6">
              {/* Status Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>Lead Status</span>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={lead.disqualified ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'}>
                        {lead.disqualified ? 'Disqualified' : 'Active'}
                      </Badge>
                      <Button size="sm" variant="outline" onClick={() => setShowEditModal(true)}>
                        <Icons.Edit className="mr-2 h-3.5 w-3.5" />
                        Edit Status
                      </Button>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <div className="text-sm text-muted-foreground mb-2">Current State</div>
                      <LeadStatusBadge state={lead.state} outcome={lead.outcome} />
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground mb-2">Deal Information</div>
                      <div className="space-y-1">
                        <div className="font-medium">LinkedIn URL:</div>
                        {lead.linkedinUrl ? (
                          <a
                            href={lead.linkedinUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 hover:underline text-sm truncate block"
                          >
                            {lead.linkedinUrl}
                            <Icons.ExternalLink className="ml-1 inline h-3 w-3" />
                          </a>
                        ) : (
                          <span className="text-sm text-muted-foreground">Not available</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <Separator />

                  <div>
                    <div className="text-sm text-muted-foreground mb-3">Timeline</div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm">Created:</span>
                        <span className="text-sm font-medium">
                          {formatDistanceToNow(new Date(lead.creationDate), { addSuffix: true })}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm">Last Updated:</span>
                        <span className="text-sm font-medium">
                          {formatDistanceToNow(new Date(lead.updateDate), { addSuffix: true })}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Contact Information Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>Contact Information</span>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => setShowEditModal(true)}>
                        <Icons.Edit className="mr-2 h-3.5 w-3.5" />
                        Edit Contact Info
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setShowAddToCampaign(true)}>
                        <Icons.Users className="mr-2 h-3.5 w-3.5" />
                        Add to Campaign
                      </Button>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {lead.contactInfo?.email && (
                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Primary Email</div>
                      <a
                        href={`mailto:${lead.contactInfo.email}`}
                        className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                      >
                        {lead.contactInfo.email}
                      </a>
                    </div>
                  )}
                  
                  {lead.contactInfo?.phoneNumbers && lead.contactInfo.phoneNumbers.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-sm text-muted-foreground">Phone Numbers</div>
                      <div className="flex flex-wrap gap-2">
                        {lead.contactInfo.phoneNumbers.map((phone, index) => (
                          <Badge key={index} variant="outline" className="font-mono">
                            {phone}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {(!lead.contactInfo?.email && !lead.contactInfo?.phoneNumbers) && (
                    <div className="text-center py-6 text-muted-foreground">
                      <Icons.AlertTriangle className="mx-auto h-8 w-8 mb-2" />
                      <div>No contact information available</div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Profile Tab */}
            <TabsContent value="profile" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>LinkedIn Profile Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  {profile ? (
                    <>
                      {/* Basic Info */}
                      <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <div className="text-sm text-muted-foreground mb-1">Company</div>
                            <div className="font-medium">{profile.headline || lead.company || 'Not specified'}</div>
                          </div>
                          <div>
                            <div className="text-sm text-muted-foreground mb-1">Title</div>
                            <div className="font-medium">{lead.title || 'Not specified'}</div>
                          </div>
                        </div>

                        {profile.headline && (
                          <div>
                            <div className="text-sm text-muted-foreground mb-1">Headline</div>
                            <div className="font-medium">{profile.headline}</div>
                          </div>
                        )}

                        {profile.location && (
                          <div>
                            <div className="text-sm text-muted-foreground mb-1">Location</div>
                            <div className="font-medium">{profile.location}</div>
                          </div>
                        )}
                      </div>

                      {/* Summary */}
                      {profile.summary && (
                        <>
                          <Separator />
                          <div>
                            <div className="text-sm text-muted-foreground mb-2">Summary</div>
                            <div className="text-sm leading-relaxed whitespace-pre-wrap">{profile.summary}</div>
                          </div>
                        </>
                      )}

                      {/* Experience */}
                      {profile.experience && profile.experience.length > 0 && (
                        <>
                          <Separator />
                          <div>
                            <div className="text-sm text-muted-foreground mb-2">Experience</div>
                            <div className="space-y-3">
                              {profile.experience.map((exp, index) => (
                                <div key={index} className="space-y-1">
                                  <div className="font-medium">{exp.title || 'Role'} • {exp.company || 'Company'}</div>
                                  {exp.duration && (
                                    <div className="text-sm text-muted-foreground">{exp.duration}</div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </>
                      )}
                    </>
                  ) : (
                    <div className="text-center py-8">
                      <Icons.AlertCircle className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                      <div className="text-muted-foreground">Profile information not available</div>
                      <Button onClick={() => handleReScrape()} className="mt-4">
                        <Icons.RefreshCw className="mr-2 h-4 w-4" />
                        Re-scrape Profile
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Messages Tab */}
            <TabsContent value="messages" className="space-y-6">
              <MessageThread
                messages={messages}
                onSendMessage={handleSendMessage}
                isLoading={messageLoading}
                isSending={sendingMessage}
                leadName={lead.name || 'Lead'}
              />
            </TabsContent>

            {/* Campaigns Tab */}
            <TabsContent value="campaigns" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Campaign Participation</CardTitle>
                </CardHeader>
                <CardContent>
                  {campaigns.length > 0 ? (
                    <div className="space-y-4">
                      {campaigns.map(campaign => (
                        <div key={campaign.id} className="p-4 border rounded-lg hover:bg-muted/50 transition-colors">
                          <div className="flex items-start justify-between">
                            <div>
                              <h3 className="font-medium">{campaign.name}</h3>
                              {campaign.description && (
                                <p className="text-sm text-muted-foreground mt-1">{campaign.description}</p>
                              )}
                              <div className="flex items-center gap-2 mt-2">
                                <Badge variant="outline" className="text-xs">
                                  {campaign.status || 'Draft'}
                                </Badge>
                                {campaign.ghostModeEnabled && (
                                  <Badge variant="secondary" className="text-xs">
                                    Ghost Mode
                                  </Badge>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <Icons.BarChart3 className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                      <div className="text-muted-foreground">This lead is not part of any campaigns</div>
                      <Button onClick={() => setShowAddToCampaign(true)} className="mt-4">
                        <Icons.Users className="mr-2 h-4 w-4" />
                        Add to Campaign
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Quick Actions Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="outline" className="w-full justify-start" onClick={handleReScrape}>
                <Icons.RefreshCw className="mr-2 h-4 w-4" />
                Re-scrape Profile
              </Button>
              <Button variant="outline" className="w-full justify-start" onClick={() => setShowEditModal(true)}>
                <Icons.Edit className="mr-2 h-4 w-4" />
                Edit Lead Info
              </Button>
              <Button variant="outline" className="w-full justify-start">
                <Icons.MessageSquare className="mr-2 h-4 w-4" />
                Send Message
              </Button>
              <Button variant="outline" className="w-full justify-start" onClick={() => setShowAddToCampaign(true)}>
                <Icons.Link className="mr-2 h-4 w-4" />
                View Campaigns
              </Button>
              <Button variant="destructive" className="w-full justify-start" onClick={handleDisqualify}>
                <Icons.Trash2 className="mr-2 h-4 w-4" />
                Disqualify Lead
              </Button>
            </CardContent>
          </Card>

          {/* Metadata Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Metadata</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Public ID:</span>
                <span className="text-sm font-mono">{lead.publicIdentifier}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">LinkedIn URN:</span>
                <span className="text-sm font-mono truncate max-w-[120px]">
                  {lead.linkedinUrl?.split('/').pop() || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Messages:</span>
                <span className="text-sm font-medium">{lead.messagesCount || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-muted-foreground">Last Message:</span>
                <span className="text-sm">
                  {lead.lastMessageAt 
                    ? formatDistanceToNow(new Date(lead.lastMessageAt), { addSuffix: true })
                    : 'Never'
                  }
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Notes Card */}
          <LeadNotes
            notes={notes}
            onAddNote={handleAddNote}
            onEditNote={handleEditNote}
            onDeleteNote={handleDeleteNote}
            isLoading={notesLoading}
            isSaving={savingNote}
            leadName={lead.name || 'Lead'}
          />
        </div>
      </div>

      {/* Edit Lead Modal */}
      <LeadForm
        open={showEditModal}
        onOpenChange={setShowEditModal}
        lead={lead}
        onSubmit={handleEditSubmit}
        isSubmitting={loading}
      />

      {/* Add to Campaign Modal */}
      {campaigns.length > 0 && (
        <AddToCampaignModal
          open={showAddToCampaign}
          onOpenChange={setShowAddToCampaign}
          leadId={lead.id}
          leadName={lead.name}
          onSuccess={() => {
            setShowAddToCampaign(false)
            void fetchLeadDetails()
          }}
        />
      )}
    </div>
  )
}

export default LeadDetailsPage