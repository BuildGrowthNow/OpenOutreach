'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Icons } from '@/lib/types/components'

interface SidebarItem {
  title: string
  href: string
  icon: keyof typeof Icons
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
            <span>Lengrowth</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2">
          <div className="space-y-1 px-2">
            {items.map((item, index) => {
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
              return (
                <React.Fragment key={item.href}>
                  <div className="relative group">
                    <Link href={item.href}>
                      <Button
                        variant={isActive ? 'secondary' : 'ghost'}
                        size="sm"
                        className="w-full justify-start gap-3 rounded-md px-2"
                        data-active={isActive}
                      >
                        {React.createElement(Icons[item.icon], { className: "h-4 w-4 shrink-0" })}
                        <span className="text-sm font-medium">{item.title}</span>
                        {isActive && (
                          <span className="ml-auto flex h-4 w-4 items-center justify-center">
                            <span className="absolute h-2 w-2 rounded-full bg-current opacity-50"></span>
                          </span>
                        )}
                      </Button>
                    </Link>
                  </div>
                  {index < items.length - 1 && (
                    <Separator className="mx-2" />
                  )}
                </React.Fragment>
              )
            })}
          </div>
        </nav>

        {/* Footer - Logout */}
        <div className="border-t p-2">
          <Link href="/api/auth/logout">
            <Button variant="outline" className="w-full justify-start gap-3 rounded-md px-2" size="sm">
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
