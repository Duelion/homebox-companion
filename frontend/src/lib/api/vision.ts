/**
 * Vision AI API endpoints
 */

import { request, requestFormData } from './client';
import { getIsDemoMode, fieldPreferences } from './settings';
import { apiLogger as log } from '../utils/logger';
import type {
	DetectionResponse,
	BatchDetectionResponse,
	AdvancedItemDetails,
	MergedItemResponse,
	CorrectionResponse,
	MergeItem,
} from '../types';

export interface DetectOptions {
	singleItem?: boolean;
	extraInstructions?: string;
	extractExtendedFields?: boolean;
	additionalImages?: File[];
	signal?: AbortSignal;
}

export interface BatchDetectOptions {
	configs?: Array<{ single_item?: boolean; extra_instructions?: string }>;
	extractExtendedFields?: boolean;
	signal?: AbortSignal;
}

export interface AnalyzeOptions {
	signal?: AbortSignal;
}

export interface MergeOptions {
	signal?: AbortSignal;
}

export interface CorrectOptions {
	signal?: AbortSignal;
}

/**
 * Build headers for vision API requests.
 * In demo mode, includes field preferences for AI customization.
 */
async function buildVisionHeaders(): Promise<Record<string, string>> {
	const headers: Record<string, string> = {};

	// Add field preferences header in demo mode
	if (getIsDemoMode()) {
		try {
			const prefs = await fieldPreferences.get();
			headers['X-Field-Preferences'] = JSON.stringify(prefs);
			log.debug('Added field preferences header for demo mode');
		} catch (error) {
			// Silently ignore - preferences are optional
			log.debug('Failed to load field preferences for header:', error);
		}
	}

	return headers;
}

export const vision = {
	/**
	 * Detect items from a single image
	 */
	detect: async (image: File, options: DetectOptions = {}): Promise<DetectionResponse> => {
		log.debug(`Preparing detection request: file=${image.name}, size=${image.size} bytes`);
		log.debug(
			`Options: singleItem=${options.singleItem ?? false}, extractExtendedFields=${options.extractExtendedFields ?? true}, additionalImages=${options.additionalImages?.length ?? 0}`
		);

		const formData = new FormData();
		formData.append('image', image);

		if (options.singleItem !== undefined) {
			formData.append('single_item', String(options.singleItem));
		}
		if (options.extraInstructions) {
			formData.append('extra_instructions', options.extraInstructions);
			log.debug(
				`Extra instructions: ${options.extraInstructions.substring(0, 100)}${options.extraInstructions.length > 100 ? '...' : ''}`
			);
		}
		if (options.extractExtendedFields !== undefined) {
			formData.append('extract_extended_fields', String(options.extractExtendedFields));
		}
		if (options.additionalImages) {
			for (const img of options.additionalImages) {
				formData.append('additional_images', img);
			}
		}

		const headers = await buildVisionHeaders();
		log.info('Sending vision/detect request to backend');
		return requestFormData<DetectionResponse>('/tools/vision/detect', formData, {
			errorMessage: 'Detection failed',
			signal: options.signal,
			headers,
		});
	},

	/**
	 * Detect items from multiple images in parallel on the server.
	 * More efficient than calling detect() multiple times.
	 */
	detectBatch: async (
		images: File[],
		options: BatchDetectOptions = {}
	): Promise<BatchDetectionResponse> => {
		log.debug(`Preparing batch detection request: ${images.length} images`);
		log.debug(`Total size: ${images.reduce((sum, img) => sum + img.size, 0)} bytes`);

		const formData = new FormData();

		for (const img of images) {
			formData.append('images', img);
		}

		if (options.configs) {
			formData.append('configs', JSON.stringify(options.configs));
		}
		if (options.extractExtendedFields !== undefined) {
			formData.append('extract_extended_fields', String(options.extractExtendedFields));
		}

		const headers = await buildVisionHeaders();
		log.info(`Sending vision/detect-batch request for ${images.length} images to backend`);
		return requestFormData<BatchDetectionResponse>('/tools/vision/detect-batch', formData, {
			errorMessage: 'Batch detection failed',
			signal: options.signal,
			headers,
		});
	},

	/**
	 * Analyze multiple images to extract detailed item information
	 */
	analyze: async (
		images: File[],
		itemName: string,
		itemDescription?: string,
		options: AnalyzeOptions = {}
	): Promise<AdvancedItemDetails> => {
		log.debug(`Preparing analysis request: item="${itemName}", images=${images.length}`);

		const formData = new FormData();
		for (const img of images) {
			formData.append('images', img);
		}
		formData.append('item_name', itemName);
		if (itemDescription) {
			formData.append('item_description', itemDescription);
		}

		const headers = await buildVisionHeaders();
		log.info(`Sending vision/analyze request for "${itemName}" to backend`);
		return requestFormData<AdvancedItemDetails>('/tools/vision/analyze', formData, {
			errorMessage: 'Analysis failed',
			signal: options.signal,
			headers,
		});
	},

	/**
	 * Merge multiple items into a single consolidated item using AI
	 */
	merge: async (
		itemsToMerge: MergeItem[],
		options: MergeOptions = {}
	): Promise<MergedItemResponse> => {
		log.debug(`Preparing merge request: ${itemsToMerge.length} items`);

		const headers = await buildVisionHeaders();
		log.info(`Sending vision/merge request for ${itemsToMerge.length} items to backend`);
		return request<MergedItemResponse>('/tools/vision/merge', {
			method: 'POST',
			body: JSON.stringify({ items: itemsToMerge }),
			signal: options.signal,
			headers,
		});
	},

	/**
	 * Correct an item based on user feedback
	 */
	correct: async (
		image: File,
		currentItem: MergeItem,
		correctionInstructions: string,
		options: CorrectOptions = {}
	): Promise<CorrectionResponse> => {
		log.debug(`Preparing correction request: item="${currentItem.name}"`);
		log.debug(
			`Correction instructions: ${correctionInstructions.substring(0, 100)}${correctionInstructions.length > 100 ? '...' : ''}`
		);

		const formData = new FormData();
		formData.append('image', image);
		formData.append('current_item', JSON.stringify(currentItem));
		formData.append('correction_instructions', correctionInstructions);

		const headers = await buildVisionHeaders();
		log.info(`Sending vision/correct request for "${currentItem.name}" to backend`);
		return requestFormData<CorrectionResponse>('/tools/vision/correct', formData, {
			errorMessage: 'Correction failed',
			signal: options.signal,
			headers,
		});
	},
};
