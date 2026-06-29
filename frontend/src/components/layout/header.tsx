'use client'

import { Menu, Bell, Search, Settings, LogOut, User } from 'lucide-react'
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
import { cn } from '@/lib/utils'
import { useAuth } from '@/app/auth-provider'
import { useRouter } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { useEffect, useState } from 'react'
import { getLinkedInProfileHealth } from '@/lib/api/dashboard'
import { LinkedInProfileHealthResponse } from '@/lib/types/components'
import { AlertCircle } from 'lucide-react'
import { getNotificationSummary, markNotificationAsRead, Notification } from '@/lib/api/notifications'

interface HeaderProps {
  onMenuClick: () => void
  className?: string
}

const Header = ({ onMenuClick, className }: HeaderProps) => {
  const { isAuthenticated, user } = useAuth()
  const router = useRouter()
  
  // Get user's display name from Supabase user_metadata or derive from email
  const userName = user?.user_metadata?.full_name || (user?.email ? user.email.split('@')[0] : 'User')
  const userEmail = user?.email || 'user@example.com'
  const [linkedinHealth, setLinkedinHealth] = useState<LinkedInProfileHealthResponse | null>(null)
  const [loadingHealth, setLoadingHealth] = useState(true)
  
  // Notification state
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loadingNotifications, setLoadingNotifications] = useState(false)
  const [notificationMenuOpen, setNotificationMenuOpen] = useState(false)

  const fetchLinkedInHealth = async () => {
    try {
      const response = await getLinkedInProfileHealth()
      if (response.data) {
        setLinkedinHealth(response.data)
      }
    } catch (error) {
      console.error('Failed to fetch LinkedIn profile health:', error)
    } finally {
      setLoadingHealth(false)
    }
  }

  // Get the worst health status among all profiles
  const getOverallHealthStatus = () => {
    if (!linkedinHealth?.profiles || linkedinHealth.profiles.length === 0) {
      return { label: 'No Profile', color: 'bg-slate-500' }
    }

    // Process profiles to find worst status
    let worstStatus: 'neutral' | 'locked' | 'expired' | 'invalid' | 'active' = 'neutral'
    
    // Sort profiles by severity (invalid > locked > expired > active > neutral)
    for (const profile of linkedinHealth.profiles) {
      if (profile.credentials_status === 'invalid') {
        return { label: 'LinkedIn Invalid', color: 'bg-red-500' }
      }
    }
    
    for (const profile of linkedinHealth.profiles) {
      if (profile.credentials_status === 'locked') {
        worstStatus = 'locked'
      }
    }
    
    for (const profile of linkedinHealth.profiles) {
      if (profile.credentials_status === 'expired') {
        if (worstStatus === 'neutral') {
          worstStatus = 'expired'
        }
      }
    }
    
    for (const profile of linkedinHealth.profiles) {
      if (profile.credentials_status === 'active') {
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
      if (profile.credentials_status === 'invalid' && profile.last_error) {
        return `LinkedIn Invalid: ${profile.last_error}`
      }
      if (profile.credentials_status === 'locked' && profile.last_error) {
        return `LinkedIn Locked: ${profile.last_error}`
      }
      if (profile.credentials_status === 'expired' && profile.last_error) {
        return `LinkedIn Expired: ${profile.last_error}`
      }
    }

    // Show last verification if available
    for (const profile of linkedinHealth.profiles) {
      if (profile.last_verification) {
        return `Last verified: ${new Date(profile.last_verification).toLocaleDateString()}`
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
          const response = await getLinkedInProfileHealth()
          if (response.data) {
            setLinkedinHealth(response.data)
          }
        } catch (error) {
          console.error('Failed to fetch LinkedIn profile health:', error)
        } finally {
          setLoadingHealth(false)
        }
      })()
    }
  }, [isAuthenticated])

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

  // Handle clicking a notification to mark as read
  const handleNotificationClick = async (notificationId: number) => {
    try {
      await markNotificationAsRead(notificationId)
      // Refresh notifications
      const response = await getNotificationSummary()
      if (response.data) {
        setNotifications(response.data.recent_notifications || [])
        setUnreadCount(response.data.unread_count || 0)
      }
    } catch (error) {
      console.error('Failed to mark notification as read:', error)
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
        <div className="hidden md:flex items-center gap-2">
          {loadingHealth ? (
            <div className="flex items-center gap-2 px-2 py-1">
              <div className="h-4 w-4 rounded-full border-2 border-slate-500 border-t-transparent animate-spin" />
              <span className="text-xs text-muted-foreground">Checking...</span>
            </div>
          ) : (
            <div 
              className="cursor-pointer hover:opacity-90 transition-opacity"
              title={getTooltipContent()}
              onClick={handleBadgeClick}
            >
              <Badge variant="outline" className={cn(
                'gap-2 px-3 py-1 cursor-pointer',
                healthStatus.color,
                'text-white border-transparent'
              )}>
                <span className="h-2 w-2 rounded-full bg-current" />
                {healthStatus.label}
              </Badge>
            </div>
          )}
        </div>


        <DropdownMenu open={notificationMenuOpen} onOpenChange={setNotificationMenuOpen}>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute right-1 top-1 h-5 w-5 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center font-bold animate-pulse">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-96">
            <div className="px-4 py-3 border-b">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Notifications</h3>
                {unreadCount > 0 && (
                  <Badge variant="secondary" className="text-xs">
                    {unreadCount} unread
                  </Badge>
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
                      className={`flex gap-3 p-3 border-b last:border-0 hover:bg-accent ${!notification.is_read ? 'bg-accent/50' : ''}`}
                      onClick={() => handleNotificationClick(notification.id)}
                    >
                      <div className="flex-shrink-0">
                        {notification.is_read ? (
                          <Icons.Bell className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          getNotificationIcon(notification.notification_type)
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium ${!notification.is_read ? 'font-semibold' : ''}`}>
                          {notification.title}
                        </p>
                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                          {notification.message}
                        </p>
                        <p className="text-[10px] text-muted-foreground mt-1">
                          {getTimeAgo(notification.created_at)}
                        </p>
                      </div>
                      {!notification.is_read && (
                        <div className="h-2 w-2 rounded-full bg-blue-500 flex-shrink-0" />
                      )}
                    </DropdownMenuItem>
                  ))}
                </>
              )}
            </div>
            {notifications.length > 0 && (
              <div className="border-t p-2">
                <div className="text-xs text-center text-muted-foreground">
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
          <DropdownMenuContent align="end" className="w-56">
            <div className="flex items-center gap-2 px-2 py-2">
              <div className="h-9 w-9 overflow-hidden rounded-full bg-muted">
                <span className="flex h-full w-full items-center justify-center font-medium text-xs">
                  {userName.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex flex-col overflow-hidden">
                <span className="text-sm font-medium truncate">{userName}</span>
                <span className="text-xs text-muted-foreground truncate">{userEmail}</span>
              </div>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2" onClick={() => router.push('/settings/profile')}>
              <User className="h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2" onClick={() => router.push('/settings')}>
              <Settings className="h-4 w-4" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <a href="/api/auth/logout" className="cursor-pointer">
                <LogOut className="h-4 w-4" />
                Logout
              </a>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}

export { Header }