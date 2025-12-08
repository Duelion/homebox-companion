/**
 * @deprecated This file is deprecated. Import from '$lib/api' instead.
 * 
 * This file re-exports all API functions for backward compatibility during migration.
 */

// Re-export everything from the new API module
export * from './api/index';

// Re-export types from types module for backward compatibility
// (old code imported types from api.ts)
export type {
	LocationData,
	LocationTreeNode,
	LocationCreateData,
	LocationUpdateData,
	LabelData,
	DetectedItem,
	DetectionResponse,
	ItemInput,
	BatchCreateRequest,
	BatchCreateResponse,
	MergeItem,
	MergedItemResponse,
	AdvancedItemDetails,
	CorrectionResponse,
	BatchDetectionResult,
	BatchDetectionResponse,
} from './types';
