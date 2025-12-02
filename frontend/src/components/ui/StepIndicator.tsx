/**
 * Step indicator for wizard flow
 */

import { Check } from 'lucide-react'
import { clsx } from 'clsx'

interface StepIndicatorProps {
  currentStep: number
  totalSteps: number
}

export function StepIndicator({ currentStep, totalSteps }: StepIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-1 mb-8">
      {Array.from({ length: totalSteps }, (_, i) => {
        const step = i + 1
        const isActive = step === currentStep
        const isCompleted = step < currentStep

        return (
          <div key={step} className="flex items-center">
            {/* Step circle */}
            <div
              className={clsx(
                'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-200',
                isCompleted && 'bg-emerald-500 text-white',
                isActive && 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/40',
                !isCompleted && !isActive && 'bg-midnight-700 border-2 border-white/10 text-gray-500'
              )}
            >
              {isCompleted ? <Check className="w-4 h-4" /> : step}
            </div>

            {/* Connector line */}
            {step < totalSteps && (
              <div
                className={clsx(
                  'w-6 h-0.5 mx-1',
                  isCompleted ? 'bg-emerald-500' : 'bg-white/10'
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
