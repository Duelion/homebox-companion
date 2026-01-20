/**
 * Serialization utilities for session persistence
 *
 * Handles conversion between runtime types (with File objects and Object URLs)
 * and storable types (with base64 data URLs only).
 *
 * Why this is needed:
 * - File objects cannot be stored in IndexedDB directly
 * - Object URLs (blob:...) are session-scoped and become invalid after page reload
 * - We need base64 data URLs for persistence which survive reloads
 */

import type {
	CapturedImage,
	ReviewItem,
	ConfirmedItem,
	ScanStatus,
	ThumbnailTransform,
	ItemCore,
	ItemExtended,
	ImageAnalysisStatus,
	DuplicateMatch,
} from '$lib/types';

// =============================================================================
// STORED TYPES (Serializable - no File objects or Object URLs)
// =============================================================================

/** Serializable version of CapturedImage */
export interface StoredImage {
	id: string;
	filename: string;
	mimeType: string;
	/** base64 data URL (NOT object URL) */
	dataUrl: string;
	separateItems: boolean;
	extraInstructions: string;
	/** base64 data URLs for additional images */
	additionalDataUrls?: string[];
	additionalFilenames?: string[];
	additionalMimeTypes?: string[];
}

/** Serializable version of ReviewItem */
export interface StoredReviewItem extends ItemCore, ItemExtended {
	sourceImageIndex: number;
	/** Original image filename for reconstruction */
	originalFilename?: string;
	originalMimeType?: string;
	customThumbnail?: string;
	thumbnailTransform?: ThumbnailTransform;
	/** Already base64 from backend */
	compressedDataUrl?: string;
	compressedAdditionalDataUrls?: string[];
	/** Duplicate match info if serial matches an existing item */
	duplicate_match?: DuplicateMatch | null;
}

/** Serializable version of ConfirmedItem */
export interface StoredConfirmedItem extends StoredReviewItem {
	confirmed: true;
}

/** Complete session state for IndexedDB storage */
export interface StoredSession {
	// Metadata
	id: string;
	createdAt: number;
	updatedAt: number;
	status: ScanStatus;

	// Location context
	locationId: string | null;
	locationName: string | null;
	locationPath: string | null;
	parentItemId: string | null;
	parentItemName: string | null;

	// Images (fully serializable)
	images: StoredImage[];

	// Review state (fully serializable)
	detectedItems: StoredReviewItem[];
	confirmedItems: StoredConfirmedItem[];
	currentReviewIndex: number;

	// Analysis state (for partial_analysis recovery)
	imageStatuses?: Record<number, ImageAnalysisStatus>;
}

// =============================================================================
// FILE CONVERSION UTILITIES
// =============================================================================

/**
 * Convert a File to a base64 data URL.
 * This is the key operation for making Files serializable.
 */
export function fileToDataUrl(file: File): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => {
			if (typeof reader.result === 'string') {
				resolve(reader.result);
			} else {
				reject(new Error('FileReader did not return a string'));
			}
		};
		reader.onerror = () => reject(reader.error);
		reader.readAsDataURL(file);
	});
}

/**
 * Convert a base64 data URL back to a File object.
 * This reverses the fileToDataUrl operation.
 */
export async function dataUrlToFile(
	dataUrl: string,
	filename: string,
	mimeType?: string
): Promise<File> {
	// Extract mime type from data URL if not provided
	const mimeMatch = dataUrl.match(/^data:([^;]+);/);
	const actualMimeType = mimeType || mimeMatch?.[1] || 'image/jpeg';

	// Log warning if we had to fall back to default MIME type
	if (!mimeType && !mimeMatch?.[1]) {
		console.warn(
			'[serialize] Could not extract MIME type from data URL, falling back to image/jpeg',
			{ filename, dataUrlPrefix: dataUrl.substring(0, 50) }
		);
	}

	// Fetch the data URL to get a blob
	const response = await fetch(dataUrl);
	const blob = await response.blob();

	return new File([blob], filename, { type: actualMimeType });
}

// =============================================================================
// OBJECT URL CLEANUP
// =============================================================================

/**
 * Revoke Object URLs associated with a CapturedImage to prevent memory leaks.
 *
 * Object URLs (blob:...) are created during deserialization for efficient display.
 * They must be revoked when the image is no longer needed (e.g., workflow reset,
 * image removal, or before page unload).
 *
 * @param image - The CapturedImage whose Object URLs should be revoked
 */
export function revokeImageObjectUrls(image: CapturedImage): void {
	// Revoke main image Object URL
	// Only revoke if it's an Object URL (starts with 'blob:')
	if (image.dataUrl?.startsWith('blob:')) {
		URL.revokeObjectURL(image.dataUrl);
	}

	// Revoke additional image Object URLs
	if (image.additionalDataUrls) {
		for (const url of image.additionalDataUrls) {
			if (url?.startsWith('blob:')) {
				URL.revokeObjectURL(url);
			}
		}
	}
}

// =============================================================================
// SERIALIZATION (Runtime → Stored)
// =============================================================================

/**
 * Serialize a CapturedImage to StoredImage.
 * Converts File objects and Object URLs to base64 data URLs.
 */
export async function serializeImage(img: CapturedImage): Promise<StoredImage> {
	// Convert main file to base64
	const dataUrl = await fileToDataUrl(img.file);

	// Convert additional files to base64
	let additionalDataUrls: string[] | undefined;
	let additionalFilenames: string[] | undefined;
	let additionalMimeTypes: string[] | undefined;

	if (img.additionalFiles && img.additionalFiles.length > 0) {
		additionalDataUrls = await Promise.all(img.additionalFiles.map(fileToDataUrl));
		additionalFilenames = img.additionalFiles.map((f) => f.name);
		additionalMimeTypes = img.additionalFiles.map((f) => f.type || 'image/jpeg');
	}

	return {
		id: crypto.randomUUID(),
		filename: img.file.name,
		mimeType: img.file.type || 'image/jpeg',
		dataUrl,
		separateItems: img.separateItems,
		extraInstructions: img.extraInstructions,
		additionalDataUrls,
		additionalFilenames,
		additionalMimeTypes,
	};
}

