/**
 * Online status detection hook
 */

import { useEffect } from 'react'
import { useAppStore } from '@/store'

export function useOnlineStatus() {
  const setOnline = useAppStore((state) => state.setOnline)
  const isOnline = useAppStore((state) => state.isOnline)
  
  useEffect(() => {
    const handleOnline = () => setOnline(true)
    const handleOffline = () => setOnline(false)
    
    // Set initial state
    setOnline(navigator.onLine)
    
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [setOnline])
  
  return isOnline
}
