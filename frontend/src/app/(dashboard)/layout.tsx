'use client'

import { useState } from 'react'
import { Sidebar } from '@/components/layout/sidebar'
import { Header } from '@/components/layout/header'
import { cn } from '@/lib/utils'
import { Icons } from '@/lib/types/components'
import { DashboardContainer } from '@/components/dashboard/dashboard-container'
import { LinkedinBanner } from '@/components/layout/linkedin-banner'

type SidebarIcon = keyof typeof Icons

interface SidebarItem {
  title: string
  href: string
  icon: SidebarIcon
}

const dashboardItems: SidebarItem[] = [
  {
    title: 'Dashboard',
    href: '/dashboard',
    icon: 'LayoutDashboard'
  },
  {
    title: 'Campaigns',
    href: '/campaigns',
    icon: 'BarChart3'
  },
  {
    title: 'Leads',
    href: '/leads',
    icon: 'Users'
  },
  {
    title: 'Messages',
    href: '/messages',
    icon: 'MessageSquare'
  },
  {
    title: 'State Machine',
    href: '/state-machine',
    icon: 'Workflow'
  },
  {
    title: 'Analytics',
    href: '/analytics',
    icon: 'BarChartBig'
  },
  {
    title: 'Links',
    href: '/links',
    icon: 'Link'
  },
  {
    title: 'Settings',
    href: '/settings',
    icon: 'Settings'
  },
]

interface DashboardLayoutProps {
  children: React.ReactNode
}

const DashboardLayout = ({ children }: DashboardLayoutProps) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  return (
    <div className={cn('flex h-screen overflow-hidden dark')}>
      {/* LinkedIn Connection Banner - Shows at top when LinkedIn is not connected */}
      <LinkedinBanner />

      {/* Sidebar */}
      <Sidebar
        items={dashboardItems}
        isOpen={isSidebarOpen}
        setIsOpen={setIsSidebarOpen}
      />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden bg-background">
        {/* Header */}
        <Header
          onMenuClick={() => setIsSidebarOpen(true)}
        />

        {/* Page Content - Now wrapped in DashboardContainer for consistent padding */}
        <DashboardContainer>
          {children}
        </DashboardContainer>
      </div>
    </div>
  )
}

export default DashboardLayout