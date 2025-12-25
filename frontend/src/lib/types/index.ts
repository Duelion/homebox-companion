/**
 * Consolidated type definitions for Homebox Companion
 * 
 * This file contains all shared types organized by domain:
 * - Domain models (Location, Label, Item)
 * - API types (requests/responses)
 * - Workflow types (scan workflow state)
 */

// =============================================================================
// DOMAIN MODELS
// =============================================================================

/** Location in Homebox hierarchy */
export interface Location {
	id: string;
	name: string;
	description?: string;
	itemCount?: number;
	children?: Location[];
}

/** Location tree node (always has children array) */
export interface LocationTreeNode extends Location {
	children: Location[];
}

/** Label for categorizing items */
export interface Label {
	id: string;
	name: string;
	description?: string;
	color?: string;
}

/** Item summary for selection/listing (lightweight) */
export interface ItemSummary {
	id: string;
	name: string;
	quantity: number;
	thumbnailId?: string | null;
}

/** Core item fields shared across all item types */
export interface ItemCore {
	name: string;
	quantity: number;
	description?: string | null;
	label_ids?: string[] | null;
}

/** Extended item fields (manufacturer, model, etc.) */
export interface ItemExtended {
	manufacturer?: string | null;
	model_number?: string | null;
	serial_number?: string | null;
	purchase_price?: number | null;
	purchase_from?: string | null;
	notes?: string | null;
}

/** Complete item with all fields */
export interface Item extends ItemCore, ItemExtended {
	id?: string;
	location_id?: string | null;
}

// =============================================================================
// WORKFLOW TYPES - Scan Flow
// =============================================================================

/** Image captured for analysis */
export interface CapturedImage {
	file: File;
	/** 
	 * URL for displaying preview thumbnail in UI.
	 * This is typically an Object URL (blob:...) for memory efficiency.
	 * Object URLs are much smaller than base64 data URLs since they
	 * reference the existing File blob instead of duplicating it.
	 * Note: This is NOT used for submission - we use compressedDataUrl or originalFile instead.
	 */
	dataUrl: string;
	/** If true, AI should detect multiple items in this image */
	separateItems: boolean;
	/** Optional instructions for AI about this image */
	extraInstructions: string;
	/** Additional images showing the same item from different angles */
	additionalFiles?: File[];
	/** Object URLs for displaying additional image previews in UI */
	additionalDataUrls?: string[];
}

/** Thumbnail editor transform state */
export interface ThumbnailTransform {
	scale: number;
	rotation: number;
	offsetX: number;
	offsetY: number;
	sourceImageIndex: number;
	dataUrl: string | null;
}

/** Item detected by AI, ready for review */
export interface ReviewItem extends ItemCore, ItemExtended {
	/** Index of the source image in capturedImages array */
	sourceImageIndex: number;
	/** Additional images for this specific item */
	additionalImages?: File[];
	/** Reference to original file for attachment upload */
	originalFile?: File;
	/** Custom cropped thumbnail data URL */
	customThumbnail?: string;
	/** Thumbnail editor transform state for restoring edits */
	thumbnailTransform?: ThumbnailTransform;
	/** Compressed image data URL for Homebox upload (replaces originalFile after analysis) */
	compressedDataUrl?: string;
	/** Compressed additional images for Homebox upload */
	compressedAdditionalDataUrls?: string[];
}

/** Item confirmed by user, ready for submission */
export interface ConfirmedItem extends ReviewItem {
	confirmed: true;
}

/** Status of the scan workflow */
export type ScanStatus =
	| 'idle'             // No active scan
	| 'location'         // Selecting location
	| 'capturing'        // Adding/configuring images
	| 'analyzing'        // AI processing (async)
	| 'partial_analysis' // Analysis complete with some failures
	| 'reviewing'        // Editing detected items
	| 'confirming'       // Summary before submit
	| 'submitting'       // Creating items in Homebox
	| 'complete';        // Success

/** Status of individual item submission */
export type ItemSubmissionStatus = 'pending' | 'creating' | 'success' | 'partial_success' | 'failed';

/** Status of individual image analysis */
export type ImageAnalysisStatus = 'pending' | 'analyzing' | 'success' | 'failed';

/** Progress for async operations */
export interface Progress {
	current: number;
	total: number;
	message?: string;
}

/** Result of the last successful submission (for success page display) */
export interface SubmissionResult {
	itemCount: number;
	photoCount: number;
	labelCount: number;
	itemNames: string[];
	locationName: string;
	locationId: string;
}

