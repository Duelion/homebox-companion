/**
 * API Client with retry/backoff logic
 * 
 * This module provides a consistent API client with:
 * - Automatic retry with exponential backoff
 * - Bearer token handling
 * - Consistent error handling
 * - TypeScript type safety
 */

import type {
  LoginRequest,
  LoginResponse,
  Location,
  Label,
  DetectionResponse,
  BatchCreateRequest,
  BatchCreateResponse,
  MergeItemsRequest,
  MergedItemResponse,
  CorrectionResponse,
  AdvancedItemDetails,
  ApiError,
} from './types'

// ============================================================================
// Configuration
// ============================================================================

const API_BASE = '/api'
const MAX_RETRIES = 3
const INITIAL_RETRY_DELAY = 1000 // 1 second
const MAX_RETRY_DELAY = 10000 // 10 seconds
const REQUEST_TIMEOUT = 60000 // 60 seconds for AI operations

// ============================================================================
// Error Handling
// ============================================================================

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: string
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

// ============================================================================
// Utility Functions
// ============================================================================

async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function calculateBackoff(attempt: number): number {
  const delay = INITIAL_RETRY_DELAY * Math.pow(2, attempt)
  const jitter = delay * 0.1 * Math.random()
  return Math.min(delay + jitter, MAX_RETRY_DELAY)
}

// ============================================================================
// Core Request Function
// ============================================================================

interface RequestOptions extends RequestInit {
  timeout?: number
  retries?: number
  requireAuth?: boolean
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    timeout = REQUEST_TIMEOUT,
    retries = MAX_RETRIES,
    requireAuth = true,
    headers: customHeaders,
    ...fetchOptions
  } = options

  const url = `${API_BASE}${endpoint}`
  const headers: HeadersInit = {
    ...customHeaders,
  }

  // Add auth header if required
  if (requireAuth) {
    const token = sessionStorage.getItem('token')
    if (!token) {
      throw new ApiRequestError('Authentication required', 401, 'No token found')
    }
    headers['Authorization'] = `Bearer ${token}`
  }

  // Retry loop
  let lastError: Error | null = null
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      // Create abort controller for timeout
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), timeout)

      const response = await fetch(url, {
        ...fetchOptions,
        headers,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      // Handle errors
      if (!response.ok) {
        let detail = response.statusText
        try {
          const errorData = await response.json() as ApiError
          detail = errorData.detail || detail
        } catch {
          // Ignore JSON parse errors
        }

        // Don't retry on client errors (4xx) except 429 (rate limit)
        if (response.status >= 400 && response.status < 500 && response.status !== 429) {
          throw new ApiRequestError(detail, response.status, detail)
        }

        // Retry on server errors (5xx) and rate limits
        throw new ApiRequestError(detail, response.status, detail)
      }

      // Parse response
      const data = await response.json() as T
      return data

    } catch (error) {
      lastError = error as Error

      // Don't retry on abort or client errors
      if (error instanceof ApiRequestError && error.status >= 400 && error.status < 500 && error.status !== 429) {
        throw error
      }

      // Check if we should retry
      if (attempt < retries) {
        const delay = calculateBackoff(attempt)
        console.log(`Request failed, retrying in ${delay}ms (attempt ${attempt + 1}/${retries})`)
        await sleep(delay)
      }
    }
  }

  throw lastError || new Error('Request failed')
}

// ============================================================================
// Auth API
// ============================================================================

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
    requireAuth: false,
  })
}

// ============================================================================
// Location API
// ============================================================================

export async function getLocations(filterChildren?: boolean): Promise<Location[]> {
  const params = filterChildren != null ? `?filter_children=${filterChildren}` : ''
  return request<Location[]>(`/locations${params}`)
}

export async function getLocationsTree(): Promise<Location[]> {
  return request<Location[]>('/locations/tree')
}

export async function getLocation(locationId: string): Promise<Location> {
  return request<Location>(`/locations/${locationId}`)
}

// ============================================================================
// Labels API
// ============================================================================

export async function getLabels(): Promise<Label[]> {
  return request<Label[]>('/labels')
}

// ============================================================================
// Detection API
// ============================================================================

export interface DetectOptions {
  image: File
  singleItem?: boolean
  extraInstructions?: string
  extractExtendedFields?: boolean
  additionalImages?: File[]
}

export async function detectItems(options: DetectOptions): Promise<DetectionResponse> {
  const formData = new FormData()
  formData.append('image', options.image)
  formData.append('single_item', String(options.singleItem ?? false))
  formData.append('extract_extended_fields', String(options.extractExtendedFields ?? true))

  if (options.extraInstructions) {
    formData.append('extra_instructions', options.extraInstructions)
  }

  if (options.additionalImages) {
    options.additionalImages.forEach(file => {
      formData.append('additional_images', file)
    })
  }

  return request<DetectionResponse>('/detect', {
    method: 'POST',
    body: formData,
    timeout: 120000, // 2 minutes for detection
  })
}

export interface AnalyzeAdvancedOptions {
  images: File[]
  itemName: string
  itemDescription?: string
}

export async function analyzeAdvanced(options: AnalyzeAdvancedOptions): Promise<AdvancedItemDetails> {
  const formData = new FormData()
  options.images.forEach(file => {
    formData.append('images', file)
  })
  formData.append('item_name', options.itemName)
  if (options.itemDescription) {
    formData.append('item_description', options.itemDescription)
  }

  return request<AdvancedItemDetails>('/analyze-advanced', {
    method: 'POST',
    body: formData,
    timeout: 120000,
  })
}

export async function mergeItems(items: MergeItemsRequest): Promise<MergedItemResponse> {
  return request<MergedItemResponse>('/merge-items', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
    timeout: 60000,
  })
}

export interface CorrectItemOptions {
  image: File
  currentItem: Record<string, unknown>
  correctionInstructions: string
}

export async function correctItem(options: CorrectItemOptions): Promise<CorrectionResponse> {
  const formData = new FormData()
  formData.append('image', options.image)
  formData.append('current_item', JSON.stringify(options.currentItem))
  formData.append('correction_instructions', options.correctionInstructions)

  return request<CorrectionResponse>('/correct-item', {
    method: 'POST',
    body: formData,
    timeout: 60000,
  })
}

// ============================================================================
// Items API
// ============================================================================

export async function createItems(data: BatchCreateRequest): Promise<BatchCreateResponse> {
  return request<BatchCreateResponse>('/items', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function uploadItemAttachment(itemId: string, file: File): Promise<Record<string, unknown>> {
  const formData = new FormData()
  formData.append('file', file)

  return request<Record<string, unknown>>(`/items/${itemId}/attachments`, {
    method: 'POST',
    body: formData,
  })
}

// ============================================================================
// Version API
// ============================================================================

export async function getVersion(): Promise<{ version: string }> {
  return request<{ version: string }>('/version', { requireAuth: false })
}
