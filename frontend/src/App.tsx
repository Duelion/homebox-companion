/**
 * Homebox Vision - Main Application
 * 
 * A React-based SPA for AI-powered item detection for Homebox inventory.
 * Version: 0.16.0
 */

import { useEffect } from 'react'
import { AppShell } from '@/components/layout'
import { LoginForm } from '@/components/features/Login'
import { LocationPicker } from '@/components/features/LocationPicker'
import { ImageCapture } from '@/components/features/ImageCapture'
import { ItemReview } from '@/components/features/ItemReview'
import { Summary, SuccessScreen } from '@/components/features/Summary'
import { useAppStore } from '@/store'
import type { WizardStep } from '@/api/types'

// Map wizard steps to components
const stepComponents: Record<WizardStep, React.ComponentType> = {
  login: LoginForm,
  location: LocationPicker,
  capture: ImageCapture,
  review: ItemReview,
  summary: Summary,
  success: SuccessScreen,
}

function App() {
  const { currentStep, isAuthenticated, setToken, setCurrentStep } = useAppStore()

  // Check for existing token on mount
  useEffect(() => {
    const token = sessionStorage.getItem('token')
    if (token && !isAuthenticated) {
      setToken(token)
    }
  }, [isAuthenticated, setToken])

  // Ensure we're on the login step if not authenticated
  useEffect(() => {
    if (!isAuthenticated && currentStep !== 'login') {
      setCurrentStep('login')
    }
  }, [isAuthenticated, currentStep, setCurrentStep])

  // Get the current step component
  const CurrentStepComponent = stepComponents[currentStep]

  return (
    <AppShell>
      <CurrentStepComponent />
    </AppShell>
  )
}

export default App
