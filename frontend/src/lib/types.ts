/**
 * Shared TypeScript type definitions for the Homebox Companion frontend
 */

// Location types
export interface LocationData {
	id: string;
	name: string;
	description?: string;
	itemCount?: number;
	children?: LocationData[];
}

export interface LocationTreeNode extends LocationData {
	children: LocationData[];
}

export interface LocationCreateData {
	name: string;
	description?: string;
	parent_id?: string | null;
}

export interface LocationUpdateData {
	name: string;
	description?: string;
	parent_id?: string | null;
}

// Label types
export interface LabelData {
	id: string;
	name: string;
	description?: string;
	color?: string;
}

// Item types - Core fields shared across item schemas
export interface ItemBaseFields {
	name: string;
	quantity: number;
	description?: string | null;
	label_ids?: string[] | null;
}

// Item types - Extended fields for detailed item info
export interface ItemExtendedFields {
	manufacturer?: string | null;
	model_number?: string | null;
	serial_number?: string | null;
	purchase_price?: number | null;
	purchase_from?: string | null;
	notes?: string | null;
}

// Detected item from AI vision analysis
export interface DetectedItem extends ItemBaseFields, ItemExtendedFields {}

// Item input for creating items in Homebox
export interface ItemInput extends ItemBaseFields, ItemExtendedFields {
	location_id?: string | null;
	insured?: boolean;
}

// Item for merge operations
export interface MergeItem extends ItemBaseFields, ItemExtendedFields {}

// Detection response types
export interface DetectionResponse {
	items: DetectedItem[];
	message: string;
}

export interface BatchDetectionResult {
	image_index: number;
	success: boolean;
	items: DetectedItem[];
	error?: string | null;
}

export interface BatchDetectionResponse {
	results: BatchDetectionResult[];
	total_items: number;
	successful_images: number;
	failed_images: number;
	message: string;
}

// Analysis response type
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

// Merge response type
export interface MergedItemResponse {
	name: string;
	quantity: number;
	description?: string | null;
	label_ids?: string[] | null;
}

// Correction response type
export interface CorrectionResponse {
	items: DetectedItem[];
	message: string;
}

// Batch item creation types
export interface BatchCreateRequest {
	items: ItemInput[];
	location_id?: string | null;
}

export interface BatchCreateResponse {
	created: unknown[];
	errors: string[];
	message: string;
}

