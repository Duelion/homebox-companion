/**
 * API Types - TypeScript interfaces matching the backend Pydantic models
 * 
 * These types provide type safety for API requests and responses.
 * They mirror the schemas defined in server/schemas/*.py
 */

// ============================================================================
// Auth Types
// ============================================================================

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  token: string
  message: string
}

// ============================================================================
// Location Types
// ============================================================================

export interface Location {
  id: string
  name: string
  description?: string
  itemCount?: number
  children?: Location[]
}

// ============================================================================
// Label Types
// ============================================================================

export interface Label {
  id: string
  name: string
  description?: string
}

// ============================================================================
// Detection Types
// ============================================================================

export interface DetectedItem {
  name: string
  quantity: number
  description?: string | null
  label_ids?: string[] | null
  manufacturer?: string | null
  model_number?: string | null
  serial_number?: string | null
  purchase_price?: number | null
  purchase_from?: string | null
  notes?: string | null
}

export interface DetectionResponse {
  items: DetectedItem[]
  message: string
}

export interface AdvancedItemDetails {
  name?: string | null
  description?: string | null
  serial_number?: string | null
  model_number?: string | null
  manufacturer?: string | null
  purchase_price?: number | null
  notes?: string | null
  label_ids?: string[] | null
}

export interface MergeItemsRequest {
  items: Record<string, unknown>[]
}

export interface MergedItemResponse {
  name: string
  quantity: number
  description?: string | null
  label_ids?: string[] | null
}

export interface CorrectedItem {
  name: string
  quantity: number
  description?: string | null
  label_ids?: string[] | null
}

export interface CorrectionResponse {
  items: CorrectedItem[]
  message: string
}

// ============================================================================
// Item Types
// ============================================================================

export interface ItemInput {
  name: string
  quantity?: number
  description?: string | null
  location_id?: string | null
  label_ids?: string[] | null
  serial_number?: string | null
  model_number?: string | null
  manufacturer?: string | null
  purchase_price?: number | null
  purchase_from?: string | null
  notes?: string | null
  insured?: boolean
}

export interface BatchCreateRequest {
  items: ItemInput[]
  location_id?: string | null
}

export interface BatchCreateResponse {
  created: Record<string, unknown>[]
  errors: string[]
  message: string
}

// ============================================================================
// Captured Image Types (Frontend-only)
// ============================================================================

export interface CapturedImage {
  id: string
  file: File
  dataUrl: string
  singleItem: boolean
  extraInstructions: string
}

export interface ReviewItem extends DetectedItem {
  id: string
  sourceImageId: string
  coverImageDataUrl?: string
  confirmed: boolean
}

// ============================================================================
// Wizard Step Types
// ============================================================================

export type WizardStep = 
  | 'login'
  | 'location'
  | 'capture'
  | 'review'
  | 'summary'
  | 'success'

// ============================================================================
// Error Types
// ============================================================================

export interface ApiError {
  detail: string
  status?: number
}
