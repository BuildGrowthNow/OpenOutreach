'use client'

import { useState } from 'react'
import { Sidebar } from '@/components/layout/sidebar'
import { Header } from '@/components/layout/header'
import { cn } from '@/lib/utils'
import { Icons } from '@/lib/types/components'

type SidebarIcon = keyof typeof Icons

interface SidebarItem {
  title: string
  href: string
  icon: SidebarIcon
  description?: string
}

const dashboardItems: SidebarItem[] = [
  {
    title: 'Dashboard',
    href: '/dashboard',
    icon: 'LayoutDashboard',
    description: 'Overview & stats'
  },
  {
    title: 'Campaigns',
    href: '/campaigns',
    icon: 'BarChart3',
    description: 'Manage campaigns'
  },
  {
    title: 'Leads',
    href: '/leads',
    icon: 'Users',
    description: 'Lead management'
  },
  {
    title: 'Messages',
    href: '/messages',
    icon: 'MessageSquare',
    description: 'Communication'
  },
  {
    title: 'Analytics',
    href: '/analytics',
    icon: 'BarChartBig',
    description: 'Performance metrics'
  },
  {
    title: 'Links',
    href: '/links',
    icon: 'Link',
    description: 'Track links'
  },
  {
    title: 'Settings',
    href: '/settings',
    icon: 'Settings',
    description: 'System settings'
  },
]

interface DashboardLayoutProps {
  children: React.ReactNode
}

const DashboardLayout = ({ children }: DashboardLayoutProps) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light'
    }
    return 'dark'
  })

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  return (
    <div className={cn('flex h-screen overflow-hidden', theme === 'dark' ? 'dark' : '')}>
      {/* Sidebar */}
      <Sidebar
        items={dashboardItems}
        isOpen={isSidebarOpen}
        setIsOpen={setIsSidebarOpen}
      />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <Header
          onMenuClick={() => setIsSidebarOpen(true)}
          theme={theme}
          toggleTheme={toggleTheme}
        />

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto bg-background">
          {children}
        </main>
      </div>
    </div>
  )
}

export default DashboardLayout