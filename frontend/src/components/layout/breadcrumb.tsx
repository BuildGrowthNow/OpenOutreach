'use client'

// ChevronRight is imported but not used - kept for potential future use
import { cn } from '@/lib/utils'
import Link from 'next/link'

interface BreadcrumbItem {
  label: string
  href?: string
  isActive?: boolean
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
  separator?: React.ReactNode
  className?: string
}

const Breadcrumb = ({
  items,
  separator = <div className="h-4 w-4 text-muted-foreground">/</div>,
  className
}: BreadcrumbProps) => {

  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center gap-2 text-sm', className)}>
      <ol className="flex items-center gap-2">
        {items.map((item, index) => {
          const isLast = index === items.length - 1
          return (
            <li key={index} className="flex items-center gap-2">
              {isLast ? (
                <span className="font-medium text-foreground">{item.label}</span>
              ) : (
                <Link
                  href={item.href || '#'}
                  className="font-medium text-muted-foreground transition-colors hover:text-foreground"
                >
                  {item.label}
                </Link>
              )}
              {!isLast && <div className="text-muted-foreground">{separator}</div>}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export { Breadcrumb }