/** Complete scan workflow state */
export interface ScanState {
	status: ScanStatus;
	// Location
	locationId: string | null;
	locationName: string | null;
	locationPath: string | null;
	// Parent Item (for sub-item relationships)
	parentItemId: string | null;
	parentItemName: string | null;
	// Capture
	images: CapturedImage[];
	// Analysis
	analysisProgress: Progress | null;
	/** Per-image analysis status for UI feedback */
	imageStatuses: Record<number, ImageAnalysisStatus>;
	// Review
	detectedItems: ReviewItem[];
	currentReviewIndex: number;
	// Confirmation
	confirmedItems: ConfirmedItem[];
	// Submission
	submissionProgress: Progress | null;
	/** Per-item submission status for UI feedback */
	itemStatuses: Record<number, ItemSubmissionStatus>;
	/** Result of last successful submission (preserved for success page) */
	lastSubmissionResult: SubmissionResult | null;
	/** Error messages from the last submission attempt (for displaying specific failure reasons) */
	submissionErrors: string[];
	// Error handling
	error: string | null;
}

// =============================================================================
// API TYPES - Requests
// =============================================================================

/** Request to create a location */
export interface LocationCreateRequest {
	name: string;
	description?: string;
	parent_id?: string | null;
}

/** Request to update a location */
export interface LocationUpdateRequest {
	name: string;
	description?: string;
	parent_id?: string | null;
}

/** Request to create items in batch */
export interface BatchCreateRequest {
	items: ItemInput[];
	location_id?: string | null;
}

/** Item input for creation (with location) */
export interface ItemInput extends ItemCore, ItemExtended {
	location_id?: string | null;
	parent_id?: string | null;
	insured?: boolean;
}

/** Item for merge operations */
export interface MergeItem extends ItemCore, ItemExtended { }

// =============================================================================
// API TYPES - Responses
// =============================================================================

/** Compressed image from backend */
export interface CompressedImage {
	data: string;  // Base64-encoded image
	mime_type: string;
}

/** Response from item detection */
export interface DetectionResponse {
	items: DetectedItem[];
	message: string;
	compressed_images: CompressedImage[];
}

/** Detected item from AI (same as ItemCore + ItemExtended) */
export interface DetectedItem extends ItemCore, ItemExtended { }

/** Single image result in batch detection */
export interface BatchDetectionResult {
	image_index: number;
	success: boolean;
	items: DetectedItem[];
	error?: string | null;
}

/** Response from batch detection */
export interface BatchDetectionResponse {
	results: BatchDetectionResult[];
	total_items: number;
	successful_images: number;
	failed_images: number;
	message: string;
}

/** Response from advanced analysis */
export interface AdvancedItemDetails {
	name?: string | null;
	description?: string | null;
	serial_number?: string | null;
	model_number?: string | null;
	manufacturer?: string | null;
	purchase_price?: number | null;
	notes?: string | null;
	label_ids?: string[] | null;
}

/** Response from merge operation */
export interface MergedItemResponse {
	name: string;
	quantity: number;
	description?: string | null;
	label_ids?: string[] | null;
}

/** Response from correction operation */
export interface CorrectionResponse {
	items: DetectedItem[];
	message: string;
}

/** Item successfully created in Homebox (returned from backend) */
export interface CreatedItem {
	id: string;
	name: string;
	quantity: number;
	description?: string | null;
	/** Location object with id and name */
	location?: {
		id: string;
		name?: string;
	} | null;
	/** Labels array with id and name */
	labels?: Array<{
		id: string;
		name?: string;
	}>;
	// Extended fields (may be present after update)
	manufacturer?: string | null;
	modelNumber?: string | null;
	serialNumber?: string | null;
	purchasePrice?: number | null;
	purchaseFrom?: string | null;
	notes?: string | null;
	insured?: boolean;
}

/** Response from batch item creation */
export interface BatchCreateResponse {
	/** Successfully created items */
	created: CreatedItem[];
	/** Error messages for items that failed to create */
	errors: string[];
	/** Summary message (e.g., "Created 2 items, 1 failed") */
	message: string;
}

// =============================================================================
// BACKWARDS COMPATIBILITY
// Re-export with old names for gradual migration
// =============================================================================

/** @deprecated Use Location instead */
export type LocationData = Location;

/** @deprecated Use Label instead */
export type LabelData = Label;

/** @deprecated Use ItemCore instead */
export type ItemBaseFields = ItemCore;

/** @deprecated Use ItemExtended instead */
export type ItemExtendedFields = ItemExtended;

/** @deprecated Use LocationCreateRequest instead */
export type LocationCreateData = LocationCreateRequest;

/** @deprecated Use LocationUpdateRequest instead */
export type LocationUpdateData = LocationUpdateRequest;

