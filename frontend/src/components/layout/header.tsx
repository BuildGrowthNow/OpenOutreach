'use client'

import { Moon, Sun, Menu, Bell, Search, Settings, LogOut } from 'lucide-react'
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
import { Badge } from '@/components/ui/badge'
import { useEffect, useState } from 'react'
import { getLinkedInProfileHealth } from '@/lib/api/dashboard'
import { LinkedInProfileHealthResponse } from '@/lib/types/components'

interface HeaderProps {
  onMenuClick: () => void
  theme: 'light' | 'dark'
  toggleTheme: () => void
  className?: string
}

const Header = ({ onMenuClick, theme, toggleTheme, className }: HeaderProps) => {
  const { isAuthenticated } = useAuth()
  const [linkedinHealth, setLinkedinHealth] = useState<LinkedInProfileHealthResponse | null>(null)
  const [loadingHealth, setLoadingHealth] = useState(true)

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

  // Compute health status after data is fetched
  const healthStatus = getOverallHealthStatus()

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
            <Badge variant="outline" className={cn(
              'gap-2 px-3 py-1',
              healthStatus.color,
              'text-white border-transparent'
            )}>
              <span className="h-2 w-2 rounded-full bg-current" />
              {healthStatus.label}
            </Badge>
          )}
        </div>

        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          {theme === 'dark' ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80">
            <div className="px-2 py-2">
              <h3 className="text-sm font-medium">Notifications</h3>
            </div>
            <DropdownMenuSeparator />
            <div className="max-h-64 overflow-y-auto p-2">
              <p className="text-sm text-muted-foreground text-center py-4">
                No new notifications
              </p>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="h-8 w-px bg-border mx-1" />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full">
              <div className="h-8 w-8 overflow-hidden rounded-full bg-muted">
                <span className="flex h-full w-full items-center justify-center font-medium">
                  U
                </span>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <div className="flex items-center gap-2 px-2 py-2">
              <div className="h-9 w-9 overflow-hidden rounded-full bg-muted">
                <span className="flex h-full w-full items-center justify-center font-medium text-xs">
                  U
                </span>
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-medium">User</span>
                <span className="text-xs text-muted-foreground">user@example.com</span>
              </div>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2">
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