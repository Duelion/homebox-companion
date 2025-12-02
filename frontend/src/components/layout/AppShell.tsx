/**
 * App shell layout component
 */

import type { ReactNode } from 'react'
import { Header } from './Header'
import { ToastContainer } from '@/components/ui'
import { OfflineBanner } from './OfflineBanner'
import { VersionFooter } from './VersionFooter'

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen min-h-[100dvh] flex flex-col">
      <Header />
      
      <main className="flex-1 flex flex-col p-6 pb-12">
        <div className="max-w-lg mx-auto w-full">
          {children}
        </div>
      </main>

      <OfflineBanner />
      <ToastContainer />
      <VersionFooter />
    </div>
  )
}
