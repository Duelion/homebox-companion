/**
 * ScanWorkflow - Manages the entire scan-to-submit workflow
 * 
 * This class owns:
 * - All state for the scan workflow
 * - All async operations (analysis, submission)
 * - Cancellation logic
 * 
 * Pages become thin views that read state and call actions.
 */

import { vision, items as itemsApi, fieldPreferences } from '$lib/api/index';
import { labels as labelsStore } from '$lib/stores/labels';
import { withRetry } from '$lib/utils/retry';
import { get } from 'svelte/store';
import type {
	ScanState,
	ScanStatus,
	CapturedImage,
	ReviewItem,
	ConfirmedItem,
	DetectedItem,
	Progress,
	ItemInput,
} from '$lib/types';

// =============================================================================
// INITIAL STATE
// =============================================================================

const initialState: ScanState = {
	status: 'idle',
	locationId: null,
	locationName: null,
	locationPath: null,
	images: [],
	analysisProgress: null,
	detectedItems: [],
	currentReviewIndex: 0,
	confirmedItems: [],
	submissionProgress: null,
	error: null,
};

// =============================================================================
// SCAN WORKFLOW CLASS
// =============================================================================

class ScanWorkflow {
	// Reactive state using Svelte 5 runes
	state = $state<ScanState>({ ...initialState });

	// Private: abort controller for cancellable operations
	private analysisAbortController: AbortController | null = null;
	private submissionAbortController: AbortController | null = null;

	// Cache for default label (loaded once per session)
	private defaultLabelId: string | null = null;
	private defaultLabelLoaded = false;

	// =========================================================================
	// LOCATION ACTIONS
	// =========================================================================

	/** Set the selected location */
	setLocation(id: string, name: string, path: string): void {
		this.state.locationId = id;
		this.state.locationName = name;
		this.state.locationPath = path;
		this.state.status = 'capturing';
		this.state.error = null;
	}

	/** Clear location selection */
	clearLocation(): void {
		this.state.locationId = null;
		this.state.locationName = null;
		this.state.locationPath = null;
		this.state.status = 'location';
	}

	// =========================================================================
	// IMAGE CAPTURE ACTIONS
	// =========================================================================

	/** Add a captured image */
	addImage(image: CapturedImage): void {
		this.state.images = [...this.state.images, image];
	}

	/** Remove an image by index */
	removeImage(index: number): void {
		this.state.images = this.state.images.filter((_, i) => i !== index);
	}

	/** Update image options (separateItems, extraInstructions) */
	updateImageOptions(
		index: number,
		options: Partial<Pick<CapturedImage, 'separateItems' | 'extraInstructions'>>
	): void {
		this.state.images = this.state.images.map((img, i) =>
			i === index ? { ...img, ...options } : img
		);
	}

	/** Add additional images to a captured image */
	addAdditionalImages(imageIndex: number, files: File[], dataUrls: string[]): void {
		this.state.images = this.state.images.map((img, i) => {
			if (i !== imageIndex) return img;
			return {
				...img,
				additionalFiles: [...(img.additionalFiles || []), ...files],
				additionalDataUrls: [...(img.additionalDataUrls || []), ...dataUrls],
			};
		});
	}

	/** Remove an additional image */
	removeAdditionalImage(imageIndex: number, additionalIndex: number): void {
		this.state.images = this.state.images.map((img, i) => {
			if (i !== imageIndex) return img;
			return {
				...img,
				additionalFiles: img.additionalFiles?.filter((_, j) => j !== additionalIndex),
				additionalDataUrls: img.additionalDataUrls?.filter((_, j) => j !== additionalIndex),
			};
		});
	}

	/** Clear all captured images */
	clearImages(): void {
		this.state.images = [];
	}

	// =========================================================================
	// ANALYSIS (ASYNC)
	// =========================================================================

	/** Load default label ID if not already loaded */
	private async loadDefaultLabel(): Promise<void> {
		if (this.defaultLabelLoaded) return;
		try {
			const prefs = await fieldPreferences.get();
			this.defaultLabelId = prefs.default_label_id;
		} catch {
			// Silently ignore - default label is optional
		}
		this.defaultLabelLoaded = true;
	}

