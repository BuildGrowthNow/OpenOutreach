'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Icons } from '@/lib/types/components'

interface SidebarItem {
  title: string
  href: string
  icon: keyof typeof Icons
  description?: string
}

interface SidebarProps {
  items: SidebarItem[]
  isOpen: boolean
  setIsOpen: (isOpen: boolean) => void
}

const Sidebar = ({ items, isOpen, setIsOpen }: SidebarProps) => {
  const pathname = usePathname()

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-background
          transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0
        `}
      >
        {/* Logo */}
        <div className="flex h-16 items-center border-b px-6">
          <div className="flex items-center gap-2 font-bold text-xl">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              {React.createElement(Icons.Sparkles, { className: "h-5 w-5" })}
            </div>
            <span>OpenOutreach</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <div className="space-y-0.5">
            {items.map((item, index) => {
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
              return (
                <div key={item.href} className="relative">
                  <Link href={item.href}>
                    <Button
                      variant={isActive ? 'secondary' : 'ghost'}
                      className={`
                        w-full justify-start gap-3 rounded-lg
                        hover:bg-accent hover:text-accent-foreground
                        data-[active=true]:bg-accent data-[active=true]:text-accent-foreground
                      `}
                      data-active={isActive}
                    >
                      {React.createElement(Icons[item.icon], { className: "h-4 w-4" })}
                      <div className="flex flex-col items-start text-left flex-1">
                        <span className="text-sm font-medium">{item.title}</span>
                        {item.description && (
                          <span className="text-[0.7rem] text-muted-foreground">
                            {item.description}
                          </span>
                        )}
                      </div>
                      {isActive && (
                        <span className="ml-auto flex h-4 w-4 items-center justify-center">
                          <span className="absolute h-2 w-2 rounded-full bg-current opacity-50"></span>
                        </span>
                      )}
                    </Button>
                  </Link>
                  {index < items.length - 1 && (
                    <div className="mx-4 h-px bg-border" />
                  )}
                </div>
              )
            })}
          </div>
        </nav>

        {/* Footer - Logout */}
        <div className="border-t p-3">
          <Link href="/api/auth/logout">
            <Button variant="outline" className="w-full justify-start gap-2">
              {React.createElement(Icons.LogOut, { className: "h-4 w-4" })}
              <span className="text-sm">Logout</span>
            </Button>
          </Link>
        </div>
      </aside>
    </>
  )
}

export { Sidebar }