/**
 * Serialize a ReviewItem to StoredReviewItem.
 * Strips out File objects (we rely on compressedDataUrl instead).
 */
export function serializeReviewItem(item: ReviewItem): StoredReviewItem {
	return {
		// ItemCore fields
		name: item.name,
		quantity: item.quantity,
		description: item.description,
		label_ids: item.label_ids,
		// ItemExtended fields
		manufacturer: item.manufacturer,
		model_number: item.model_number,
		serial_number: item.serial_number,
		purchase_price: item.purchase_price,
		purchase_from: item.purchase_from,
		notes: item.notes,
		// ReviewItem-specific fields
		sourceImageIndex: item.sourceImageIndex,
		originalFilename: item.originalFile?.name,
		originalMimeType: item.originalFile?.type,
		customThumbnail: item.customThumbnail,
		thumbnailTransform: item.thumbnailTransform,
		compressedDataUrl: item.compressedDataUrl,
		compressedAdditionalDataUrls: item.compressedAdditionalDataUrls,
		duplicate_match: item.duplicate_match,
	};
}

/**
 * Serialize a ConfirmedItem to StoredConfirmedItem.
 */
export function serializeConfirmedItem(item: ConfirmedItem): StoredConfirmedItem {
	return {
		...serializeReviewItem(item),
		confirmed: true,
	};
}

// =============================================================================
// DESERIALIZATION (Stored → Runtime)
// =============================================================================

/**
 * Deserialize a StoredImage back to CapturedImage.
 * Converts base64 data URLs back to File objects and creates fresh Object URLs.
 */
export async function deserializeImage(stored: StoredImage): Promise<CapturedImage> {
	// Convert base64 back to File
	const file = await dataUrlToFile(stored.dataUrl, stored.filename, stored.mimeType);

	// Convert additional images
	let additionalFiles: File[] | undefined;
	let additionalDataUrls: string[] | undefined;

	if (stored.additionalDataUrls && stored.additionalDataUrls.length > 0) {
		additionalFiles = await Promise.all(
			stored.additionalDataUrls.map((url, i) => {
				const filename = stored.additionalFilenames?.[i] || `additional_${i}.jpg`;
				const mimeType = stored.additionalMimeTypes?.[i]; // Let dataUrlToFile extract from URL if missing
				return dataUrlToFile(url, filename, mimeType);
			})
		);
		// Create fresh Object URLs for display
		additionalDataUrls = additionalFiles.map((f) => URL.createObjectURL(f));
	}

	return {
		file,
		// Create fresh Object URL for display (NOT the base64 - Object URLs are more memory efficient for display)
		dataUrl: URL.createObjectURL(file),
		separateItems: stored.separateItems,
		extraInstructions: stored.extraInstructions,
		additionalFiles,
		additionalDataUrls,
	};
}

/**
 * Deserialize a StoredReviewItem back to ReviewItem.
 * Reconstructs File objects from compressedDataUrl if available.
 */
export async function deserializeReviewItem(stored: StoredReviewItem): Promise<ReviewItem> {
	// Reconstruct originalFile from compressedDataUrl if we have it
	let originalFile: File | undefined;
	if (stored.compressedDataUrl && stored.originalFilename) {
		originalFile = await dataUrlToFile(
			stored.compressedDataUrl,
			stored.originalFilename,
			stored.originalMimeType
		);
	} else if (stored.compressedDataUrl && !stored.originalFilename) {
		// Log warning when we have image data but no filename to reconstruct with
		console.warn(
			'[serialize] Cannot reconstruct originalFile: compressedDataUrl exists but originalFilename is missing',
			{ name: stored.name }
		);
	}

	// Reconstruct additionalImages from compressedAdditionalDataUrls
	let additionalImages: File[] | undefined;
	if (stored.compressedAdditionalDataUrls && stored.compressedAdditionalDataUrls.length > 0) {
		additionalImages = await Promise.all(
			stored.compressedAdditionalDataUrls.map((url, i) =>
				dataUrlToFile(url, `additional_${i}.jpg`, 'image/jpeg')
			)
		);
	}

	return {
		// ItemCore fields
		name: stored.name,
		quantity: stored.quantity,
		description: stored.description,
		label_ids: stored.label_ids,
		// ItemExtended fields
		manufacturer: stored.manufacturer,
		model_number: stored.model_number,
		serial_number: stored.serial_number,
		purchase_price: stored.purchase_price,
		purchase_from: stored.purchase_from,
		notes: stored.notes,
		// ReviewItem-specific fields
		sourceImageIndex: stored.sourceImageIndex,
		originalFile,
		additionalImages,
		customThumbnail: stored.customThumbnail,
		thumbnailTransform: stored.thumbnailTransform,
		compressedDataUrl: stored.compressedDataUrl,
		compressedAdditionalDataUrls: stored.compressedAdditionalDataUrls,
		duplicate_match: stored.duplicate_match,
	};
}

/**
 * Deserialize a StoredConfirmedItem back to ConfirmedItem.
 */
export async function deserializeConfirmedItem(
	stored: StoredConfirmedItem
): Promise<ConfirmedItem> {
	const reviewItem = await deserializeReviewItem(stored);
	return {
		...reviewItem,
		confirmed: true,
	};
}
