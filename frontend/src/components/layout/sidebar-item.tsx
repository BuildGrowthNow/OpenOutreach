import React from 'react'
import { cn } from '@/lib/utils'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

interface SidebarItemProps {
  title: string
  href: string
  icon: React.ElementType
  isActive?: boolean
  isCollapsed?: boolean
  className?: string
}

const SidebarItem = ({
  title,
  href,
  icon: Icon,
  isActive,
  isCollapsed = false,
  className
}: SidebarItemProps) => {
  const pathname = usePathname()
  const active = isActive !== null && isActive !== undefined ? isActive : (pathname === href || pathname.startsWith(`${href}/`))

  return (
    <Link
      href={href}
      className={cn(
        'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
        active
          ? 'bg-primary text-primary-foreground hover:bg-primary/90'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        className
      )}
    >
      <Icon className={cn('h-5 w-5 shrink-0', active && 'text-primary-foreground')} />
      <span className={cn('truncate transition-all', isCollapsed && 'hidden')}>{title}</span>
      {active && !isCollapsed && (
        <div className="ml-auto h-2 w-2 rounded-full bg-primary-foreground" />
      )}
    </Link>
  )
}

export { SidebarItem }