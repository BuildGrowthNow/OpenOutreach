'use client'

import * as React from 'react'
import { toast } from '@/components/ui/use-toast'
import { Icons } from '@/lib/types/components'

// Toast notification types for real-time updates
export type ToastVariant = 'default' | 'destructive' | 'success' | 'error' | 'info' | 'warning'

/**
 * Display a toast notification for campaign status changes
 */
export function showToastCampaignStatus(
  campaignName: string,
  status: 'paused' | 'started' | 'completed',
  options?: { title?: string; description?: string; duration?: number }
) {
  const pausIcon = <Icons.Pause className="h-5 w-5 text-amber-500" />
  const playIcon = <Icons.Play className="h-5 w-5 text-emerald-500" />
  const checkIcon = <Icons.CheckCircle className="h-5 w-5 text-blue-500" />
  const bellIcon = <Icons.Bell className="h-5 w-5 text-slate-500" />

  const config: Record<string, { icon: React.ReactNode; title: string; description: string }> = {
    paused: {
      icon: pausIcon,
      title: 'Campaign Paused',
      description: campaignName + ' has been paused',
    },
    started: {
      icon: playIcon,
      title: 'Campaign Started',
      description: campaignName + ' has been started',
    },
    completed: {
      icon: checkIcon,
      title: 'Campaign Completed',
      description: campaignName + ' has completed all its activities',
    },
  }

  const { icon, title, description } = config[status] || {
    icon: bellIcon,
    title: status.charAt(0).toUpperCase() + status.slice(1),
    description: options?.title || '',
  }

  toast({
    title: options?.title || title,
    description: options?.description || description,
    icon: icon,
    variant: status === 'paused' ? 'warning' : status === 'started' ? 'success' : 'info',
    duration: options?.duration || 5000,
  })
}

/**
 * Display a toast notification for rate limit warnings
 */
export function showToastRateLimitWarning(profileUsername: string, warning: string) {
  const alertIcon = <Icons.AlertTriangle className="h-5 w-5 text-rose-500" />
  toast({
    title: 'Rate Limit Warning',
    description: profileUsername + ': ' + warning,
    icon: alertIcon,
    variant: 'warning',
    duration: 8000,
  })
}

/**
 * Display a toast notification for new messages
 */
export function showToastNewMessage(leadName: string, campaignName: string, preview: string) {
  const msgIcon = <Icons.MessageSquare className="h-5 w-5 text-purple-500" />
  toast({
    title: 'New Message Received',
    description: 'From ' + leadName + ' in ' + campaignName + ': ' + preview,
    icon: msgIcon,
    variant: 'info',
    duration: 6000,
  })
}

/**
 * Display a generic success toast
 */
export function showToastSuccess(title: string, description?: string, options?: { duration?: number }) {
  const successIcon = <Icons.CheckCircle className="h-5 w-5 text-emerald-500" />
  toast({
    title,
    description,
    icon: successIcon,
    variant: 'success',
    duration: options?.duration ?? 5000,
  })
}

/**
 * Display an error toast
 */
export function showToastError(title: string, description?: string, options?: { duration?: number }) {
  const errorIcon = <Icons.AlertCircle className="h-5 w-5 text-rose-500" />
  toast({
    title,
    description,
    icon: errorIcon,
    variant: 'error',
    duration: options?.duration ?? 8000,
  })
}

/**
 * Display an info toast
 */
export function showToastInfo(title: string, description?: string, options?: { duration?: number }) {
  const infoIcon = <Icons.Bell className="h-5 w-5 text-blue-500" />
  toast({
    title,
    description,
    icon: infoIcon,
    variant: 'info',
    duration: options?.duration ?? 5000,
  })
}

/**
 * Display a warning toast
 */
export function showToastWarning(title: string, description?: string, options?: { duration?: number }) {
  const warnIcon = <Icons.AlertTriangle className="h-5 w-5 text-amber-500" />
  toast({
    title,
    description,
    icon: warnIcon,
    variant: 'warning',
    duration: options?.duration ?? 6000,
  })
}
