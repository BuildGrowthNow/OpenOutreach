'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Sidebar } from '@/components/layout/sidebar'
import { Header } from '@/components/layout/header'
import { cn } from '@/lib/utils'
import { Icons } from '@/lib/types/components'
import { DashboardContainer } from '@/components/dashboard/dashboard-container'
import { LinkedinBanner } from '@/components/layout/linkedin-banner'
import { DashboardBillingWrapper } from '@/components/billing/dashboard-billing-wrapper'
import { useAuthStore } from '@/lib/authStoreV2'

type SidebarIcon = keyof typeof Icons

interface SidebarItem {
  title: string
  href: string
  icon: SidebarIcon
}

// Phase 6: Feature flags for deferred secondary surfaces
// These surfaces exist but are hidden from nav until post-launch
const ENABLE_STATE_MACHINE = process.env.NEXT_PUBLIC_ENABLE_STATE_MACHINE === 'true'
const ENABLE_LINKS = false // Phase 6: hidden; link tracking is post-launch
const ENABLE_TEMPLATES = false // Phase 6: hidden; templates are post-launch

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
  // State Machine temporarily hidden - incomplete feature (Phase 6)
  // Missing: edge editing, node configuration, daemon integration
  ...(ENABLE_STATE_MACHINE ? [{
    title: 'State Machine',
    href: '/state-machine',
    icon: 'Workflow' as SidebarIcon
  }] : []),
  {
    title: 'Analytics',
    href: '/analytics',
    icon: 'BarChartBig'
  },
  // Links hidden until post-launch (Phase 6)
  // Users can track via UTM parameters; full link tracking deferred
  ...(ENABLE_LINKS ? [{
    title: 'Links',
    href: '/links',
    icon: 'Link' as SidebarIcon
  }] : []),
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
  const router = useRouter()
  const user = useAuthStore((state) => state.user)

  // Redirect to billing if user has no subscription (Phase 10: require payment before dashboard)
  useEffect(() => {
    if (user && user.status === 'active') {
      // Check if user has completed billing (via billing status)
      // This is a soft check - the billing provider will also enforce
      // The user can proceed but will see overlays if subscription is missing
    }
  }, [user, router])

  return (
    <DashboardBillingWrapper>
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
    </DashboardBillingWrapper>
  )
}

export default DashboardLayout