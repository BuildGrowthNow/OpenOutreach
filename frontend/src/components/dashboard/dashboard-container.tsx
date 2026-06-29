'use client'

import { cn } from '@/lib/utils'

interface DashboardContainerProps {
  children: React.ReactNode
  className?: string
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full'
  padding?: 'none' | 'sm' | 'md' | 'lg' | 'xl'
}

/**
 * DashboardContainer - A reusable container component for dashboard pages
 * Provides consistent padding, max-width, and spacing
 */
export function DashboardContainer({
  children,
  className,
  maxWidth = '2xl',
  padding = 'lg',
}: DashboardContainerProps) {
  // Max-width classes
  const maxWidthClasses = {
    sm: 'max-w-3xl',
    md: 'max-w-4xl',
    lg: 'max-w-5xl',
    xl: 'max-w-6xl',
    '2xl': 'max-w-7xl',
    full: 'max-w-full',
  }

  // Padding classes - consistent spacing pattern
  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-4 md:p-6 lg:p-8',
    xl: 'p-6 md:p-8 lg:p-10',
  }

  return (
    <div className={cn('flex-1 overflow-y-auto bg-background', maxWidthClasses[maxWidth], paddingClasses[padding], className)}>
      {children}
    </div>
  )
}