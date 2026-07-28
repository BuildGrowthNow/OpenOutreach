'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { BarChart2, Users, DollarSign, FileText, Server, ShieldCheck, LogOut } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/ui/logo'
import { useAuthStore } from '@/lib/authStoreV2'

const NAV = [
  { href: '/admin', label: 'Dashboard', icon: BarChart2, exact: true },
  { href: '/admin/users', label: 'Users', icon: Users, exact: false },
  { href: '/admin/finance', label: 'Finance', icon: DollarSign, exact: false },
  { href: '/admin/audit', label: 'Audit Log', icon: FileText, exact: false },
  { href: '/admin/platform', label: 'Platform', icon: Server, exact: false },
]

export default function AdminSidebar() {
  const pathname = usePathname()
  const { logout } = useAuthStore()

  return (
    <aside className="fixed inset-y-0 left-0 z-50 flex w-56 flex-col border-r bg-background md:relative">
      <div className="flex h-16 items-center border-b px-4">
        <Logo variant="dark" iconSize={28} className="text-sm" />
      </div>

      <div className="flex flex-col px-2 py-3">
        <div className="mb-3 flex items-center gap-1.5 px-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5" />
          Admin
        </div>
        <nav className="space-y-0.5">
          {NAV.map(({ href, label, icon: Icon, exact }) => {
            const isActive = exact ? pathname === href : pathname === href || pathname.startsWith(href + '/')
            return (
              <Button
                key={href}
                asChild
                variant="ghost"
                className={cn(
                  'w-full justify-start gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                  isActive && 'bg-accent text-accent-foreground'
                )}
              >
                <Link href={href}>
                  <Icon className="h-4 w-4 shrink-0" />
                  {label}
                </Link>
              </Button>
            )
          })}
        </nav>
      </div>

      <div className="mt-auto border-t p-2">
        <Button
          variant="ghost"
          className="w-full justify-start gap-3 rounded-lg px-3 py-2.5 text-sm font-medium"
          onClick={async () => {
            await logout()
            window.location.href = '/login'
          }}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          Logout
        </Button>
      </div>
    </aside>
  )
}
