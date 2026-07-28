'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/lib/authStoreV2'
import AdminSidebar from '@/components/admin/admin-sidebar'

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, isInitialized } = useAuthStore()

  useEffect(() => {
    if (!isInitialized) return
    if (!user || !user.is_admin) {
      router.replace('/dashboard')
    }
  }, [user, isInitialized, router])

  if (!isInitialized || !user?.is_admin) return null

  return (
    <div className="flex h-screen overflow-hidden dark bg-background">
      <AdminSidebar />
      <main className="flex flex-1 flex-col overflow-y-auto">
        <div className="flex-1 p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
