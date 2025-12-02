/**
 * Summary component
 */

import { Plus, Check, CheckCircle, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'
import { Button, StepIndicator, Loader } from '@/components/ui'
import { useAppStore } from '@/store'
import { useToast } from '@/hooks/useToast'
import { createItems } from '@/api/client'
import type { ItemInput } from '@/api/types'

export function Summary() {
  const {
    confirmedItems,
    selectedLocationId,
    selectedLocationName,
    removeConfirmedItem,
    setCurrentStep,
    isLoading,
    setLoading,
    resetWizard,
  } = useAppStore()

  const toast = useToast()

  // Handle submit all items
  const handleSubmit = async () => {
    if (confirmedItems.length === 0) return

    setLoading(true, 'Creating items in Homebox...')

    try {
      // Convert review items to item inputs
      const items: ItemInput[] = confirmedItems.map((item) => ({
        name: item.name,
        quantity: item.quantity,
        description: item.description,
        label_ids: item.label_ids,
        location_id: selectedLocationId || undefined,
        manufacturer: item.manufacturer,
        model_number: item.model_number,
        serial_number: item.serial_number,
        purchase_price: item.purchase_price,
        purchase_from: item.purchase_from,
        notes: item.notes,
      }))

      const response = await createItems({
        items,
        location_id: selectedLocationId || undefined,
      })

      if (response.errors.length > 0) {
        toast.warning(`Created ${response.created.length} items, ${response.errors.length} failed`)
      } else {
        toast.success(`Created ${response.created.length} items!`)
      }

      setCurrentStep('success')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create items'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  // Handle scan more items
  const handleScanMore = () => {
    resetWizard()
  }

  if (confirmedItems.length === 0) {
    return (
      <div className="animate-fade-in text-center py-12">
        <p className="text-gray-400 mb-4">No items to submit</p>
        <Button variant="secondary" onClick={() => setCurrentStep('capture')}>
          Back to Capture
        </Button>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      <StepIndicator currentStep={4} totalSteps={4} />

      <h2 className="text-2xl font-bold gradient-text text-center mb-2">
        Review & Submit
      </h2>
      <p className="text-gray-400 text-center mb-6">
        Confirm items to add to your inventory
      </p>

      {/* Items list */}
      <div className="space-y-3 max-h-72 overflow-y-auto mb-4">
        {confirmedItems.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-3 p-4 bg-midnight-600 border border-white/5 rounded-xl"
          >
            {/* Thumbnail */}
            {item.coverImageDataUrl && (
              <div className="w-16 h-16 rounded-lg overflow-hidden bg-midnight-700 flex-shrink-0">
                <img
                  src={item.coverImageDataUrl}
                  alt={item.name}
                  className="w-full h-full object-cover"
                />
              </div>
            )}

            {/* Item info */}
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-white truncate">{item.name}</p>
              <p className="text-sm text-gray-500 truncate">
                {item.description || 'No description'}
              </p>
            </div>

            {/* Quantity badge */}
            <span className="px-3 py-1 bg-midnight-700 rounded-lg font-mono text-sm text-indigo-400">
              ×{item.quantity}
            </span>

            {/* Remove button */}
            <button
              onClick={() => removeConfirmedItem(item.id)}
              className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        ))}
      </div>

      {/* Location info */}
      <div className="flex items-center gap-4 p-4 bg-midnight-700 rounded-xl mb-6">
        <span className="text-gray-500 text-sm">Location:</span>
        <span className="font-medium text-teal-400">
          {selectedLocationName || 'Not selected'}
        </span>
      </div>

      {/* Actions */}
      <div className="space-y-3">
        <Button variant="secondary" fullWidth onClick={handleScanMore}>
          <Plus className="w-5 h-5" />
          <span>Scan More Items</span>
        </Button>

        <Button
          fullWidth
          disabled={isLoading}
          isLoading={isLoading}
          onClick={handleSubmit}
        >
          <Check className="w-5 h-5" />
          <span>Submit All Items</span>
        </Button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="mt-6 py-8">
          <Loader message="Creating items..." />
        </div>
      )}
    </div>
  )
}

export function SuccessScreen() {
  const { confirmedItems, resetWizard } = useAppStore()
  const itemCount = confirmedItems.length

  return (
    <div className="animate-fade-in text-center">
      {/* Success animation */}
      <div className="w-32 h-32 mx-auto mb-8 rounded-full bg-emerald-500/10 flex items-center justify-center animate-pulse-glow">
        <CheckCircle className="w-20 h-20 text-emerald-500" />
      </div>

      <h2 className="text-3xl font-bold gradient-text mb-2">Success!</h2>
      <p className="text-gray-400 mb-8">
        {itemCount} item{itemCount !== 1 ? 's have' : ' has'} been added to your
        inventory
      </p>

      <Button fullWidth onClick={resetWizard}>
        <RefreshCw className="w-5 h-5" />
        <span>Scan More Items</span>
      </Button>
    </div>
  )
}
