/**
 * Image capture component
 */

import { useRef, useCallback } from 'react'
import { Camera, Upload, Search, ChevronLeft, X, Plus } from 'lucide-react'
import { clsx } from 'clsx'
import { Button, StepIndicator, Loader } from '@/components/ui'
import { useAppStore, createImageId, createReviewItem } from '@/store'
import { useToast } from '@/hooks/useToast'
import { detectItems, type DetectOptions } from '@/api/client'

const MAX_IMAGES = 10
const MAX_FILE_SIZE_MB = 10

export function ImageCapture() {
  const {
    capturedImages,
    addCapturedImage,
    removeCapturedImage,
    clearCapturedImages,
    setDetectedItems,
    setCurrentStep,
    isLoading,
    setLoading,
  } = useAppStore()

  const toast = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)

  // Handle file selection
  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files) return

      const remainingSlots = MAX_IMAGES - capturedImages.length
      if (remainingSlots <= 0) {
        toast.warning(`Maximum ${MAX_IMAGES} images allowed`)
        return
      }

      const filesToProcess = Array.from(files).slice(0, remainingSlots)

      for (const file of filesToProcess) {
        // Validate file size
        if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
          toast.error(`File ${file.name} exceeds ${MAX_FILE_SIZE_MB}MB limit`)
          continue
        }

        // Read file as data URL
        try {
          const dataUrl = await readFileAsDataUrl(file)
          addCapturedImage({
            id: createImageId(),
            file,
            dataUrl,
            singleItem: false,
            extraInstructions: '',
          })
        } catch {
          toast.error(`Failed to read file: ${file.name}`)
        }
      }
    },
    [capturedImages.length, addCapturedImage, toast]
  )

  // Read file as data URL
  const readFileAsDataUrl = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  // Handle analyze button
  const handleAnalyze = async () => {
    if (capturedImages.length === 0) return

    setLoading(true, 'Analyzing images with AI...')

    try {
      const allItems: ReturnType<typeof createReviewItem>[] = []

      // Process each captured image
      for (let i = 0; i < capturedImages.length; i++) {
        const image = capturedImages[i]
        setLoading(true, `Processing image ${i + 1} of ${capturedImages.length}...`)

        const options: DetectOptions = {
          image: image.file,
          singleItem: image.singleItem,
          extraInstructions: image.extraInstructions || undefined,
          extractExtendedFields: true,
        }

        const response = await detectItems(options)

        // Convert detected items to review items
        for (const detected of response.items) {
          const reviewItem = createReviewItem(detected, image.id, image.dataUrl)
          allItems.push(reviewItem)
        }
      }

      if (allItems.length === 0) {
        toast.warning('No items detected in the images')
        setLoading(false)
        return
      }

      setDetectedItems(allItems)
      toast.success(`Detected ${allItems.length} items!`)
      setCurrentStep('review')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Detection failed'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade-in">
      {/* Back button */}
      <button
        onClick={() => setCurrentStep('location')}
        className="flex items-center gap-1 text-gray-500 hover:text-indigo-400 text-sm mb-4 transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        <span>Change Location</span>
      </button>

      <StepIndicator currentStep={2} totalSteps={4} />

      <h2 className="text-2xl font-bold gradient-text text-center mb-2">
        Capture Items
      </h2>
      <p className="text-gray-400 text-center mb-6">
        Add one or more photos to detect items
      </p>

      {/* Image grid */}
      {capturedImages.length > 0 ? (
        <div className="space-y-3 mb-4">
          {capturedImages.map((image, index) => (
            <div
              key={image.id}
              className="bg-midnight-600 border border-white/5 rounded-xl p-3 animate-fade-in"
            >
              <div className="flex items-center gap-3">
                <div className="relative w-16 h-16 rounded-lg overflow-hidden bg-midnight-700 border-2 border-white/10 flex-shrink-0">
                  <img
                    src={image.dataUrl}
                    alt={`Capture ${index + 1}`}
                    className="w-full h-full object-cover"
                  />
                  <span className="absolute bottom-1 left-1 bg-black/75 text-white text-xs px-1.5 py-0.5 rounded font-bold">
                    {index + 1}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">
                    {image.file.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {(image.file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <button
                  onClick={() => removeCapturedImage(image.id)}
                  className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
          ))}

          {/* Add more images */}
          {capturedImages.length < MAX_IMAGES && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full flex flex-col items-center gap-2 p-6 border-2 border-dashed border-white/10 rounded-xl text-gray-500 hover:border-indigo-500 hover:text-indigo-400 transition-colors"
            >
              <Plus className="w-8 h-8" />
              <p className="text-sm">Add more photos</p>
            </button>
          )}
        </div>
      ) : (
        /* Empty state */
        <button
          onClick={() => fileInputRef.current?.click()}
          className={clsx(
            'w-full aspect-[4/3] flex flex-col items-center justify-center gap-3',
            'bg-midnight-700 border-2 border-dashed border-white/10 rounded-2xl',
            'text-gray-500 hover:border-indigo-500 hover:bg-indigo-500/5',
            'transition-all cursor-pointer mb-4'
          )}
        >
          <Camera className="w-16 h-16 opacity-50" />
          <p>Tap to capture or upload photos</p>
          <span className="text-sm opacity-70">You can select multiple photos at once</span>
        </button>
      )}

      {/* Hidden file inputs */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {/* Action buttons */}
      <div className="flex gap-3 mb-4">
        <Button
          variant="secondary"
          className="flex-1"
          onClick={() => cameraInputRef.current?.click()}
        >
          <Camera className="w-5 h-5" />
          <span>Camera</span>
        </Button>
        <Button
          variant="secondary"
          className="flex-1"
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="w-5 h-5" />
          <span>Upload</span>
        </Button>
      </div>

      {/* Image count and clear */}
      {capturedImages.length > 0 && (
        <div className="flex items-center justify-between p-3 bg-midnight-700 rounded-xl mb-4">
          <span className="text-sm text-gray-400">
            {capturedImages.length} photo{capturedImages.length !== 1 ? 's' : ''} selected
          </span>
          <button
            onClick={clearCapturedImages}
            className="text-sm text-red-400 hover:text-red-300 underline"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Analyze button */}
      <Button
        fullWidth
        disabled={capturedImages.length === 0 || isLoading}
        isLoading={isLoading}
        onClick={handleAnalyze}
      >
        <span>Analyze with AI</span>
        <Search className="w-5 h-5" />
      </Button>

      {/* Loading state */}
      {isLoading && (
        <div className="mt-6 py-8">
          <Loader message={useAppStore.getState().loadingMessage} />
        </div>
      )}
    </div>
  )
}
