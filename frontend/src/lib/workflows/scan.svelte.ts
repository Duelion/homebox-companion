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

import { vision, items as itemsApi, fieldPreferences, ApiError } from '$lib/api/index';
import { labels as labelsStore } from '$lib/stores/labels';
import { withRetry } from '$lib/utils/retry';
import { checkAuth } from '$lib/utils/token';
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
	ItemSubmissionStatus,
	SubmissionResult,
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
	itemStatuses: {},
	lastSubmissionResult: null,
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
			this.state.error = 'Analysis already in progress';
			return;
		}

		if (this.state.images.length === 0) {
			this.state.error = 'Please add at least one image';
			return;
		}

		console.log(`[ScanWorkflow] Starting analysis for ${this.state.images.length} image(s)`);

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
		try {
			await this.loadDefaultLabel();
		} catch (error) {
			console.error('[ScanWorkflow] Failed to load default label:', error);
			// Continue anyway - default label is optional
		}

		// Update progress message
		const imageCount = this.state.images.length;
		this.state.analysisProgress = {
			current: 0,
			total: imageCount,
			message: imageCount === 1 ? 'Analyzing item...' : 'Analyzing items...',
		};

		try {
			const allDetectedItems: ReviewItem[] = [];
			let completedCount = 0;

		// Process images in parallel
		const signal = this.analysisAbortController?.signal;
		const detectionPromises = this.state.images.map(async (image, index) => {
			try {
				console.log(`[ScanWorkflow] Starting detection for image ${index + 1}/${this.state.images.length}: ${image.file.name}`);
				const response = await vision.detect(image.file, {
					singleItem: !image.separateItems,
					extraInstructions: image.extraInstructions || undefined,
					extractExtendedFields: true,
					additionalImages: image.additionalFiles,
					signal,
				});

				console.log(`[ScanWorkflow] Detection complete for image ${index + 1}, found ${response.items.length} item(s)`);

				completedCount++;
				this.state.analysisProgress = {
					current: completedCount,
					total: this.state.images.length,
					message: this.state.images.length === 1 ? 'Analyzing item...' : 'Analyzing items...',
				};

				return {
					success: true as const,
					imageIndex: index,
					image,
					items: response.items,
				};
			} catch (error) {
				// Re-throw abort errors to be handled at the top level
				if (error instanceof Error && error.name === 'AbortError') {
					console.log(`[ScanWorkflow] Analysis aborted for image ${index + 1}`);
					throw error;
				}
			
				completedCount++;
				this.state.analysisProgress = {
					current: completedCount,
					total: this.state.images.length,
					message: this.state.images.length === 1 ? 'Analyzing item...' : 'Analyzing items...',
				};

				console.error(`[ScanWorkflow] Failed to analyze image ${index + 1} (${image.file.name}):`, error);
				return {
					success: false as const,
					imageIndex: index,
					image,
					error: error instanceof Error ? error.message : 'Unknown error',
				};
			}
		});

		console.log('[ScanWorkflow] Waiting for all detections to complete...');
		const results = await Promise.all(detectionPromises);

		console.log(`[ScanWorkflow] All detections complete. Processing ${results.length} result(s)...`);

		// Check if cancelled
		if (this.analysisAbortController?.signal.aborted) {
			console.log('[ScanWorkflow] Analysis was cancelled, exiting');
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
		console.log(`[ScanWorkflow] Analysis complete! Detected ${allDetectedItems.length} item(s)`);
		this.state.detectedItems = allDetectedItems;
		this.state.currentReviewIndex = 0;
		// Keep analysisProgress for success animation - will be cleared by UI after animation
		this.state.status = 'reviewing';
		} catch (error) {
			// Don't set error if cancelled (check both signal and error type)
			if (this.analysisAbortController?.signal.aborted || 
				(error instanceof Error && error.name === 'AbortError')) {
				console.log('[ScanWorkflow] Analysis cancelled by user');
				return;
			}

			console.error('[ScanWorkflow] Analysis failed with error:', error);
			// Log additional details for network errors
			if (error instanceof Error) {
				console.error('[ScanWorkflow] Error type:', error.name);
				console.error('[ScanWorkflow] Error message:', error.message);
				console.error('[ScanWorkflow] Error stack:', error.stack);
			}
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

	/** Convert data URL to File */
	private async dataUrlToFile(dataUrl: string, filename: string): Promise<File> {
		const response = await fetch(dataUrl);
		const blob = await response.blob();
		return new File([blob], filename, { type: blob.type || 'image/jpeg' });
	}

	/** Upload attachments for a created item. Returns true if all succeeded. */
	private async uploadAttachments(
		itemId: string,
		confirmedItem: ConfirmedItem,
		signal?: AbortSignal
	): Promise<boolean> {
		let allSucceeded = true;

		// Upload custom thumbnail (replaces original) or original image as primary
		if (confirmedItem.customThumbnail) {
			try {
				const thumbnailFile = await this.dataUrlToFile(
					confirmedItem.customThumbnail,
					`thumbnail_${confirmedItem.name.replace(/\s+/g, '_')}.jpg`
				);
				await withRetry(
					() => itemsApi.uploadAttachment(itemId, thumbnailFile, { signal }),
					{
						maxAttempts: 3,
						onRetry: (attempt) => console.log(`Retrying thumbnail upload (attempt ${attempt})`)
					}
				);
			} catch (error) {
				if (error instanceof Error && error.name === 'AbortError') {
					throw error;
				}
				console.error(`Failed to upload thumbnail for ${confirmedItem.name}:`, error);
				allSucceeded = false;
			}
		} else if (confirmedItem.originalFile) {
			// Only upload original if no custom thumbnail (custom thumbnail replaces it)
			try {
				await withRetry(
					() => itemsApi.uploadAttachment(itemId, confirmedItem.originalFile!, { signal }),
					{
						maxAttempts: 3,
						onRetry: (attempt) => console.log(`Retrying image upload (attempt ${attempt})`)
					}
				);
			} catch (error) {
				if (error instanceof Error && error.name === 'AbortError') {
					throw error;
				}
				console.error(`Failed to upload image for ${confirmedItem.name}:`, error);
				allSucceeded = false;
			}
		}

		// Upload additional images (if any)
		if (confirmedItem.additionalImages && confirmedItem.additionalImages.length > 0) {
			for (const addImage of confirmedItem.additionalImages) {
				try {
					await withRetry(
						() => itemsApi.uploadAttachment(itemId, addImage, { signal }),
						{
							maxAttempts: 3,
							onRetry: (attempt) => console.log(`Retrying additional image upload (attempt ${attempt})`)
						}
					);
				} catch (error) {
					if (error instanceof Error && error.name === 'AbortError') {
						throw error;
					}
					console.error(`Failed to upload additional image for ${confirmedItem.name}:`, error);
					allSucceeded = false;
				}
			}
		}

		return allSucceeded;
	}

	/** Submit a single item at the given index. Updates itemStatuses. Returns status. */
	private async submitItem(
		index: number,
		signal?: AbortSignal
	): Promise<ItemSubmissionStatus> {
		const confirmedItem = this.state.confirmedItems[index];
		if (!confirmedItem) return 'failed';

		this.state.itemStatuses = { ...this.state.itemStatuses, [index]: 'creating' };

		try {
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
			}, { signal });

			if (response.created.length > 0) {
				const createdItem = response.created[0] as { id?: string };

				if (createdItem?.id) {
					const attachmentsOk = await this.uploadAttachments(createdItem.id, confirmedItem, signal);
					const status: ItemSubmissionStatus = attachmentsOk ? 'success' : 'partial_success';
					this.state.itemStatuses = { ...this.state.itemStatuses, [index]: status };
					return status;
				}
				// Item created but no ID returned - treat as success
				this.state.itemStatuses = { ...this.state.itemStatuses, [index]: 'success' };
				return 'success';
			} else {
				this.state.itemStatuses = { ...this.state.itemStatuses, [index]: 'failed' };
				return 'failed';
			}
		} catch (error) {
			if (error instanceof Error && error.name === 'AbortError') {
				throw error;
			}
			// Check for 401 authentication error
			if (error instanceof ApiError && error.status === 401) {
				// Session expired - mark and re-throw
				throw error;
			}
			console.error(`Failed to create item ${confirmedItem.name}:`, error);
			this.state.itemStatuses = { ...this.state.itemStatuses, [index]: 'failed' };
			return 'failed';
		}
	}

	/**
	 * Submit all confirmed items to Homebox.
	 * @param options.validateAuth - If true, validate auth token before submitting (default: true)
	 * @returns Object with success, counts, and sessionExpired flag
	 */
	async submitAll(options?: { validateAuth?: boolean }): Promise<{
		success: boolean;
		successCount: number;
		partialSuccessCount: number;
		failCount: number;
		sessionExpired: boolean;
	}> {
		const result = { success: false, successCount: 0, partialSuccessCount: 0, failCount: 0, sessionExpired: false };

		if (this.state.confirmedItems.length === 0) {
			this.state.error = 'No items to submit';
			return result;
		}

		// Validate auth token if requested (default: true)
		if (options?.validateAuth !== false) {
			const isValid = await checkAuth();
			if (!isValid) {
				result.sessionExpired = true;
				return result;
			}
		}

		this.submissionAbortController = new AbortController();
		this.state.status = 'submitting';
		this.state.error = null;
		
		// Initialize all items as pending
		const initialStatuses: Record<number, ItemSubmissionStatus> = {};
		this.state.confirmedItems.forEach((_, index) => {
			initialStatuses[index] = 'pending';
		});
		this.state.itemStatuses = initialStatuses;
		
		this.state.submissionProgress = {
			current: 0,
			total: this.state.confirmedItems.length,
			message: 'Creating items...',
		};

		const signal = this.submissionAbortController?.signal;

		try {
			for (let i = 0; i < this.state.confirmedItems.length; i++) {
				if (signal?.aborted) {
					return result;
				}

				const status = await this.submitItem(i, signal);
				
				if (status === 'success') {
					result.successCount++;
				} else if (status === 'partial_success') {
					result.partialSuccessCount++;
				} else {
					result.failCount++;
				}

				this.state.submissionProgress = {
					current: i + 1,
					total: this.state.confirmedItems.length,
					message: `Created ${result.successCount + result.partialSuccessCount} of ${this.state.confirmedItems.length}...`,
				};
			}

			// Handle results
			if (result.failCount > 0 && result.successCount === 0 && result.partialSuccessCount === 0) {
				this.state.error = 'All items failed to create';
				this.state.status = 'confirming';
			} else if (result.failCount > 0) {
				this.state.error = `Created ${result.successCount + result.partialSuccessCount} items, ${result.failCount} failed`;
				// Keep status as 'submitting' to show per-item status UI
			} else if (result.partialSuccessCount > 0) {
				this.state.error = `${result.partialSuccessCount} item(s) created with missing attachments`;
				this.saveSubmissionResult();
				this.state.status = 'complete';
				result.success = true;
			} else {
				this.saveSubmissionResult();
				this.state.status = 'complete';
				result.success = true;
			}
		} catch (error) {
			if (this.submissionAbortController?.signal.aborted ||
				(error instanceof Error && error.name === 'AbortError')) {
				return result;
			}
			// Check for 401 authentication error
			if (error instanceof ApiError && error.status === 401) {
				result.sessionExpired = true;
				return result;
			}
			console.error('Submission failed:', error);
			this.state.error = error instanceof Error ? error.message : 'Submission failed';
			this.state.status = 'confirming';
		} finally {
			this.submissionAbortController = null;
		}

		return result;
	}

	/**
	 * Retry only failed items.
	 * @returns Object with success flag, counts, and sessionExpired flag
	 */
	async retryFailed(): Promise<{
		success: boolean;
		successCount: number;
		partialSuccessCount: number;
		failCount: number;
		sessionExpired: boolean;
	}> {
		const result = { success: false, successCount: 0, partialSuccessCount: 0, failCount: 0, sessionExpired: false };

		const failedIndices = Object.entries(this.state.itemStatuses)
			.filter(([_, status]) => status === 'failed')
			.map(([index]) => parseInt(index));

		if (failedIndices.length === 0) {
			result.success = true;
			return result;
		}

		// Validate auth token before retrying
		const isValid = await checkAuth();
		if (!isValid) {
			result.sessionExpired = true;
			return result;
		}

		this.submissionAbortController = new AbortController();
		this.state.error = null;

		const signal = this.submissionAbortController?.signal;

		try {
			for (const i of failedIndices) {
				if (signal?.aborted) {
					return result;
				}

				const status = await this.submitItem(i, signal);

				if (status === 'success') {
					result.successCount++;
				} else if (status === 'partial_success') {
					result.partialSuccessCount++;
				} else {
					result.failCount++;
				}
			}

			// Check if all items are now successful
			const allSuccess = Object.values(this.state.itemStatuses).every(
				s => s === 'success' || s === 'partial_success'
			);

			if (allSuccess) {
				this.saveSubmissionResult();
				this.state.status = 'complete';
				result.success = true;
			} else if (result.failCount > 0) {
				this.state.error = `Retried: ${result.successCount + result.partialSuccessCount} succeeded, ${result.failCount} still failing`;
			}
		} catch (error) {
			if (this.submissionAbortController?.signal.aborted ||
				(error instanceof Error && error.name === 'AbortError')) {
				return result;
			}
			if (error instanceof ApiError && error.status === 401) {
				result.sessionExpired = true;
				return result;
			}
			console.error('Retry failed:', error);
			this.state.error = error instanceof Error ? error.message : 'Retry failed';
		} finally {
			this.submissionAbortController = null;
		}

		return result;
	}

	/** Check if there are any failed items */
	hasFailedItems(): boolean {
		return Object.values(this.state.itemStatuses).some(s => s === 'failed');
	}

	/** Check if all items were successfully submitted */
	allItemsSuccessful(): boolean {
		return Object.keys(this.state.itemStatuses).length > 0 &&
			Object.values(this.state.itemStatuses).every(s => s === 'success' || s === 'partial_success');
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

	/** Save submission result for success page display */
	private saveSubmissionResult(): void {
		// Count successful items
		const successfulIndices = Object.entries(this.state.itemStatuses)
			.filter(([_, status]) => status === 'success' || status === 'partial_success')
			.map(([index]) => parseInt(index));

		const successfulItems = successfulIndices.map(i => this.state.confirmedItems[i]).filter(Boolean);

		// Calculate totals
		const itemNames = successfulItems.map(item => item.name);
		const photoCount = successfulItems.reduce((count, item) => {
			let photos = 0;
			// Custom thumbnail replaces original, so count as one primary image
			if (item.originalFile || item.customThumbnail) photos++;
			if (item.additionalImages) photos += item.additionalImages.length;
			return count + photos;
		}, 0);

		// Count unique labels across all items
		const allLabelIds = new Set<string>();
		successfulItems.forEach(item => {
			item.label_ids?.forEach(id => allLabelIds.add(id));
		});

		this.state.lastSubmissionResult = {
			itemCount: successfulItems.length,
			photoCount,
			labelCount: allLabelIds.size,
			itemNames,
			locationName: this.state.locationName || 'Unknown',
			locationId: this.state.locationId || '',
		};
	}

	/** Get last submission result (preserved after workflow completion) */
	get submissionResult(): SubmissionResult | null {
		return this.state.lastSubmissionResult;
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const scanWorkflow = new ScanWorkflow();

