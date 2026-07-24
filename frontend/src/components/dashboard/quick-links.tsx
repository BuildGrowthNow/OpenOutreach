'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Users,
  BarChart2,
  Settings,
  Plus,
  MessageSquare,
} from 'lucide-react'

const links = [
  { label: 'New Campaign', href: '/campaigns', icon: Plus, description: 'Start a new outreach campaign' },
  { label: 'All Campaigns', href: '/campaigns', icon: LayoutDashboard, description: 'View and manage campaigns' },
  { label: 'Leads', href: '/leads', icon: Users, description: 'Browse all discovered leads' },
  { label: 'Analytics', href: '/analytics', icon: BarChart2, description: 'Review performance metrics' },
  { label: 'Messages', href: '/messages', icon: MessageSquare, description: 'View all conversations' },
  { label: 'Settings', href: '/settings', icon: Settings, description: 'Configure account & rate limits' },
]

interface QuickLinksProps {
  className?: string
}

export function QuickLinks({ className }: QuickLinksProps) {
  const router = useRouter()

  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader>
        <CardTitle className="text-base">Quick Links</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col justify-between gap-0">
        {links.map(({ label, href, icon: Icon, description }) => (
          <button
            key={label}
            onClick={() => router.push(href)}
            className="flex items-center gap-3 py-2.5 border-b last:border-b-0 hover:text-foreground text-left group transition-colors"
          >
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted group-hover:bg-primary/10 transition-colors">
              <Icon className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium leading-none">{label}</div>
              <div className="text-xs text-muted-foreground mt-0.5 truncate">{description}</div>
            </div>
          </button>
        ))}
      </CardContent>
    </Card>
  )
}
