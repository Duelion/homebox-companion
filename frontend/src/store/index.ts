/**
 * Zustand Store for Homebox Vision
 * 
 * This store manages the entire wizard flow state including:
 * - Authentication state
 * - Location selection
 * - Image capture
 * - Item detection and review
 * - Final submission
 */

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type {
  Location,
  Label,
  CapturedImage,
  ReviewItem,
  WizardStep,
  DetectedItem,
} from '@/api/types'

// ============================================================================
// State Types
// ============================================================================

interface AuthState {
  token: string | null
  isAuthenticated: boolean
}

interface LocationState {
  locations: Location[]
  locationTree: Location[]
  locationPath: { id: string; name: string }[]
  selectedLocationId: string | null
  selectedLocationName: string | null
  labels: Label[]
}

interface CaptureState {
  capturedImages: CapturedImage[]
}

interface ReviewState {
  detectedItems: ReviewItem[]
  confirmedItems: ReviewItem[]
  currentItemIndex: number
  isMergeReview: boolean
}

interface UIState {
  currentStep: WizardStep
  isLoading: boolean
  loadingMessage: string
  isOnline: boolean
}

interface AppState extends AuthState, LocationState, CaptureState, ReviewState, UIState {
  // Auth actions
  setToken: (token: string | null) => void
  logout: () => void

  // Location actions
  setLocations: (locations: Location[]) => void
  setLocationTree: (tree: Location[]) => void
  setLocationPath: (path: { id: string; name: string }[]) => void
  selectLocation: (id: string, name: string) => void
  clearLocation: () => void
  setLabels: (labels: Label[]) => void

  // Capture actions
  addCapturedImage: (image: CapturedImage) => void
  updateCapturedImage: (id: string, updates: Partial<CapturedImage>) => void
  removeCapturedImage: (id: string) => void
  clearCapturedImages: () => void

  // Review actions
  setDetectedItems: (items: ReviewItem[]) => void
  addDetectedItems: (items: ReviewItem[]) => void
  updateDetectedItem: (id: string, updates: Partial<ReviewItem>) => void
  confirmCurrentItem: () => void
  skipCurrentItem: () => void
  setCurrentItemIndex: (index: number) => void
  addConfirmedItem: (item: ReviewItem) => void
  removeConfirmedItem: (id: string) => void
  updateConfirmedItem: (id: string, updates: Partial<ReviewItem>) => void
  setMergeReview: (isMerge: boolean) => void
  clearReviewState: () => void

  // UI actions
  setCurrentStep: (step: WizardStep) => void
  setLoading: (isLoading: boolean, message?: string) => void
  setOnline: (isOnline: boolean) => void

  // Wizard navigation
  goToNextStep: () => void
  goToPreviousStep: () => void
  resetWizard: () => void
}

// ============================================================================
// Initial State
// ============================================================================

const initialAuthState: AuthState = {
  token: null,
  isAuthenticated: false,
}

const initialLocationState: LocationState = {
  locations: [],
  locationTree: [],
  locationPath: [],
  selectedLocationId: null,
  selectedLocationName: null,
  labels: [],
}

const initialCaptureState: CaptureState = {
  capturedImages: [],
}

const initialReviewState: ReviewState = {
  detectedItems: [],
  confirmedItems: [],
  currentItemIndex: 0,
  isMergeReview: false,
}

const initialUIState: UIState = {
  currentStep: 'login',
  isLoading: false,
  loadingMessage: '',
  isOnline: true,
}

// ============================================================================
// Wizard Step Order
// ============================================================================

const STEP_ORDER: WizardStep[] = ['login', 'location', 'capture', 'review', 'summary', 'success']

