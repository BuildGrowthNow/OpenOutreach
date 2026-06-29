'use client'

import { useEffect, useState, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { toast } from '@/components/ui/use-toast'
import { Icons } from '@/lib/types/components'
import {
  Notification,
  NotificationType,
  getNotificationSummary,
  markNotificationAsRead,
} from '@/lib/api/notifications'
import {
  showToastCampaignStatus,
  showToastRateLimitWarning,
  showToastNewMessage,
  showToastSuccess,
  showToastError,
  showToastInfo,
  showToastWarning,
} from '@/lib/notification/toast'

/**
 * Notification service for managing and displaying toast notifications
 */
export function useNotificationService() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [notificationMenuOpen, setNotificationMenuOpen] = useState(false)

  /**
   * Fetch notifications from the server
   */
  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true)
      const response = await getNotificationSummary()
      if (response.data) {
        setNotifications(response.data.recent_notifications || [])
        setUnreadCount(response.data.unread_count || 0)
      }
    } catch (error) {
      console.error('Failed to fetch notifications:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  /**
   * Mark a notification as read
   */
  const handleNotificationClick = async (notificationId: number) => {
    try {
      await markNotificationAsRead(notificationId)
      await fetchNotifications()
    } catch (error) {
      console.error('Failed to mark notification as read:', error)
    }
  }

  /**
   * Display toast notification based on type
   */
  const showToastForNotification = (notification: Notification) => {
    const { notification_type, title, message, campaign_name, recipient_username } = notification

    switch (notification_type) {
      case 'campaign_started':
        showToastCampaignStatus(campaign_name || 'Campaign', 'started', {
          title,
          description: message,
        })
        break

      case 'campaign_paused':
        showToastCampaignStatus(campaign_name || 'Campaign', 'paused', {
          title,
          description: message,
        })
        break

      case 'campaign_completed':
        showToastCampaignStatus(campaign_name || 'Campaign', 'completed', {
          title,
          description: message,
        })
        break

      case 'rate_limit_warning':
        showToastRateLimitWarning(recipient_username || 'Unknown', message)
        break

      case 'new_message':
        showToastNewMessage(
          recipient_username || 'Unknown',
          campaign_name || 'Campaign',
          message
        )
        break

      case 'campaign_error':
        showToastError(title || 'Campaign Error', message)
        break

      case 'system_announcement':
        showToastInfo(title || 'System Announcement', message)
        break

      default:
        showToastInfo(title || 'Notification', message)
    }
  }

  /**
   * Show notifications for unread items
   */
  const showUnreadNotifications = () => {
    const unread = notifications.filter((n) => !n.is_read)
    unread.forEach((notification) => {
      showToastForNotification(notification)
    })
  }

  /**
   * Initialize notification service with auto-refresh
   */
  useEffect(() => {
    void fetchNotifications()

    // Poll for notifications every 30 seconds
    const interval = setInterval(() => {
      void fetchNotifications()
    }, 30000)

    return () => clearInterval(interval)
  }, [fetchNotifications])

  return {
    notifications,
    unreadCount,
    loading,
    notificationMenuOpen,
    setNotificationMenuOpen,
    fetchNotifications,
    handleNotificationClick,
    showToastForNotification,
    showUnreadNotifications,
  }
}

export default useNotificationService