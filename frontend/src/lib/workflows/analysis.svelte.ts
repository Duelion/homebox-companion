/**
 * AnalysisService - Handles AI detection and analysis operations
 *
 * Responsibilities:
 * - Running AI detection on images
 * - Managing analysis progress
 * - Cancellation support
 * - Default label loading
 */

import { vision, fieldPreferences } from '$lib/api/index';
import { labels as labelsStore } from '$lib/stores/labels';
import { workflowLogger as log } from '$lib/utils/logger';
import { get } from 'svelte/store';
import type { CapturedImage, ReviewItem, Progress, DetectedItem } from '$lib/types';

// =============================================================================
// TYPES
// =============================================================================

export interface AnalysisResult {
	success: boolean;
	items: ReviewItem[];
	error?: string;
	/** Number of images that failed to process */
	failedCount: number;
}

/** Internal type for tracking image detection results */
interface ImageDetectionResult {
	success: boolean;
	imageIndex: number;
	image: CapturedImage;
	items: DetectedItem[];
	error?: string;
}

// =============================================================================
// ANALYSIS SERVICE CLASS
// =============================================================================

export class AnalysisService {
	/** Progress of current analysis operation */
	progress = $state<Progress | null>(null);

	/** Abort controller for cancellable operations */
	private abortController: AbortController | null = null;

	/** Cache for default label (loaded once per session) */
	private defaultLabelId: string | null = null;
	private defaultLabelLoaded = false;

	// =========================================================================
	// ANALYSIS OPERATIONS
	// =========================================================================

	/** Load default label ID if not already loaded */
	async loadDefaultLabel(): Promise<void> {
		if (this.defaultLabelLoaded) return;
		try {
			const prefs = await fieldPreferences.get();
			this.defaultLabelId = prefs.default_label_id;
		} catch {
			// Silently ignore - default label is optional
		}
		this.defaultLabelLoaded = true;
	}

	/**
	 * Analyze images and detect items using AI
	 * Uses batch detection endpoint for efficiency, with fallback for images
	 * that have additional files (which require single-image detection).
	 * @param images - Array of captured images to analyze
	 * @returns Analysis result with detected items
	 */
	async analyze(images: CapturedImage[]): Promise<AnalysisResult> {
		if (images.length === 0) {
			return { success: false, items: [], error: 'No images to analyze', failedCount: 0 };
		}

		// Prevent starting a new analysis if one is in progress
		if (this.abortController) {
			log.warn('Analysis already in progress, ignoring duplicate request');
			return { success: false, items: [], error: 'Analysis already in progress', failedCount: 0 };
		}

		log.debug(`Starting analysis for ${images.length} image(s)`);

		// Initialize analysis state
		this.abortController = new AbortController();
		this.progress = {
			current: 0,
			total: images.length,
			message: 'Loading preferences...'
		};

		try {
			// Load default label first
			await this.loadDefaultLabel();

			// Update progress message
			this.progress = {
				current: 0,
				total: images.length,
				message: images.length === 1 ? 'Analyzing item...' : 'Analyzing items...'
			};

			const signal = this.abortController?.signal;
			const results = await this.runDetection(images, signal);

			// Check if cancelled
			if (this.abortController?.signal.aborted) {
				log.debug('Analysis was cancelled, exiting');
				return { success: false, items: [], error: 'Analysis cancelled', failedCount: 0 };
			}

			// Validate default label exists in current Homebox instance
			const currentLabels = get(labelsStore);
			const validDefaultLabelId =
				this.defaultLabelId && currentLabels.some((l) => l.id === this.defaultLabelId)
					? this.defaultLabelId
					: null;

			// Process results into ReviewItems
			const allDetectedItems: ReviewItem[] = [];
			for (const result of results) {
				if (result.success) {
					for (const item of result.items) {
						// Add default label if configured and valid
						let labelIds = item.label_ids ?? [];
						if (validDefaultLabelId && !labelIds.includes(validDefaultLabelId)) {
							labelIds = [...labelIds, validDefaultLabelId];
						}

						allDetectedItems.push({
							...item,
							label_ids: labelIds,
							sourceImageIndex: result.imageIndex,
							originalFile: result.image.file,
							additionalImages: result.image.additionalFiles || []
						});
					}
				}
			}

			// Handle results
			const failedCount = results.filter((r) => !r.success).length;

			if (failedCount === results.length) {
				return {
					success: false,
					items: [],
					error: 'All images failed to analyze. Please try again.',
					failedCount
				};
			}

			if (allDetectedItems.length === 0) {
				return {
					success: false,
					items: [],
					error: 'No items detected in the images',
					failedCount
				};
			}

			// Success
			log.debug(`Analysis complete! Detected ${allDetectedItems.length} item(s)`);
			return {
				success: true,
				items: allDetectedItems,
				failedCount
			};
		} catch (error) {
			// Don't set error if cancelled
			if (
				this.abortController?.signal.aborted ||
				(error instanceof Error && error.name === 'AbortError')
			) {
				log.debug('Analysis cancelled by user');
				return { success: false, items: [], error: 'Analysis cancelled', failedCount: 0 };
			}

			log.error('Analysis failed', error);
			return {
				success: false,
				items: [],
				error: error instanceof Error ? error.message : 'Analysis failed',
				failedCount: 0
			};
		} finally {
			this.abortController = null;
		}
	}

