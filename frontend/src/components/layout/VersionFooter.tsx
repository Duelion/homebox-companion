/**
 * Version footer component
 */

import { useEffect, useState } from 'react'
import { getVersion } from '@/api/client'

export function VersionFooter() {
  const [version, setVersion] = useState<string>('0.16.0')

  useEffect(() => {
    getVersion()
      .then((data) => setVersion(data.version))
      .catch(() => {
        // Use default version
      })
  }, [])

  return (
    <footer className="fixed bottom-0 right-0 p-2 pointer-events-none">
      <span className="font-mono text-xs text-gray-600 opacity-40 hover:opacity-70 transition-opacity">
        v{version}
      </span>
    </footer>
  )
}
