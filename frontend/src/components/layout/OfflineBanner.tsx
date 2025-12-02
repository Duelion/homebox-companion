/**
 * Offline status banner
 */

import { WifiOff } from 'lucide-react'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'

export function OfflineBanner() {
  const isOnline = useOnlineStatus()

  if (isOnline) return null

  return (
    <div className="fixed top-16 left-0 right-0 z-40 flex items-center justify-center gap-2 py-2 px-4 bg-amber-500 text-black text-sm font-medium animate-slide-down">
      <WifiOff className="w-4 h-4" />
      <span>You're offline. Some features may not work.</span>
    </div>
  )
}