// ============================================================================
// Store Creation
// ============================================================================

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        ...initialAuthState,
        ...initialLocationState,
        ...initialCaptureState,
        ...initialReviewState,
        ...initialUIState,

        // ============================================================
        // Auth Actions
        // ============================================================
        setToken: (token) => {
          if (token) {
            sessionStorage.setItem('token', token)
            set({
              token,
              isAuthenticated: true,
              currentStep: 'location',
            })
          } else {
            sessionStorage.removeItem('token')
            set({ token: null, isAuthenticated: false })
          }
        },

        logout: () => {
          sessionStorage.removeItem('token')
          set({
            ...initialAuthState,
            ...initialLocationState,
            ...initialCaptureState,
            ...initialReviewState,
            currentStep: 'login',
          })
        },

        // ============================================================
        // Location Actions
        // ============================================================
        setLocations: (locations) => set({ locations }),
        
        setLocationTree: (locationTree) => set({ locationTree }),
        
        setLocationPath: (locationPath) => set({ locationPath }),
        
        selectLocation: (id, name) => set({
          selectedLocationId: id,
          selectedLocationName: name,
        }),
        
        clearLocation: () => set({
          selectedLocationId: null,
          selectedLocationName: null,
        }),
        
        setLabels: (labels) => set({ labels }),

        // ============================================================
        // Capture Actions
        // ============================================================
        addCapturedImage: (image) => set((state) => ({
          capturedImages: [...state.capturedImages, image],
        })),

        updateCapturedImage: (id, updates) => set((state) => ({
          capturedImages: state.capturedImages.map((img) =>
            img.id === id ? { ...img, ...updates } : img
          ),
        })),

        removeCapturedImage: (id) => set((state) => ({
          capturedImages: state.capturedImages.filter((img) => img.id !== id),
        })),

        clearCapturedImages: () => set({ capturedImages: [] }),

        // ============================================================
        // Review Actions
        // ============================================================
        setDetectedItems: (items) => set({
          detectedItems: items,
          currentItemIndex: 0,
        }),

        addDetectedItems: (items) => set((state) => ({
          detectedItems: [...state.detectedItems, ...items],
        })),

        updateDetectedItem: (id, updates) => set((state) => ({
          detectedItems: state.detectedItems.map((item) =>
            item.id === id ? { ...item, ...updates } : item
          ),
        })),

        confirmCurrentItem: () => {
          const state = get()
          const currentItem = state.detectedItems[state.currentItemIndex]
          
          if (currentItem) {
            const confirmedItem = { ...currentItem, confirmed: true }
            set((state) => ({
              confirmedItems: [...state.confirmedItems, confirmedItem],
              detectedItems: state.detectedItems.filter((_, i) => i !== state.currentItemIndex),
              currentItemIndex: Math.min(
                state.currentItemIndex,
                Math.max(0, state.detectedItems.length - 2)
              ),
            }))
          }
        },

        skipCurrentItem: () => {
          const state = get()
          set({
            detectedItems: state.detectedItems.filter((_, i) => i !== state.currentItemIndex),
            currentItemIndex: Math.min(
              state.currentItemIndex,
              Math.max(0, state.detectedItems.length - 2)
            ),
          })
        },

        setCurrentItemIndex: (index) => set({ currentItemIndex: index }),

        addConfirmedItem: (item) => set((state) => ({
          confirmedItems: [...state.confirmedItems, item],
        })),

        removeConfirmedItem: (id) => set((state) => ({
          confirmedItems: state.confirmedItems.filter((item) => item.id !== id),
        })),

        updateConfirmedItem: (id, updates) => set((state) => ({
          confirmedItems: state.confirmedItems.map((item) =>
            item.id === id ? { ...item, ...updates } : item
          ),
        })),

        setMergeReview: (isMerge) => set({ isMergeReview: isMerge }),

        clearReviewState: () => set({
          detectedItems: [],
          confirmedItems: [],
          currentItemIndex: 0,
          isMergeReview: false,
        }),

        // ============================================================
        // UI Actions
        // ============================================================
        setCurrentStep: (step) => set({ currentStep: step }),

        setLoading: (isLoading, message = '') => set({
          isLoading,
          loadingMessage: message,
        }),

        setOnline: (isOnline) => set({ isOnline }),

        // ============================================================
        // Wizard Navigation
        // ============================================================
        goToNextStep: () => {
          const state = get()
          const currentIndex = STEP_ORDER.indexOf(state.currentStep)
          if (currentIndex < STEP_ORDER.length - 1) {
            set({ currentStep: STEP_ORDER[currentIndex + 1] })
          }
        },

        goToPreviousStep: () => {
          const state = get()
          const currentIndex = STEP_ORDER.indexOf(state.currentStep)
          if (currentIndex > 0) {
            set({ currentStep: STEP_ORDER[currentIndex - 1] })
          }
        },

        resetWizard: () => {
          const state = get()
          set({
            ...initialCaptureState,
            ...initialReviewState,
            currentStep: 'capture',
            // Keep auth and location state
            token: state.token,
            isAuthenticated: state.isAuthenticated,
            selectedLocationId: state.selectedLocationId,
            selectedLocationName: state.selectedLocationName,
            labels: state.labels,
          })
        },
      }),
      {
        name: 'homebox-vision-store',
        partialize: (state) => ({
          // Only persist auth-related state
          token: state.token,
          isAuthenticated: state.isAuthenticated,
        }),
      }
    ),
    { name: 'HomeboxVision' }
  )
)

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Create a ReviewItem from a DetectedItem
 */
export function createReviewItem(
  detected: DetectedItem,
  sourceImageId: string,
  coverImageDataUrl?: string
): ReviewItem {
  return {
    ...detected,
    id: `item-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    sourceImageId,
    coverImageDataUrl,
    confirmed: false,
  }
}

/**
 * Create a unique ID for captured images
 */
export function createImageId(): string {
  return `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}
