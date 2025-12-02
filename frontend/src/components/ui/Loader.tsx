/**
 * Loading spinner component
 */

import { clsx } from 'clsx'

interface LoaderProps {
  size?: 'sm' | 'md' | 'lg'
  message?: string
  className?: string
}

export function Loader({ size = 'md', message, className }: LoaderProps) {
  const sizes = {
    sm: 'w-6 h-6 border-2',
    md: 'w-10 h-10 border-3',
    lg: 'w-16 h-16 border-4',
  }

  return (
    <div className={clsx('flex flex-col items-center gap-4', className)}>
      <div
        className={clsx(
          sizes[size],
          'rounded-full border-midnight-700 border-t-indigo-500 animate-spin'
        )}
      />
      {message && <p className="text-gray-400 text-sm">{message}</p>}
    </div>
  )
}