	/**
	 * Run detection on images, using batch endpoint when possible.
	 * Images with additionalFiles must use single detection (batch doesn't support it).
	 */
	private async runDetection(
		images: CapturedImage[],
		signal?: AbortSignal
	): Promise<ImageDetectionResult[]> {
		// Partition images: those that can use batch vs those that need single detection
		const simpleImages: Array<{ index: number; image: CapturedImage }> = [];
		const complexImages: Array<{ index: number; image: CapturedImage }> = [];

		for (let i = 0; i < images.length; i++) {
			const image = images[i];
			if (image.additionalFiles && image.additionalFiles.length > 0) {
				complexImages.push({ index: i, image });
			} else {
				simpleImages.push({ index: i, image });
			}
		}

		log.debug(
			`Detection split: ${simpleImages.length} batch-eligible, ${complexImages.length} need single detection`
		);

		const results: ImageDetectionResult[] = [];
		let completedCount = 0;

		const updateProgress = () => {
			completedCount++;
			this.progress = {
				current: completedCount,
				total: images.length,
				message: images.length === 1 ? 'Analyzing item...' : 'Analyzing items...'
			};
		};

		// Process batch-eligible images using batch endpoint
		if (simpleImages.length > 0) {
			const batchResults = await this.runBatchDetection(simpleImages, signal, updateProgress);
			results.push(...batchResults);
		}

		// Process complex images (with additionalFiles) using single detection
		if (complexImages.length > 0) {
			const singleResults = await this.runSingleDetections(complexImages, signal, updateProgress);
			results.push(...singleResults);
		}

		// Sort by original image index to maintain order
		results.sort((a, b) => a.imageIndex - b.imageIndex);

		return results;
	}

	/**
	 * Run batch detection for multiple images in a single API call.
	 */
	private async runBatchDetection(
		items: Array<{ index: number; image: CapturedImage }>,
		signal?: AbortSignal,
		onComplete?: () => void
	): Promise<ImageDetectionResult[]> {
		const files = items.map((item) => item.image.file);
		const configs = items.map((item) => ({
			single_item: !item.image.separateItems,
			extra_instructions: item.image.extraInstructions || undefined
		}));

		log.debug(`Running batch detection for ${files.length} images`);

		try {
			const response = await vision.detectBatch(files, {
				configs,
				extractExtendedFields: true,
				signal
			});

			log.debug(
				`Batch detection complete: ${response.successful_images}/${response.results.length} successful, ${response.total_items} items`
			);

			// Map batch results back to original indices
			return response.results.map((result, i) => {
				// Call progress update for each image processed
				onComplete?.();

				const originalItem = items[i];
				if (result.success) {
					return {
						success: true,
						imageIndex: originalItem.index,
						image: originalItem.image,
						items: result.items
					};
				} else {
					log.error(`Batch detection failed for image ${originalItem.index + 1}: ${result.error}`);
					return {
						success: false,
						imageIndex: originalItem.index,
						image: originalItem.image,
						items: [],
						error: result.error || 'Detection failed'
					};
				}
			});
		} catch (error) {
			// Re-throw abort errors
			if (error instanceof Error && error.name === 'AbortError') {
				throw error;
			}

			log.error('Batch detection failed', error);
			// Return failures for all images in the batch
			return items.map((item) => {
				onComplete?.();
				return {
					success: false,
					imageIndex: item.index,
					image: item.image,
					items: [],
					error: error instanceof Error ? error.message : 'Batch detection failed'
				};
			});
		}
	}

	/**
	 * Run single detection for images that have additionalFiles.
	 * These cannot use batch detection as the batch endpoint doesn't support additional images.
	 */
	private async runSingleDetections(
		items: Array<{ index: number; image: CapturedImage }>,
		signal?: AbortSignal,
		onComplete?: () => void
	): Promise<ImageDetectionResult[]> {
		log.debug(`Running single detection for ${items.length} images with additional files`);

		const detectionPromises = items.map(async ({ index, image }) => {
			try {
				log.debug(`Starting single detection for image ${index + 1} (has additional files)`);
				const response = await vision.detect(image.file, {
					singleItem: !image.separateItems,
					extraInstructions: image.extraInstructions || undefined,
					extractExtendedFields: true,
					additionalImages: image.additionalFiles,
					signal
				});

				log.debug(`Single detection complete for image ${index + 1}, found ${response.items.length} item(s)`);
				onComplete?.();

				return {
					success: true,
					imageIndex: index,
					image,
					items: response.items
				};
			} catch (error) {
				// Re-throw abort errors
				if (error instanceof Error && error.name === 'AbortError') {
					throw error;
				}

				onComplete?.();
				log.error(`Failed to analyze image ${index + 1}`, error);
				return {
					success: false,
					imageIndex: index,
					image,
					items: [],
					error: error instanceof Error ? error.message : 'Unknown error'
				};
			}
		});

		return Promise.all(detectionPromises);
	}

	/** Cancel ongoing analysis */
	cancel(): void {
		if (this.abortController) {
			this.abortController.abort();
		}
	}

	/** Clear progress state */
	clearProgress(): void {
		this.progress = null;
	}

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Check if analysis is in progress */
	get isAnalyzing(): boolean {
		return this.abortController !== null;
	}
}
