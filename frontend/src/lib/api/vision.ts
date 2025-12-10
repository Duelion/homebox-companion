/**
 * Vision AI API endpoints
 */

import { request, requestFormData } from './client';
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

export const vision = {
	/**
	 * Detect items from a single image
	 */
	detect: (image: File, options: DetectOptions = {}): Promise<DetectionResponse> => {
		const formData = new FormData();
		formData.append('image', image);

		if (options.singleItem !== undefined) {
			formData.append('single_item', String(options.singleItem));
		}
		if (options.extraInstructions) {
			formData.append('extra_instructions', options.extraInstructions);
		}
		if (options.extractExtendedFields !== undefined) {
			formData.append('extract_extended_fields', String(options.extractExtendedFields));
		}
		if (options.additionalImages) {
			for (const img of options.additionalImages) {
				formData.append('additional_images', img);
			}
		}

		return requestFormData<DetectionResponse>(
			'/tools/vision/detect',
			formData,
			{ errorMessage: 'Detection failed', signal: options.signal }
		);
	},

	/**
	 * Detect items from multiple images in parallel on the server.
	 * More efficient than calling detect() multiple times.
	 */
	detectBatch: (images: File[], options: BatchDetectOptions = {}): Promise<BatchDetectionResponse> => {
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

		return requestFormData<BatchDetectionResponse>(
			'/tools/vision/detect-batch',
			formData,
			{ errorMessage: 'Batch detection failed', signal: options.signal }
		);
	},

	/**
	 * Analyze multiple images to extract detailed item information
	 */
	analyze: (
		images: File[],
		itemName: string,
		itemDescription?: string,
		options: AnalyzeOptions = {}
	): Promise<AdvancedItemDetails> => {
		const formData = new FormData();
		for (const img of images) {
			formData.append('images', img);
		}
		formData.append('item_name', itemName);
		if (itemDescription) {
			formData.append('item_description', itemDescription);
		}

		return requestFormData<AdvancedItemDetails>(
			'/tools/vision/analyze',
			formData,
			{ errorMessage: 'Analysis failed', signal: options.signal }
		);
	},

	/**
	 * Merge multiple items into a single consolidated item using AI
	 */
	merge: (itemsToMerge: MergeItem[], options: MergeOptions = {}) =>
		request<MergedItemResponse>('/tools/vision/merge', {
			method: 'POST',
			body: JSON.stringify({ items: itemsToMerge }),
			signal: options.signal,
		}),

	/**
	 * Correct an item based on user feedback
	 */
	correct: (
		image: File,
		currentItem: MergeItem,
		correctionInstructions: string,
		options: CorrectOptions = {}
	): Promise<CorrectionResponse> => {
		const formData = new FormData();
		formData.append('image', image);
		formData.append('current_item', JSON.stringify(currentItem));
		formData.append('correction_instructions', correctionInstructions);

		return requestFormData<CorrectionResponse>(
			'/tools/vision/correct',
			formData,
			{ errorMessage: 'Correction failed', signal: options.signal }
		);
	},
};

