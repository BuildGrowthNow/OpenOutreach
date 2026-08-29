'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { BarChart2, Users, DollarSign, FileText, Server, ShieldCheck, LogOut, ArrowLeft } from 'lucide-react'
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
  const router = useRouter()
  const { logout } = useAuthStore()

  return (
    <aside className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-background md:relative">
      {/* Logo */}
      <div className="flex h-16 items-center border-b px-6">
        <Logo variant="dark" iconSize={32} className="text-base" />
      </div>

      {/* Section label */}
      <div className="flex items-center gap-1.5 px-6 pt-4 pb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5" />
        Admin Panel
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        <div className="space-y-0.5 px-3">
          {NAV.map(({ href, label, icon: Icon, exact }) => {
            const isActive = exact
              ? pathname === href
              : pathname === href || pathname.startsWith(href + '/')
            return (
              <Link key={href} href={href}>
                <Button
                  variant={isActive ? 'secondary' : 'ghost'}
                  className="w-full justify-start gap-3.5 rounded-lg px-3 py-2.5 transition-all duration-200"
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="text-sm font-medium">{label}</span>
                  {isActive && (
                    <span className="ml-auto h-2 w-2 rounded-full bg-current" />
                  )}
                </Button>
              </Link>
            )
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t p-3 space-y-0.5">
        {/* Back to app - ghost with muted tint */}
        <Link href="/dashboard">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3.5 rounded-lg px-3 py-2.5 transition-all duration-200 text-muted-foreground hover:text-foreground bg-muted/40 hover:bg-muted/70"
          >
            <ArrowLeft className="h-4 w-4 shrink-0" />
            <span className="text-sm font-medium">Back to App</span>
          </Button>
        </Link>

        <Button
          variant="ghost"
          className="w-full justify-start gap-3.5 rounded-lg px-3 py-2.5 transition-all duration-200"
          onClick={async () => {
            await logout()
            router.push('/login')
          }}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          <span className="text-sm font-medium">Logout</span>
        </Button>
      </div>
    </aside>
  )
}