	/** Start image analysis - THIS IS THE KEY ASYNC OPERATION */
	async startAnalysis(): Promise<void> {
		// Prevent starting a new analysis if one is already in progress
		// CRITICAL: Set status IMMEDIATELY to prevent race conditions
		if (this.state.status === 'analyzing') {
			console.warn('Analysis already in progress, ignoring duplicate request');
			return;
		}

		if (this.state.images.length === 0) {
			this.state.error = 'Please add at least one image';
			return;
		}

		// Set status BEFORE any async operations to prevent duplicate triggers
		this.analysisAbortController = new AbortController();
		this.state.status = 'analyzing';
		this.state.error = null;
		this.state.analysisProgress = {
			current: 0,
			total: this.state.images.length,
			message: 'Loading preferences...',
		};

		// Load default label (now happens AFTER status is set)
		await this.loadDefaultLabel();

		// Update progress message
		this.state.analysisProgress = {
			current: 0,
			total: this.state.images.length,
			message: 'Starting analysis...',
		};

		try {
			const allDetectedItems: ReviewItem[] = [];
			let completedCount = 0;

			// Process images in parallel
			const detectionPromises = this.state.images.map(async (image, index) => {
				try {
					const response = await vision.detect(image.file, {
						singleItem: !image.separateItems,
						extraInstructions: image.extraInstructions || undefined,
						extractExtendedFields: true,
						additionalImages: image.additionalFiles,
					});

					completedCount++;
					this.state.analysisProgress = {
						current: completedCount,
						total: this.state.images.length,
						message: `Analyzed ${completedCount} of ${this.state.images.length}...`,
					};

					return {
						success: true as const,
						imageIndex: index,
						image,
						items: response.items,
					};
				} catch (error) {
					completedCount++;
					this.state.analysisProgress = {
						current: completedCount,
						total: this.state.images.length,
						message: `Analyzed ${completedCount} of ${this.state.images.length}...`,
					};

					console.error(`Failed to analyze image ${index + 1}:`, error);
					return {
						success: false as const,
						imageIndex: index,
						image,
						error: error instanceof Error ? error.message : 'Unknown error',
					};
				}
			});

			const results = await Promise.all(detectionPromises);

			// Check if cancelled
			if (this.analysisAbortController?.signal.aborted) {
				return;
			}

			// Process results
			// Validate default label exists in current Homebox instance
			const currentLabels = get(labelsStore);
			const validDefaultLabelId = this.defaultLabelId && 
				currentLabels.some(l => l.id === this.defaultLabelId) 
				? this.defaultLabelId 
				: null;

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
							additionalImages: result.image.additionalFiles || [],
						});
					}
				}
			}

			// Handle results
			const failedCount = results.filter((r) => !r.success).length;
			if (failedCount === results.length) {
				this.state.error = 'All images failed to analyze. Please try again.';
				this.state.status = 'capturing';
				return;
			}

			if (allDetectedItems.length === 0) {
				this.state.error = 'No items detected in the images';
				this.state.status = 'capturing';
				return;
			}

		// Success! Move to review
		this.state.detectedItems = allDetectedItems;
		this.state.currentReviewIndex = 0;
		// Keep analysisProgress for success animation - will be cleared by UI after animation
		this.state.status = 'reviewing';
		} catch (error) {
			// Don't set error if cancelled
			if (this.analysisAbortController?.signal.aborted) {
				return;
			}

			console.error('Analysis failed:', error);
			this.state.error = error instanceof Error ? error.message : 'Analysis failed';
			this.state.status = 'capturing';
		} finally {
			this.analysisAbortController = null;
		}
	}

	/** Cancel ongoing analysis */
	cancelAnalysis(): void {
		if (this.analysisAbortController) {
			this.analysisAbortController.abort();
			// Don't null the controller here - let the finally block do it
			// This ensures the abort signal check in startAnalysis() still works
		}
		if (this.state.status === 'analyzing') {
			this.state.status = 'capturing';
			this.state.analysisProgress = null;
		}
	}

	/** Check if analysis is in progress */
	get isAnalyzing(): boolean {
		return this.state.status === 'analyzing';
	}

	// =========================================================================
	// REVIEW ACTIONS
	// =========================================================================

	/** Get current item being reviewed */
	get currentItem(): ReviewItem | null {
		return this.state.detectedItems[this.state.currentReviewIndex] ?? null;
	}

	/** Update the current item being reviewed */
	updateCurrentItem(updates: Partial<ReviewItem>): void {
		const index = this.state.currentReviewIndex;
		if (index < 0 || index >= this.state.detectedItems.length) return;

		this.state.detectedItems = this.state.detectedItems.map((item, i) =>
			i === index ? { ...item, ...updates } : item
		);
	}

	/** Navigate to previous item */
	previousItem(): void {
		if (this.state.currentReviewIndex > 0) {
			this.state.currentReviewIndex--;
		}
	}

	/** Navigate to next item */
	nextItem(): void {
		if (this.state.currentReviewIndex < this.state.detectedItems.length - 1) {
			this.state.currentReviewIndex++;
		}
	}

	/** Skip current item and move to next */
	skipItem(): void {
		if (this.state.currentReviewIndex < this.state.detectedItems.length - 1) {
			this.nextItem();
		} else {
			// Last item - if nothing confirmed, go back to capture
			if (this.state.confirmedItems.length === 0) {
				this.backToCapture();
			} else {
				this.finishReview();
			}
		}
	}

	/** Confirm current item and move to next */
	confirmItem(item: ReviewItem): void {
		const confirmed: ConfirmedItem = { ...item, confirmed: true };
		this.state.confirmedItems = [...this.state.confirmedItems, confirmed];

		if (this.state.currentReviewIndex < this.state.detectedItems.length - 1) {
			this.nextItem();
		} else {
			this.finishReview();
		}
	}

	/** Finish review and move to confirmation */
	finishReview(): void {
		if (this.state.confirmedItems.length === 0) {
			this.state.error = 'Please confirm at least one item';
			return;
		}
		this.state.status = 'confirming';
	}

	/** Return to capture mode from review */
	backToCapture(): void {
		this.state.status = 'capturing';
		this.state.detectedItems = [];
		this.state.currentReviewIndex = 0;
		this.state.confirmedItems = [];
		this.state.error = null;
	}

	// =========================================================================
	// CONFIRMATION ACTIONS
	// =========================================================================

	/** Remove a confirmed item */
	removeConfirmedItem(index: number): void {
		this.state.confirmedItems = this.state.confirmedItems.filter((_, i) => i !== index);
		if (this.state.confirmedItems.length === 0) {
			this.state.status = 'capturing';
		}
	}

	/** Edit a confirmed item (move back to review) */
	editConfirmedItem(index: number): void {
		const item = this.state.confirmedItems[index];
		if (!item) return;

		// Remove from confirmed
		this.state.confirmedItems = this.state.confirmedItems.filter((_, i) => i !== index);

		// Add to detected items for re-review
		const reviewItem: ReviewItem = {
			name: item.name,
			quantity: item.quantity,
			description: item.description,
			label_ids: item.label_ids,
			manufacturer: item.manufacturer,
			model_number: item.model_number,
			serial_number: item.serial_number,
			purchase_price: item.purchase_price,
			purchase_from: item.purchase_from,
			notes: item.notes,
			sourceImageIndex: item.sourceImageIndex,
			additionalImages: item.additionalImages,
			originalFile: item.originalFile,
			customThumbnail: item.customThumbnail,
		};

		this.state.detectedItems = [reviewItem];
		this.state.currentReviewIndex = 0;
		this.state.status = 'reviewing';
	}

	/** Go back to add more images */
	addMoreImages(): void {
		this.state.status = 'capturing';
	}

	// =========================================================================
	// SUBMISSION (ASYNC)
	// =========================================================================

	/** Submit all confirmed items to Homebox */
	async submitAll(): Promise<void> {
		if (this.state.confirmedItems.length === 0) {
			this.state.error = 'No items to submit';
			return;
		}

		this.submissionAbortController = new AbortController();
		this.state.status = 'submitting';
		this.state.error = null;
		this.state.submissionProgress = {
			current: 0,
			total: this.state.confirmedItems.length,
			message: 'Creating items...',
		};

		let successCount = 0;
		let partialSuccessCount = 0;
		let failCount = 0;

		try {
			for (let i = 0; i < this.state.confirmedItems.length; i++) {
				// Check if cancelled
				if (this.submissionAbortController?.signal.aborted) {
					return;
				}

				const confirmedItem = this.state.confirmedItems[i];

				try {
					// Create item
					const itemInput: ItemInput = {
						name: confirmedItem.name,
						quantity: confirmedItem.quantity,
						description: confirmedItem.description,
						label_ids: confirmedItem.label_ids,
						manufacturer: confirmedItem.manufacturer,
						model_number: confirmedItem.model_number,
						serial_number: confirmedItem.serial_number,
						purchase_price: confirmedItem.purchase_price,
						purchase_from: confirmedItem.purchase_from,
						notes: confirmedItem.notes,
					};

					const response = await itemsApi.create({
						items: [itemInput],
						location_id: this.state.locationId,
					});

					if (response.created.length > 0) {
						const createdItem = response.created[0] as { id?: string };
						let attachmentsFailed = false;

						// Upload attachments if item was created
						if (createdItem?.id) {
							// Upload thumbnail or original image (if available)
							if (confirmedItem.customThumbnail) {
								try {
									const thumbnailFile = await this.dataUrlToFile(
										confirmedItem.customThumbnail,
										`thumbnail_${confirmedItem.name.replace(/\s+/g, '_')}.jpg`
									);
									await withRetry(
										() => itemsApi.uploadAttachment(createdItem.id!, thumbnailFile),
										{ 
											maxAttempts: 3, 
											onRetry: (attempt) => console.log(`Retrying thumbnail upload (attempt ${attempt})`)
										}
									);
								} catch (error) {
									console.error(`Failed to upload thumbnail for ${confirmedItem.name}:`, error);
									attachmentsFailed = true;
								}
							} else if (confirmedItem.originalFile) {
								try {
									await withRetry(
										() => itemsApi.uploadAttachment(createdItem.id!, confirmedItem.originalFile!),
										{ 
											maxAttempts: 3, 
											onRetry: (attempt) => console.log(`Retrying image upload (attempt ${attempt})`)
										}
									);
								} catch (error) {
									console.error(`Failed to upload image for ${confirmedItem.name}:`, error);
									attachmentsFailed = true;
								}
							}
							// Note: If both customThumbnail and originalFile are undefined, no primary image is uploaded

							// Upload additional images (if any)
							if (confirmedItem.additionalImages && confirmedItem.additionalImages.length > 0) {
								for (const addImage of confirmedItem.additionalImages) {
									try {
										await withRetry(
											() => itemsApi.uploadAttachment(createdItem.id!, addImage),
											{ 
												maxAttempts: 3, 
												onRetry: (attempt) => console.log(`Retrying additional image upload (attempt ${attempt})`)
											}
										);
									} catch (error) {
										console.error(`Failed to upload additional image for ${confirmedItem.name}:`, error);
										attachmentsFailed = true;
									}
								}
							}
						}

						if (attachmentsFailed) {
							partialSuccessCount++;
						} else {
							successCount++;
						}
					} else {
						failCount++;
					}
				} catch (error) {
					console.error(`Failed to create item ${confirmedItem.name}:`, error);
					failCount++;
				}

				this.state.submissionProgress = {
					current: i + 1,
					total: this.state.confirmedItems.length,
					message: `Created ${successCount + partialSuccessCount} of ${this.state.confirmedItems.length}...`,
				};
			}

			// Handle results
			if (failCount > 0 && successCount === 0 && partialSuccessCount === 0) {
				this.state.error = 'All items failed to create';
				this.state.status = 'confirming';
			} else if (failCount > 0) {
				this.state.error = `Created ${successCount + partialSuccessCount} items, ${failCount} failed`;
				// Stay in submitting state so user can see status
			} else if (partialSuccessCount > 0) {
				this.state.error = `${partialSuccessCount} item(s) created with missing attachments`;
				this.state.status = 'complete';
			} else {
				// Complete success
				this.state.status = 'complete';
			}
		} catch (error) {
			if (this.submissionAbortController?.signal.aborted) {
				return;
			}

			console.error('Submission failed:', error);
			this.state.error = error instanceof Error ? error.message : 'Submission failed';
			this.state.status = 'confirming';
		} finally {
			this.submissionAbortController = null;
		}
	}

	/** Helper to convert data URL to File */
	private async dataUrlToFile(dataUrl: string, filename: string): Promise<File> {
		const response = await fetch(dataUrl);
		const blob = await response.blob();
		return new File([blob], filename, { type: blob.type || 'image/jpeg' });
	}

	// =========================================================================
	// RESET
	// =========================================================================

	/** Reset workflow to initial state */
	reset(): void {
		this.cancelAnalysis();
		this.submissionAbortController?.abort();
		this.submissionAbortController = null;
		this.state = { ...initialState };
	}

	/** Start a new scan (keeps location if set) */
	startNew(): void {
		const locationId = this.state.locationId;
		const locationName = this.state.locationName;
		const locationPath = this.state.locationPath;

		this.reset();

		if (locationId && locationName && locationPath) {
			this.state.locationId = locationId;
			this.state.locationName = locationName;
			this.state.locationPath = locationPath;
			this.state.status = 'capturing';
		} else {
			this.state.status = 'location';
		}
	}

	// =========================================================================
	// HELPERS
	// =========================================================================

	/** Clear error */
	clearError(): void {
		this.state.error = null;
	}

	/** Get source image for a review/confirmed item */
	getSourceImage(item: ReviewItem | ConfirmedItem): CapturedImage | null {
		return this.state.images[item.sourceImageIndex] ?? null;
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const scanWorkflow = new ScanWorkflow();

