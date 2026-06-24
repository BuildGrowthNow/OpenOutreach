'use client'

import { useState, useCallback } from 'react'
import {
  getHealthStatus,
  getRateLimits,
  getCampaignAnalytics,
  getCampaignLeads,
  getCampaignMessages,
  getCampaigns as getCampaignsAPI,
  getLeads as getLeadsAPI,
  getDailyUsage
} from '@/lib/api/dashboard'
import {
  Campaign,
  Lead,
  HealthStatus,
  Pagination,
  DailyUsageResponse
} from '@/lib/types/components'

// RateLimits type is no longer exported from components.ts
// Use Settings.rate_limits from @/lib/api/dashboard for the new canonical shape

export function useDashboard() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [campaignsLoading, setCampaignsLoading] = useState(true)
  const [campaignsError, setCampaignsError] = useState<string | null>(null)

  const [leads, setLeads] = useState<Lead[]>([])
  const [leadsLoading, setLeadsLoading] = useState(true)
  const [leadsError, setLeadsError] = useState<string | null>(null)

  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [healthError, setHealthError] = useState<string | null>(null)

  // Use Settings['rate_limits'] for the new canonical rate limits shape
  const [rateLimits, setRateLimits] = useState<Record<string, unknown> | null>(null)
  const [rateLimitsLoading, setRateLimitsLoading] = useState(true)
  const [rateLimitsError, setRateLimitsError] = useState<string | null>(null)

  // Daily usage statistics
  const [dailyUsage, setDailyUsage] = useState<DailyUsageResponse | null>(null)
  const [dailyUsageLoading, setDailyUsageLoading] = useState(true)
  const [dailyUsageError, setDailyUsageError] = useState<string | null>(null)

  const fetchCampaigns = useCallback(async (status?: string) => {
    setCampaignsLoading(true)
    setCampaignsError(null)
    try {
      const response = await getCampaignsAPI(status)
      if (response.data) {
        setCampaigns(response.data.data || [])
      }
    } catch (error) {
      setCampaignsError(error instanceof Error ? error.message : 'Failed to fetch campaigns')
    } finally {
      setCampaignsLoading(false)
    }
  }, [])

  const fetchLeads = useCallback(async (status?: string) => {
    setLeadsLoading(true)
    setLeadsError(null)
    try {
      const response = await getLeadsAPI(status)
      if (response.data) {
        setLeads(response.data.data || [])
      }
    } catch (error) {
      setLeadsError(error instanceof Error ? error.message : 'Failed to fetch leads')
    } finally {
      setLeadsLoading(false)
    }
  }, [])

  const fetchHealth = useCallback(async () => {
    setHealthLoading(true)
    setHealthError(null)
    try {
      const response = await getHealthStatus()
      if (response.data) {
        setHealthStatus(response.data)
      }
    } catch (error) {
      setHealthError(error instanceof Error ? error.message : 'Failed to fetch health status')
    } finally {
      setHealthLoading(false)
    }
  }, [])

  const fetchRateLimits = useCallback(async () => {
    setRateLimitsLoading(true)
    setRateLimitsError(null)
    try {
      const response = await getRateLimits()
      if (response.data) {
        setRateLimits(response.data)
      }
    } catch (error) {
      setRateLimitsError(error instanceof Error ? error.message : 'Failed to fetch rate limits')
    } finally {
      setRateLimitsLoading(false)
    }
  }, [])

  const fetchDailyUsage = useCallback(async () => {
    setDailyUsageLoading(true)
    setDailyUsageError(null)
    try {
      const response = await getDailyUsage()
      if (response.data) {
        setDailyUsage(response.data)
      }
    } catch (error) {
      setDailyUsageError(error instanceof Error ? error.message : 'Failed to fetch daily usage')
    } finally {
      setDailyUsageLoading(false)
    }
  }, [])

  return {
    campaigns,
    campaignsLoading,
    campaignsError,
    fetchCampaigns,
    leads,
    leadsLoading,
    leadsError,
    fetchLeads,
    healthStatus,
    healthLoading,
    healthError,
    fetchHealth,
    rateLimits,
    rateLimitsLoading,
    rateLimitsError,
    fetchRateLimits,
    dailyUsage,
    dailyUsageLoading,
    dailyUsageError,
    fetchDailyUsage
  }
}

