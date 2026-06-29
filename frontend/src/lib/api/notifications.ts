'use client'

import { get, post, patch, del, ApiResponse } from '../api'

// Notification types
export type NotificationType = 
  | 'campaign_started'
  | 'campaign_paused'
  | 'campaign_completed'
  | 'rate_limit_warning'
  | 'new_message'
  | 'campaign_error'
  | 'system_announcement'

// Notification interface
export interface Notification {
  id: number
  recipient: number
  recipient_username?: string
  notification_type: NotificationType
  title: string
  message: string
  campaign?: number
  campaign_name?: string
  deal?: number
  deal_name?: string
  is_read: boolean
  read_at?: string
  data?: Record<string, unknown>
  created_at: string
}

// Notification summary interface
export interface NotificationSummary {
  unread_count: number
  recent_notifications: Notification[]
}

// Notification list response
export interface NotificationListResponse {
  data: Notification[]
  pagination: {
    page: number
    limit: number
    total: number
  }
  unread_count: number
}

// Notification API Functions
export async function getNotifications(
  isRead?: boolean,
  type?: string,
  page?: number,
  limit?: number
): Promise<ApiResponse<NotificationListResponse>> {
  const params: Record<string, string> = {}
  if (isRead !== undefined) params.is_read = isRead.toString()
  if (type) params.type = type
  if (page) params.page = page.toString()
  if (limit) params.limit = limit.toString()
  return get('/api/notifications', params)
}

export async function getNotificationSummary(): Promise<ApiResponse<NotificationSummary>> {
  return get('/api/notifications/summary')
}

export async function markAllNotificationsAsRead(): Promise<ApiResponse<{ success: boolean; updated_count: number }>> {
  return post('/api/notifications/read-all', {})
}

export async function markNotificationAsRead(id: number): Promise<ApiResponse<{ success: boolean; message: string }>> {
  return patch(`/api/notifications/${id}/read`, {})
}

export async function deleteNotification(id: number): Promise<ApiResponse<{ success: boolean; message: string }>> {
  return del(`/api/notifications/${id}`)
}