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
import type { CapturedImage, ReviewItem, Progress, ImageAnalysisStatus } from '$lib/types';

// =============================================================================
// CONCURRENCY CONTROL
// =============================================================================

/**
 * Maximum concurrent API requests to prevent overwhelming browser/server.
 * - Browser HTTP/2 multiplexing allows many requests over fewer connections
 * - Backend rate limiter handles 400 req/min with burst capacity
 * - 30 concurrent keeps UI responsive while maximizing throughput
 */
const MAX_CONCURRENT_REQUESTS = 30;

/**
 * Process items with limited concurrency using a worker pool pattern.
 *
 * Creates N worker "threads" that pull items from a shared queue.
 * Safe in JavaScript because index increment is synchronous before each await.
 *
 * @param items - Array of items to process
 * @param processor - Async function to process each item (may throw to abort all)
 * @param concurrency - Maximum concurrent operations
 * @returns Array of results in original order
 * @throws If any processor throws (other workers will complete their current task)
 */
async function mapWithConcurrency<T, R>(
	items: T[],
	processor: (item: T, index: number) => Promise<R>,
	concurrency: number
): Promise<R[]> {
	const results: R[] = new Array(items.length);
	let nextIndex = 0;

	async function worker(): Promise<void> {
		// Each iteration: grab next index synchronously, then await processing
		// This is safe because nextIndex++ completes before any await yields
		while (nextIndex < items.length) {
			const index = nextIndex++;
			results[index] = await processor(items[index], index);
		}
	}

	// Start worker pool (capped at item count for small batches)
	const workerCount = Math.min(concurrency, items.length);
	const workers = Array.from({ length: workerCount }, () => worker());

	await Promise.all(workers);
	return results;
}

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

// =============================================================================
// ANALYSIS SERVICE CLASS
// =============================================================================

export class AnalysisService {
	/** Progress of current analysis operation */
	progress = $state<Progress | null>(null);

