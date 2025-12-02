/**
 * Location picker component
 */

import { useEffect, useState } from 'react'
import { Home, MapPin, ChevronRight, ArrowRight, X } from 'lucide-react'
import { clsx } from 'clsx'
import { Button, StepIndicator, Loader } from '@/components/ui'
import { useAppStore } from '@/store'
import { useToast } from '@/hooks/useToast'
import { getLocationsTree, getLocation, getLabels } from '@/api/client'
import type { Location } from '@/api/types'

export function LocationPicker() {
  const {
    locationTree,
    locationPath,
    selectedLocationId,
    selectedLocationName,
    setLocationTree,
    setLocationPath,
    selectLocation,
    clearLocation,
    setLabels,
    setCurrentStep,
  } = useAppStore()

  const [displayedLocations, setDisplayedLocations] = useState<Location[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [currentParent, setCurrentParent] = useState<Location | null>(null)
  const toast = useToast()

  // Load locations on mount
  useEffect(() => {
    async function loadLocations() {
      try {
        setIsLoading(true)
        const [tree, labels] = await Promise.all([
          getLocationsTree(),
          getLabels(),
        ])
        setLocationTree(tree)
        setDisplayedLocations(tree)
        setLabels(labels)
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to load locations'
        toast.error(message)
      } finally {
        setIsLoading(false)
      }
    }
    loadLocations()
  }, [setLocationTree, setLabels, toast])

  // Navigate into a location with children
  const handleNavigateInto = async (location: Location) => {
    try {
      setIsLoading(true)
      const details = await getLocation(location.id)
      
      setLocationPath([...locationPath, { id: location.id, name: location.name }])
      setDisplayedLocations(details.children || [])
      setCurrentParent(location)
    } catch (error) {
      toast.error('Failed to load location')
    } finally {
      setIsLoading(false)
    }
  }

  // Navigate back to a previous level
  const handleNavigateBack = (index: number) => {
    if (index === -1) {
      // Go to root
      setLocationPath([])
      setDisplayedLocations(locationTree)
      setCurrentParent(null)
    } else {
      // Navigate to specific level
      const newPath = locationPath.slice(0, index + 1)
      setLocationPath(newPath)
      // Reload that level
      handleNavigateInto({ id: newPath[index].id, name: newPath[index].name })
    }
  }

  // Select a location (leaf or use current)
  const handleSelectLocation = (location: Location) => {
    selectLocation(location.id, location.name)
  }

  // Use current location (when it has children)
  const handleUseCurrentLocation = () => {
    if (currentParent) {
      selectLocation(currentParent.id, currentParent.name)
    }
  }

  // Continue to capture
  const handleContinue = () => {
    if (selectedLocationId) {
      setCurrentStep('capture')
    }
  }

  return (
    <div className="animate-fade-in">
      <StepIndicator currentStep={1} totalSteps={4} />

      <h2 className="text-2xl font-bold gradient-text text-center mb-2">
        Select Location
      </h2>
      <p className="text-gray-400 text-center mb-6">
        Navigate to choose where your items will be stored
      </p>

      {/* Breadcrumb */}
      <div className="flex items-center gap-1 flex-wrap p-3 bg-midnight-700 rounded-xl mb-4">
        <button
          onClick={() => handleNavigateBack(-1)}
          className={clsx(
            'flex items-center gap-1 px-2 py-1 rounded-lg text-sm transition-colors',
            locationPath.length === 0
              ? 'text-teal-400'
              : 'text-gray-400 hover:text-white hover:bg-midnight-600'
          )}
        >
          <Home className="w-4 h-4" />
          <span>All Locations</span>
        </button>

        {locationPath.map((item, index) => (
          <div key={item.id} className="flex items-center">
            <span className="text-gray-600 text-xs mx-1">/</span>
            <button
              onClick={() => handleNavigateBack(index)}
              className={clsx(
                'px-2 py-1 rounded-lg text-sm transition-colors',
                index === locationPath.length - 1
                  ? 'text-indigo-400 font-medium'
                  : 'text-gray-400 hover:text-white hover:bg-midnight-600'
              )}
            >
              {item.name}
            </button>
          </div>
        ))}
      </div>

      {/* Selected location display */}
      {selectedLocationId && (
        <div className="flex items-center gap-3 p-4 bg-gradient-to-r from-teal-500/15 to-indigo-500/10 border border-teal-500 rounded-xl mb-4 animate-fade-in">
          <div className="w-10 h-10 flex items-center justify-center bg-teal-500 rounded-lg text-midnight-900">
            <MapPin className="w-6 h-6" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-xs text-gray-500 uppercase tracking-wide">Selected:</span>
            <p className="font-semibold text-white truncate">{selectedLocationName}</p>
          </div>
          <button
            onClick={clearLocation}
            className="p-2 rounded-lg hover:bg-red-500 hover:text-white text-gray-400 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Location list */}
      <div className="space-y-2 max-h-80 overflow-y-auto mb-4">
        {isLoading ? (
          <div className="py-8">
            <Loader message="Loading locations..." />
          </div>
        ) : displayedLocations.length === 0 ? (
          <div className="py-8 text-center text-gray-500">
            <MapPin className="w-12 h-12 mx-auto mb-2 opacity-30" />
            <p>No child locations</p>
          </div>
        ) : (
          displayedLocations.map((location) => {
            const hasChildren = location.children && location.children.length > 0
            const isSelected = location.id === selectedLocationId

            return (
              <button
                key={location.id}
                onClick={() =>
                  hasChildren
                    ? handleNavigateInto(location)
                    : handleSelectLocation(location)
                }
                className={clsx(
                  'w-full flex items-center gap-3 p-4 rounded-xl border transition-all text-left',
                  isSelected
                    ? 'border-teal-500 bg-teal-500/10'
                    : 'border-white/5 bg-midnight-600 hover:border-indigo-500 hover:translate-x-1'
                )}
              >
                <div
                  className={clsx(
                    'w-9 h-9 flex items-center justify-center rounded-lg',
                    hasChildren
                      ? 'bg-gradient-to-br from-indigo-500/20 to-pink-500/20'
                      : 'bg-midnight-700'
                  )}
                >
                  <MapPin className="w-5 h-5 text-indigo-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="font-medium text-white block truncate">
                    {location.name}
                  </span>
                  <span className="text-xs text-gray-500">
                    {location.itemCount ?? 0} items
                    {hasChildren && ` • ${location.children?.length} sub-locations`}
                  </span>
                </div>
                {hasChildren && (
                  <ChevronRight className="w-5 h-5 text-gray-500" />
                )}
              </button>
            )
          })
        )}
      </div>

      {/* Use current location button (when navigated into a parent) */}
      {currentParent && !selectedLocationId && (
        <Button
          variant="secondary"
          fullWidth
          onClick={handleUseCurrentLocation}
          className="mb-3"
        >
          <MapPin className="w-5 h-5" />
          <span>Use This Location</span>
        </Button>
      )}

      {/* Continue button */}
      <Button
        fullWidth
        disabled={!selectedLocationId}
        onClick={handleContinue}
      >
        <span>Continue to Capture</span>
        <ArrowRight className="w-5 h-5" />
      </Button>
    </div>
  )
}
