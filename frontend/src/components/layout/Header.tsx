/**
 * App header component
 */

import { LogOut, Box } from 'lucide-react'
import { useAppStore } from '@/store'

export function Header() {
  const { isAuthenticated, logout } = useAppStore()

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between px-6 py-4 bg-midnight-900/80 backdrop-blur-xl border-b border-white/5">
      <div className="flex items-center gap-2">
        <Box className="w-8 h-8 text-indigo-500" />
        <span className="text-xl font-semibold text-white">Homebox</span>
      </div>

      {isAuthenticated && (
        <button
          onClick={logout}
          className="p-2 text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
          title="Logout"
        >
          <LogOut className="w-5 h-5" />
        </button>
      )}
    </header>
  )
}
