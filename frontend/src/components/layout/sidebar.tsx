'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/ui/logo'
import { Icons } from '@/lib/types/components'
import { useAuthStore } from '@/lib/authStoreV2'

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
  const logout = useAuthStore((s) => s.logout)

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
          <Logo variant="dark" iconSize={32} className="text-base" />
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4">
          <div className="space-y-1 px-3">
            {items.map((item, index) => {
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
              return (
                <div key={item.href} className="relative group">
                  <Link href={item.href}>
                    <Button
                      variant={isActive ? 'secondary' : 'ghost'}
                      className="w-full justify-start gap-3.5 rounded-lg px-3 py-2.5 transition-all duration-200"
                      data-active={isActive}
                    >
                      {React.createElement(Icons[item.icon], { className: "h-4 w-4 shrink-0" })}
                      <span className="text-sm font-medium">{item.title}</span>
                      {isActive && (
                        <span className="ml-auto flex h-2 w-2 items-center justify-center">
                          <span className="absolute h-2 w-2 rounded-full bg-current"></span>
                        </span>
                      )}
                    </Button>
                  </Link>
                </div>
              )
            })}
          </div>
        </nav>

         {/* Footer - Logout */}
         <div className="border-t p-3">
           <Button
             variant="ghost"
             className="w-full justify-start gap-3.5 rounded-lg px-3 py-2.5 transition-all duration-200"
             onClick={logout}
           >
             {React.createElement(Icons.LogOut, { className: "h-4 w-4" })}
             <span className="text-sm font-medium">Logout</span>
           </Button>
         </div>
      </aside>
    </>
  )
}

export { Sidebar }
