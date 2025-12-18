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
import type { CapturedImage, ReviewItem, Progress } from '$lib/types';

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

			const allDetectedItems: ReviewItem[] = [];
			let completedCount = 0;
			const signal = this.abortController?.signal;

			// Process images in parallel
			const detectionPromises = images.map(async (image, index) => {
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

					log.error(`Failed to analyze image ${index + 1}`, error);
					return {
						success: false as const,
						imageIndex: index,
						image,
						error: error instanceof Error ? error.message : 'Unknown error'
					};
				}
			});

			log.debug('Waiting for all detections to complete...');
			const results = await Promise.all(detectionPromises);

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
	}

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Check if analysis is in progress */
	get isAnalyzing(): boolean {
		return this.abortController !== null;
	}
}
