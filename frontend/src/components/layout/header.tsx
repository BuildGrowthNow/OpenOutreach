'use client'

import { Menu, Bell, Search, Settings, LogOut, Monitor, CreditCard, Mail } from 'lucide-react'
import { Icons } from '@/lib/types/components'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/lib/authStoreV2'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { getLinkedInProfileHealth } from '@/lib/api/dashboard'
import { LinkedInProfileHealthResponse } from '@/lib/types/components'
import { listWhatsAppProfiles, type WhatsAppProfile } from '@/lib/api/whatsapp'
import { listMailboxes, type Mailbox } from '@/lib/api/mailboxes'
import { getNotificationSummary, markNotificationAsRead, markAllNotificationsAsRead, Notification } from '@/lib/api/notifications'

interface HeaderProps {
  onMenuClick: () => void
  className?: string
}

const Header = ({ onMenuClick, className }: HeaderProps) => {
  const { isAuthenticated, user, logout } = useAuthStore()
  const router = useRouter()

  const userName = user?.full_name || (user?.email ? user.email.split('@')[0] : 'User')
  const userEmail = user?.email || 'user@example.com'
  const [linkedinHealth, setLinkedinHealth] = useState<LinkedInProfileHealthResponse | null>(null)
  const [loadingHealth, setLoadingHealth] = useState(true)
  const [isDesktop, setIsDesktop] = useState(false)
  const [waProfiles, setWaProfiles] = useState<WhatsAppProfile[]>([])
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([])

  useEffect(() => {
    setIsDesktop(!!(window as unknown as Record<string, unknown>)['__LENGROWTH_DESKTOP__'])
  }, [])
  
  // Notification state
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loadingNotifications, setLoadingNotifications] = useState(false)
  const [notificationMenuOpen, setNotificationMenuOpen] = useState(false)

  // Get the worst health status among all profiles
  const getOverallHealthStatus = () => {
    if (!linkedinHealth?.profiles || linkedinHealth.profiles.length === 0) {
      return { label: 'No Profile', color: 'bg-slate-500' }
    }

    // Process profiles to find worst status
    let worstStatus: 'neutral' | 'locked' | 'expired' | 'invalid' | 'active' = 'neutral'
    
    // Sort profiles by severity (invalid > locked > expired > active > neutral)
    for (const profile of linkedinHealth.profiles) {
      if (profile.credentialsStatus === 'invalid') {
        return { label: 'LinkedIn Invalid', color: 'bg-red-500' }
      }
    }

    for (const profile of linkedinHealth.profiles) {
      if (profile.credentialsStatus === 'locked') {
        worstStatus = 'locked'
      }
    }

    for (const profile of linkedinHealth.profiles) {
      if (profile.credentialsStatus === 'expired') {
        if (worstStatus === 'neutral') {
          worstStatus = 'expired'
        }
      }
    }

    for (const profile of linkedinHealth.profiles) {
      if (profile.credentialsStatus === 'active') {
        if (worstStatus === 'neutral') {
          worstStatus = 'active'
        }
      }
    }

    const statusColors: Record<'neutral' | 'locked' | 'expired' | 'invalid' | 'active', { label: string; color: string }> = {
      active: { label: 'LinkedIn Active', color: 'bg-green-500' },
      locked: { label: 'LinkedIn Locked', color: 'bg-amber-500' },
      expired: { label: 'LinkedIn Expired', color: 'bg-rose-500' },
      invalid: { label: 'LinkedIn Invalid', color: 'bg-red-500' },
      neutral: { label: 'LinkedIn', color: 'bg-slate-500' },
    }

    return statusColors[worstStatus]
  }

  // Compute health status after data is fetched
  const healthStatus = getOverallHealthStatus()

  // Get first profile with error for tooltip
  const getTooltipContent = () => {
    if (!linkedinHealth?.profiles || linkedinHealth.profiles.length === 0) {
      return 'LinkedIn Profile Not Configured'
    }

    for (const profile of linkedinHealth.profiles) {
      if (profile.credentialsStatus === 'invalid' && profile.lastError) {
        return `LinkedIn Invalid: ${profile.lastError}`
      }
      if (profile.credentialsStatus === 'locked' && profile.lastError) {
        return `LinkedIn Locked: ${profile.lastError}`
      }
      if (profile.credentialsStatus === 'expired' && profile.lastError) {
        return `LinkedIn Expired: ${profile.lastError}`
      }
    }

    // Show last verification if available
    for (const profile of linkedinHealth.profiles) {
      if (profile.lastVerification) {
        return `Last verified: ${new Date(profile.lastVerification).toLocaleDateString()}`
      }
    }

    return 'Click to configure LinkedIn'
  }

  const handleBadgeClick = () => {
    if (typeof window !== 'undefined') {
      window.location.href = '/settings?tab=linkedin-credentials'
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      (async () => {
        try {
          const [healthRes, waRes, mbRes] = await Promise.all([
            getLinkedInProfileHealth(),
            listWhatsAppProfiles().catch(() => [] as WhatsAppProfile[]),
            listMailboxes().catch(() => [] as Mailbox[]),
          ])
          if (healthRes.data) setLinkedinHealth(healthRes.data)
          setWaProfiles(waRes)
          setMailboxes(mbRes)
        } catch (error) {
          console.error('Failed to fetch profile health:', error)
        } finally {
          setLoadingHealth(false)
        }
      })()
    }
  }, [isAuthenticated])

  const getWaHealthStatus = () => {
    if (!waProfiles.length) return { label: 'WhatsApp', color: 'bg-slate-500', tooltip: 'WhatsApp: Not configured' }
    const hasBanned = waProfiles.some((p) => p.status === 'banned')
    if (hasBanned) return { label: 'WA Banned', color: 'bg-red-500', tooltip: 'WhatsApp: Account banned' }
    const hasConnected = waProfiles.some((p) => p.status === 'connected')
    if (hasConnected) return { label: 'WA Active', color: 'bg-green-500', tooltip: 'WhatsApp: Connected' }
    return { label: 'WA Disconnected', color: 'bg-slate-500', tooltip: 'WhatsApp: Disconnected - scan QR to connect' }
  }

  const waStatus = getWaHealthStatus()

  const getEmailHealthStatus = () => {
    if (!mailboxes.length) return { label: 'Email', color: 'bg-slate-500', tooltip: 'Email: No mailboxes configured' }
    const total = mailboxes.reduce((sum, m) => sum + m.headroomToday, 0)
    if (total === 0) return { label: 'Email Full', color: 'bg-amber-500', tooltip: 'Email: Daily send limit reached' }
    return { label: 'Email Active', color: 'bg-green-500', tooltip: `Email: ${mailboxes.length} mailbox${mailboxes.length > 1 ? 'es' : ''} active` }
  }

  const emailStatus = getEmailHealthStatus()

  // Fetch notifications on mount and when auth status changes
  useEffect(() => {
    const fetchNotifications = async () => {
      if (!isAuthenticated) {
        setNotifications([])
        setUnreadCount(0)
        return
      }
      
      try {
        setLoadingNotifications(true)
        const response = await getNotificationSummary()
        if (response.data) {
          setNotifications(response.data.recent_notifications || [])
          setUnreadCount(response.data.unread_count || 0)
        }
      } catch (error) {
        console.error('Failed to fetch notifications:', error)
      } finally {
        setLoadingNotifications(false)
      }
    }
    
    fetchNotifications()
    
    // Poll for notifications every 30 seconds
    const interval = setInterval(fetchNotifications, 30000)
    
    return () => clearInterval(interval)
  }, [isAuthenticated])

  const refreshNotifications = async () => {
    const response = await getNotificationSummary()
    if (response.data) {
      setNotifications(response.data.recent_notifications || [])
      setUnreadCount(response.data.unread_count || 0)
    }
  }

  const handleNotificationClick = async (notificationId: number) => {
    try {
      await markNotificationAsRead(notificationId)
      await refreshNotifications()
    } catch (error) {
      console.error('Failed to mark notification as read:', error)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsAsRead()
      await refreshNotifications()
    } catch (error) {
      console.error('Failed to mark all notifications as read:', error)
    }
  }

  // Format notification type to display name
  const getNotificationTypeName = (type: string) => {
    const typeMap: Record<string, string> = {
      campaign_started: 'Campaign Started',
      campaign_paused: 'Campaign Paused',
      campaign_completed: 'Campaign Completed',
      rate_limit_warning: 'Rate Limit',
      new_message: 'New Message',
      campaign_error: 'Campaign Error',
      system_announcement: 'System',
    }
    return typeMap[type] || type.replace('_', ' ').toUpperCase()
  }

  // Get notification icon based on type
  const getNotificationIcon = (type: string) => {
    const iconMap: Record<string, React.ReactNode> = {
      campaign_started: <Icons.Play className="h-4 w-4 text-emerald-500" />,
      campaign_paused: <Icons.Pause className="h-4 w-4 text-amber-500" />,
      campaign_completed: <Icons.CheckCircle className="h-4 w-4 text-blue-500" />,
      rate_limit_warning: <Icons.AlertTriangle className="h-4 w-4 text-rose-500" />,
      new_message: <Icons.MessageSquare className="h-4 w-4 text-purple-500" />,
      campaign_error: <Icons.AlertCircle className="h-4 w-4 text-red-500" />,
      system_announcement: <Icons.Bell className="h-4 w-4 text-slate-500" />,
    }
    return iconMap[type] || <Icons.Bell className="h-4 w-4 text-muted-foreground" />
  }

  // Get time ago string
  const getTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)
    
    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return `${days}d ago`
  }

  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-16 items-center gap-4 border-b bg-background/80 px-6 backdrop-blur-md',
        className
      )}
    >
      <Button variant="ghost" size="icon" onClick={onMenuClick} className="md:hidden">
        <Menu className="h-5 w-5" />
      </Button>

      <div className="flex-1">
        <div className="relative max-w-md">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search..."
            className="pl-9 w-full bg-background"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-3">
          {isDesktop ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-400">
              <Monitor className="h-3 w-3" />
              Desktop App
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/50 px-2.5 py-0.5 text-xs font-medium text-zinc-400">
              <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
              Web
            </span>
          )}

          {!loadingHealth && (
            <div className="flex items-center gap-2">
              <button
                className="relative p-1.5 rounded hover:bg-accent transition-colors"
                title={getTooltipContent()}
                onClick={handleBadgeClick}
                aria-label="LinkedIn status"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4 text-muted-foreground" aria-hidden="true">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                </svg>
                <span className={cn('absolute bottom-0.5 right-0.5 h-2 w-2 rounded-full border border-background', healthStatus.color)} />
              </button>
              <button
                className="relative p-1.5 rounded hover:bg-accent transition-colors"
                title={waStatus.tooltip}
                onClick={() => { window.location.href = '/settings?tab=whatsapp' }}
                aria-label="WhatsApp status"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4 text-muted-foreground" aria-hidden="true">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z"/>
                </svg>
                <span className={cn('absolute bottom-0.5 right-0.5 h-2 w-2 rounded-full border border-background', waStatus.color)} />
              </button>
              <button
                className="relative p-1.5 rounded hover:bg-accent transition-colors"
                title={emailStatus.tooltip}
                onClick={() => { window.location.href = '/settings?tab=email' }}
                aria-label="Email status"
              >
                <Mail className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                <span className={cn('absolute bottom-0.5 right-0.5 h-2 w-2 rounded-full border border-background', emailStatus.color)} />
              </button>
            </div>
          )}
        </div>


        <DropdownMenu open={notificationMenuOpen} onOpenChange={setNotificationMenuOpen}>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute bottom-1.5 right-1.5 h-2.5 w-2.5 rounded-full bg-red-500 border-2 border-background" />
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-96 bg-zinc-900 border-zinc-700">
            <div className="px-4 py-3 border-b border-zinc-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-zinc-100">Notifications</h3>
                  {unreadCount > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      {unreadCount} unread
                    </Badge>
                  )}
                </div>
                {unreadCount > 0 && (
                  <button
                    onClick={(e) => { e.stopPropagation(); void handleMarkAllRead() }}
                    className="text-xs text-zinc-400 hover:text-zinc-100 transition-colors"
                  >
                    Mark all as read
                  </button>
                )}
              </div>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {loadingNotifications ? (
                <div className="flex items-center justify-center py-8">
                  <div className="h-4 w-4 rounded-full border-2 border-slate-500 border-t-transparent animate-spin" />
                </div>
              ) : notifications.length === 0 ? (
                <div className="py-8 text-center">
                  <div className="mx-auto h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-3">
                    <Icons.Bell className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">No new notifications</p>
                </div>
              ) : (
                <>
                  {notifications.map((notification) => (
                    <DropdownMenuItem
                      key={notification.id}
                      className={cn(
                        'flex gap-3 p-3 border-b border-zinc-700 last:border-0 cursor-pointer',
                        'hover:bg-zinc-800 focus:bg-zinc-800 data-[highlighted]:bg-zinc-800',
                        !notification.is_read ? 'bg-zinc-800/50' : 'bg-transparent',
                      )}
                      onClick={() => void handleNotificationClick(notification.id)}
                    >
                      <div className="flex-shrink-0 mt-0.5">
                        {notification.is_read ? (
                          <Icons.Bell className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          getNotificationIcon(notification.notification_type)
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm ${!notification.is_read ? 'font-semibold text-zinc-100' : 'font-medium text-zinc-300'}`}>
                          {notification.title}
                        </p>
                        <p className="text-xs text-zinc-400 truncate mt-0.5">
                          {notification.message}
                        </p>
                        <p className="text-[10px] text-zinc-500 mt-1">
                          {getTimeAgo(notification.created_at)}
                        </p>
                      </div>
                      <div className="flex items-start gap-2 flex-shrink-0">
                        {!notification.is_read && (
                          <>
                            <div className="h-2 w-2 rounded-full bg-blue-500 mt-1.5" />
                            <button
                              onClick={(e) => { e.stopPropagation(); void handleNotificationClick(notification.id) }}
                              className="text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors whitespace-nowrap"
                            >
                              Mark read
                            </button>
                          </>
                        )}
                      </div>
                    </DropdownMenuItem>
                  ))}
                </>
              )}
            </div>
            {notifications.length > 0 && (
              <div className="border-t border-zinc-700 p-2">
                <div className="text-xs text-center text-zinc-500">
                  Showing latest {notifications.length} notifications
                </div>
              </div>
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="h-8 w-px bg-border mx-1" />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full">
              <div className="h-8 w-8 overflow-hidden rounded-full bg-muted">
                <span className="flex h-full w-full items-center justify-center font-medium">
                  {userName.charAt(0).toUpperCase()}
                </span>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64 p-2">
            <div className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-accent">
              <div className="h-10 w-10 overflow-hidden rounded-full bg-muted">
                <span className="flex h-full w-full items-center justify-center font-medium text-sm">
                  {userName.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex flex-col overflow-hidden">
                <span className="text-sm font-medium truncate">{userName}</span>
                <span className="text-xs text-muted-foreground truncate">{userEmail}</span>
              </div>
            </div>
            <DropdownMenuSeparator className="bg-zinc-200/20 my-2" />
            <DropdownMenuItem className="gap-2 rounded-md px-2 py-1.5 transition-colors" onClick={() => router.push('/settings')}>
              <Settings className="h-4 w-4" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2 rounded-md px-2 py-1.5 transition-colors" onClick={() => router.push('/settings/billing')}>
              <CreditCard className="h-4 w-4" />
              Billing
            </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-zinc-200/20 my-2" />
             <DropdownMenuItem className="gap-2 rounded-md px-2 py-1.5 transition-colors cursor-pointer" onClick={async () => {
               try {
                 await logout()
               } catch (error) {
                 console.error('Logout error:', error)
                 window.location.href = '/login'
               }
             }}>
               <LogOut className="h-4 w-4" />
               Logout
             </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}

export { Header }