interface CampaignAnalytics {
  period?: string
  campaign_id?: string
  stats?: {
    connections_sent?: number
    connections_accepted?: number
    connection_accept_rate?: number
    messages_sent?: number
    messages_replied?: number
    response_rate?: number
    conversions?: number
    conversion_rate?: number
    errors?: number
    rate_limit_warnings?: number
  }
  daily_breakdown?: Array<{
    date?: string
    connections_sent?: number
    connections_accepted?: number
    messages_sent?: number
    messages_replied?: number
  }>
  pipeline?: {
    qualified?: number
    ready_to_connect?: number
    pending?: number
    connected?: number
    completed?: number
    failed?: number
    no_email?: number
  }
}

export function useCampaignAnalytics(campaignId: string) {
  const [analytics, setAnalytics] = useState<CampaignAnalytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAnalytics = useCallback(
    async (period?: string) => {
      setLoading(true)
      setError(null)
      try {
        const response = await getCampaignAnalytics(campaignId, period)
        if (response.data) {
          setAnalytics(response.data)
        }
      } catch (error) {
        setError(error instanceof Error ? error.message : 'Failed to fetch analytics')
      } finally {
        setLoading(false)
      }
    },
    [campaignId]
  )

  return { analytics, loading, error, fetchAnalytics }
}

export function useCampaignLeads(campaignId: string) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [pagination, setPagination] = useState<Pagination | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchLeads = useCallback(
    async (status?: string, search?: string, page = 1, limit = 20) => {
      setLoading(true)
      setError(null)
      try {
        const response = await getCampaignLeads(campaignId, status, search, page, limit)
        if (response.data) {
          setLeads(response.data.data || [])
          setPagination(response.data.pagination)
        }
      } catch (error) {
        setError(error instanceof Error ? error.message : 'Failed to fetch leads')
      } finally {
        setLoading(false)
      }
    },
    [campaignId]
  )

  return { leads, pagination, loading, error, fetchLeads }
}

interface CampaignMessage {
  id: string
  deal_id: string
  deal_urn: string
  content: string
  is_outgoing: boolean
  sender: 'me' | 'them'
  creation_date: string
  recipient_name: string
  recipient_url: string
}

interface ApiMessage {
  id?: string
  deal_id?: string
  dealUrn?: string
  content?: string
  is_outgoing?: boolean
  isOutgoing?: boolean
  sender?: 'me' | 'them' | unknown
  creation_date?: string
  creationDate?: string
  recipient_name?: string
  recipientName?: string
  recipient_url?: string
  recipientUrl?: string
}

export function useCampaignMessages(campaignId: string) {
  const [messages, setMessages] = useState<CampaignMessage[]>([])
  const [pagination, setPagination] = useState<Pagination | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchMessages = useCallback(
    async (page = 1, limit = 50) => {
      setLoading(true)
      setError(null)
      try {
        const response = await getCampaignMessages(campaignId, page, limit)
        if (response.data && response.data.data) {
          // Map API Message[] to CampaignMessage[]
          const mappedMessages: CampaignMessage[] = (response.data.data || []).map((msg: ApiMessage) => ({
            id: msg.id || '',
            deal_id: msg.deal_id || msg.dealUrn || '',
            deal_urn: msg.dealUrn || msg.deal_id || '',
            content: msg.content || '',
            is_outgoing: msg.is_outgoing !== undefined ? msg.is_outgoing : (msg.isOutgoing || false),
            sender: (msg.sender as 'me' | 'them') || 'me',
            creation_date: msg.creation_date || msg.creationDate || '',
            recipient_name: msg.recipient_name || msg.recipientName || '',
            recipient_url: msg.recipient_url || msg.recipientUrl || '',
          }))
          setMessages(mappedMessages)
          setPagination(response.data.pagination || null)
        }
      } catch (error) {
        setError(error instanceof Error ? error.message : 'Failed to fetch messages')
      } finally {
        setLoading(false)
      }
    },
    [campaignId]
  )

  return { messages, pagination, loading, error, fetchMessages }
}