	/** Per-image analysis status for UI feedback */
	imageStatuses = $state<Record<number, ImageAnalysisStatus>>({});

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
			this.defaultLabelLoaded = true; // Only mark as loaded on success
		} catch {
			// Silently ignore - will retry on next analysis
		}
	}

	/**
	 * Analyze images and detect items using AI
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

		// Initialize all images as pending
		const initialStatuses: Record<number, ImageAnalysisStatus> = {};
		for (let i = 0; i < images.length; i++) {
			initialStatuses[i] = 'pending';
		}
		this.imageStatuses = initialStatuses;

		try {
			// Load default label first
			await this.loadDefaultLabel();

			// Update progress message
			this.progress = {
				current: 0,
				total: images.length,
				message: images.length === 1 ? 'Analyzing item...' : 'Analyzing items...'
			};

			const allDetectedItems: ReviewItem[] = [];
			let completedCount = 0;
			const signal = this.abortController?.signal;

			// Process images with limited concurrency to prevent overwhelming browser/server
			log.debug(`Processing ${images.length} images with max ${MAX_CONCURRENT_REQUESTS} concurrent requests`);

			const results = await mapWithConcurrency(
				images,
				async (image, index) => {
					// Check if cancelled before starting
					if (signal?.aborted) {
						throw new DOMException('Aborted', 'AbortError');
					}

					// Mark this image as analyzing
					this.imageStatuses = { ...this.imageStatuses, [index]: 'analyzing' };

					try {
						log.debug(`Starting detection for image ${index + 1}/${images.length}: file="${image.file.name}", size=${image.file.size} bytes`);
						log.debug(`Image ${index + 1} options: separateItems=${image.separateItems}, additionalImages=${image.additionalFiles?.length ?? 0}`);

						const response = await vision.detect(image.file, {
							singleItem: !image.separateItems,
							extraInstructions: image.extraInstructions || undefined,
							extractExtendedFields: true,
							additionalImages: image.additionalFiles,
							signal
						});

						log.debug(
							`Detection complete for image ${index + 1}, found ${response.items.length} item(s)`
						);

						completedCount++;
						this.progress = {
							current: completedCount,
							total: images.length,
							message: images.length === 1 ? 'Analyzing item...' : 'Analyzing items...'
						};

						// Mark this image as success
						this.imageStatuses = { ...this.imageStatuses, [index]: 'success' };

						return {
							success: true as const,
							imageIndex: index,
							image,
							items: response.items,
							compressedImages: response.compressed_images || []
						};
					} catch (error) {
						// Re-throw abort errors to be handled at the top level
						if (error instanceof Error && error.name === 'AbortError') {
							log.debug(`Analysis aborted for image ${index + 1}`);
							throw error;
						}

						completedCount++;
						this.progress = {
							current: completedCount,
							total: images.length,
							message: images.length === 1 ? 'Analyzing item...' : 'Analyzing items...'
						};

						// Mark this image as failed
						this.imageStatuses = { ...this.imageStatuses, [index]: 'failed' };

						log.error(`Failed to analyze image ${index + 1}`, error);
						return {
							success: false as const,
							imageIndex: index,
							image,
							error: error instanceof Error ? error.message : 'Unknown error'
						};
					}
				},
				MAX_CONCURRENT_REQUESTS
			);

			log.debug(`All detections complete. Processing ${results.length} result(s)...`);

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

			// Process results
			for (const result of results) {
				if (result.success) {
					// Get compressed images for this result
					const compressedImages = result.compressedImages || [];

					// First compressed image is the primary, rest are additional
					const primaryCompressed = compressedImages[0];
					const additionalCompressed = compressedImages.slice(1);

					for (const item of result.items) {
						// Add default label if configured and valid
						let labelIds = item.label_ids ?? [];
						if (validDefaultLabelId && !labelIds.includes(validDefaultLabelId)) {
							labelIds = [...labelIds, validDefaultLabelId];
						}

						// Convert compressed images to data URLs
						const compressedDataUrl = primaryCompressed
							? `data:${primaryCompressed.mime_type};base64,${primaryCompressed.data}`
							: undefined;

						const compressedAdditionalDataUrls = additionalCompressed.map(
							img => `data:${img.mime_type};base64,${img.data}`
						);

						allDetectedItems.push({
							...item,
							label_ids: labelIds,
							sourceImageIndex: result.imageIndex,
							originalFile: result.image.file,
							additionalImages: result.image.additionalFiles || [],
							compressedDataUrl,
							compressedAdditionalDataUrls: compressedAdditionalDataUrls.length > 0
								? compressedAdditionalDataUrls
								: undefined
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

	/** Cancel ongoing analysis */
	cancel(): void {
		if (this.abortController) {
			this.abortController.abort();
			this.abortController = null;
		}
	}

	/** Clear progress state */
	clearProgress(): void {
		this.progress = null;
		this.imageStatuses = {};
	}

	/**
	 * Retry analysis for failed images only
	 * @param images - All captured images
	 * @param existingItems - Items already detected successfully
	 * @returns Combined result with both existing and newly detected items
	 */
	async retryFailed(images: CapturedImage[], existingItems: ReviewItem[]): Promise<AnalysisResult> {
		const failedIndices = this.getFailedIndices();
		
		if (failedIndices.length === 0) {
			log.debug('No failed images to retry');
			return {
				success: true,
				items: existingItems,
				failedCount: 0
			};
		}

		log.info(`Retrying analysis for ${failedIndices.length} failed image(s)`);
		
		// Analyze only failed images
		const failedImages = failedIndices.map(idx => images[idx]);
		const result = await this.analyzeSubset(failedImages, failedIndices);

		// Merge with existing items
		const allItems = [...existingItems, ...result.items];
		
		return {
			success: result.success || allItems.length > 0,
			items: allItems,
			error: result.error,
			failedCount: result.failedCount
		};
	}

	/**
	 * Analyze a subset of images (used for retrying failed images)
	 * @param images - Subset of images to analyze
	 * @param originalIndices - Original indices in the full image array
	 * @returns Analysis result with items mapped to original indices
	 */
	private async analyzeSubset(images: CapturedImage[], originalIndices: number[]): Promise<AnalysisResult> {
		if (images.length === 0) {
			return { success: false, items: [], error: 'No images to analyze', failedCount: 0 };
		}

		// Prevent starting a new analysis if one is in progress
		if (this.abortController) {
			log.warn('Analysis already in progress, ignoring duplicate request');
			return { success: false, items: [], error: 'Analysis already in progress', failedCount: 0 };
		}

		log.debug(`Starting subset analysis for ${images.length} image(s)`);

		// Initialize analysis state
		this.abortController = new AbortController();
		this.progress = {
			current: 0,
			total: images.length,
			message: 'Loading preferences...'
		};

		// Reset statuses for images being retried
		const updatedStatuses = { ...this.imageStatuses };
		for (const idx of originalIndices) {
			updatedStatuses[idx] = 'pending';
		}
		this.imageStatuses = updatedStatuses;

		try {
			// Load default label first
			await this.loadDefaultLabel();

			// Update progress message
			this.progress = {
				current: 0,
				total: images.length,
				message: images.length === 1 ? 'Analyzing item...' : 'Analyzing items...'
			};

			const allDetectedItems: ReviewItem[] = [];
			let completedCount = 0;
			const signal = this.abortController?.signal;

			// Process images with limited concurrency
			log.debug(`Processing ${images.length} images with max ${MAX_CONCURRENT_REQUESTS} concurrent requests`);

			const results = await mapWithConcurrency(
				images,
				async (image, subsetIndex) => {
					const originalIndex = originalIndices[subsetIndex];
					
					// Check if cancelled before starting
					if (signal?.aborted) {
						throw new DOMException('Aborted', 'AbortError');
					}

					// Mark this image as analyzing
					this.imageStatuses = { ...this.imageStatuses, [originalIndex]: 'analyzing' };

					try {
						log.debug(`Starting detection for image ${originalIndex + 1} (retry): file="${image.file.name}", size=${image.file.size} bytes`);

						const response = await vision.detect(image.file, {
							singleItem: !image.separateItems,
							extraInstructions: image.extraInstructions || undefined,
							extractExtendedFields: true,
							additionalImages: image.additionalFiles,
							signal
						});

						log.debug(
							`Detection complete for image ${originalIndex + 1}, found ${response.items.length} item(s)`
						);

						completedCount++;
						this.progress = {
							current: completedCount,
							total: images.length,
							message: images.length === 1 ? 'Analyzing item...' : 'Analyzing items...'
						};

						// Mark this image as success
						this.imageStatuses = { ...this.imageStatuses, [originalIndex]: 'success' };

						return {
							success: true as const,
							imageIndex: originalIndex,
							image,
							items: response.items,
							compressedImages: response.compressed_images || []
						};
					} catch (error) {
						// Re-throw abort errors to be handled at the top level
						if (error instanceof Error && error.name === 'AbortError') {
							log.debug(`Analysis aborted for image ${originalIndex + 1}`);
							throw error;
						}

						completedCount++;
						this.progress = {
							current: completedCount,
							total: images.length,
							message: images.length === 1 ? 'Analyzing item...' : 'Analyzing items...'
						};

						// Mark this image as failed
						this.imageStatuses = { ...this.imageStatuses, [originalIndex]: 'failed' };

						log.error(`Failed to analyze image ${originalIndex + 1}`, error);
						return {
							success: false as const,
							imageIndex: originalIndex,
							image,
							error: error instanceof Error ? error.message : 'Unknown error'
						};
					}
				},
				MAX_CONCURRENT_REQUESTS
			);

			log.debug(`All detections complete. Processing ${results.length} result(s)...`);

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

			// Process results
			for (const result of results) {
				if (result.success) {
					// Get compressed images for this result
					const compressedImages = result.compressedImages || [];

					// First compressed image is the primary, rest are additional
					const primaryCompressed = compressedImages[0];
					const additionalCompressed = compressedImages.slice(1);

					for (const item of result.items) {
						// Add default label if configured and valid
						let labelIds = item.label_ids ?? [];
						if (validDefaultLabelId && !labelIds.includes(validDefaultLabelId)) {
							labelIds = [...labelIds, validDefaultLabelId];
						}

						// Convert compressed images to data URLs
						const compressedDataUrl = primaryCompressed
							? `data:${primaryCompressed.mime_type};base64,${primaryCompressed.data}`
							: undefined;

						const compressedAdditionalDataUrls = additionalCompressed.map(
							img => `data:${img.mime_type};base64,${img.data}`
						);

						allDetectedItems.push({
							...item,
							label_ids: labelIds,
							sourceImageIndex: result.imageIndex,
							originalFile: result.image.file,
							additionalImages: result.image.additionalFiles || [],
							compressedDataUrl,
							compressedAdditionalDataUrls: compressedAdditionalDataUrls.length > 0
								? compressedAdditionalDataUrls
								: undefined
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

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Check if analysis is in progress */
	get isAnalyzing(): boolean {
		return this.abortController !== null;
	}

	/** Get indices of images that failed analysis */
	getFailedIndices(): number[] {
		const failedIndices: number[] = [];
		for (const [indexStr, status] of Object.entries(this.imageStatuses)) {
			if (status === 'failed') {
				failedIndices.push(parseInt(indexStr, 10));
			}
		}
		return failedIndices.sort((a, b) => a - b);
	}

	/** Check if there are any failed images */
	hasFailedImages(): boolean {
		return Object.values(this.imageStatuses).some(status => status === 'failed');
	}

	/** Get count of failed images */
	get failedCount(): number {
		return Object.values(this.imageStatuses).filter(status => status === 'failed').length;
	}
}
