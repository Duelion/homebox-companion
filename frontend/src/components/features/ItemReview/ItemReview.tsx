/**
 * Item review component
 */

import { useState } from 'react'
import { ChevronLeft, ChevronRight, X, Check } from 'lucide-react'
import { clsx } from 'clsx'
import { Button, StepIndicator, Input } from '@/components/ui'
import { useAppStore } from '@/store'
import type { ReviewItem, Label } from '@/api/types'

export function ItemReview() {
  const {
    detectedItems,
    currentItemIndex,
    labels,
    setCurrentItemIndex,
    confirmCurrentItem,
    skipCurrentItem,
    updateDetectedItem,
    setCurrentStep,
  } = useAppStore()

  const currentItem = detectedItems[currentItemIndex]

  // Handle label toggle
  const handleLabelToggle = (labelId: string) => {
    if (!currentItem) return

    const currentLabels = currentItem.label_ids || []
    const newLabels = currentLabels.includes(labelId)
      ? currentLabels.filter((id) => id !== labelId)
      : [...currentLabels, labelId]

    updateDetectedItem(currentItem.id, { label_ids: newLabels })
  }

  // Handle field update
  const handleFieldUpdate = (field: keyof ReviewItem, value: string | number) => {
    if (!currentItem) return
    updateDetectedItem(currentItem.id, { [field]: value })
  }

  // Handle confirm - if last item, go to summary
  const handleConfirm = () => {
    confirmCurrentItem()
    
    // Check if there are more items
    const remainingItems = detectedItems.length - 1
    if (remainingItems <= 0) {
      setCurrentStep('summary')
    }
  }

  // Handle skip - if last item, go to summary
  const handleSkip = () => {
    skipCurrentItem()
    
    // Check if there are more items
    const remainingItems = detectedItems.length - 1
    if (remainingItems <= 0) {
      setCurrentStep('summary')
    }
  }

  // Navigate between items
  const canGoPrev = currentItemIndex > 0
  const canGoNext = currentItemIndex < detectedItems.length - 1

  if (!currentItem) {
    return (
      <div className="animate-fade-in text-center py-12">
        <p className="text-gray-400">No items to review</p>
        <Button
          variant="secondary"
          onClick={() => setCurrentStep('capture')}
          className="mt-4"
        >
          Back to Capture
        </Button>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      {/* Back button */}
      <button
        onClick={() => setCurrentStep('capture')}
        className="flex items-center gap-1 text-gray-500 hover:text-indigo-400 text-sm mb-4 transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        <span>Back to Capture</span>
      </button>

      <StepIndicator currentStep={3} totalSteps={4} />

      <h2 className="text-2xl font-bold gradient-text text-center mb-2">
        Review Items
      </h2>
      <p className="text-gray-400 text-center mb-6">
        Edit or skip detected items
      </p>

      {/* Item card */}
      <div className="bg-midnight-600 border border-white/5 rounded-2xl p-5 mb-4 animate-fade-in">
        {/* Source image thumbnail */}
        {currentItem.coverImageDataUrl && (
          <div className="flex items-center gap-3 pb-4 mb-4 border-b border-white/5">
            <div className="w-16 h-16 rounded-lg overflow-hidden border-2 border-white/10 flex-shrink-0">
              <img
                src={currentItem.coverImageDataUrl}
                alt="Source"
                className="w-full h-full object-cover"
              />
            </div>
            <div>
              <span className="text-xs text-gray-500">Source Image</span>
            </div>
          </div>
        )}

        {/* Item form */}
        <div className="space-y-4">
          <Input
            label="Name"
            value={currentItem.name}
            onChange={(e) => handleFieldUpdate('name', e.target.value)}
          />

          <div className="flex gap-3">
            <div className="w-24">
              <Input
                label="Quantity"
                type="number"
                min={1}
                value={currentItem.quantity}
                onChange={(e) => handleFieldUpdate('quantity', parseInt(e.target.value) || 1)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-gray-400">
              Description
            </label>
            <textarea
              value={currentItem.description || ''}
              onChange={(e) => handleFieldUpdate('description', e.target.value)}
              rows={2}
              className="w-full px-4 py-3 bg-midnight-700 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all resize-none"
            />
          </div>

          {/* Labels */}
          {labels.length > 0 && (
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-400">Labels</label>
              <div className="flex flex-wrap gap-2">
                {labels.map((label: Label) => {
                  const isSelected = currentItem.label_ids?.includes(label.id)
                  return (
                    <button
                      key={label.id}
                      onClick={() => handleLabelToggle(label.id)}
                      className={clsx(
                        'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                        isSelected
                          ? 'bg-teal-500/15 border border-teal-500 text-teal-400'
                          : 'bg-midnight-700 border border-midnight-700 text-gray-400 hover:border-indigo-500'
                      )}
                    >
                      {label.name}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-center gap-6 mb-6">
        <button
          disabled={!canGoPrev}
          onClick={() => setCurrentItemIndex(currentItemIndex - 1)}
          className="p-3 bg-midnight-700 border border-white/10 rounded-xl text-gray-400 hover:text-white hover:border-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>
        <span className="font-mono text-gray-400">
          {currentItemIndex + 1} / {detectedItems.length}
        </span>
        <button
          disabled={!canGoNext}
          onClick={() => setCurrentItemIndex(currentItemIndex + 1)}
          className="p-3 bg-midnight-700 border border-white/10 rounded-xl text-gray-400 hover:text-white hover:border-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="secondary" className="flex-1" onClick={handleSkip}>
          <X className="w-5 h-5" />
          <span>Skip</span>
        </Button>
        <Button className="flex-1" onClick={handleConfirm}>
          <Check className="w-5 h-5" />
          <span>Confirm</span>
        </Button>
      </div>
    </div>
  )
}
