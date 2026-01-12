/**
 * SubmissionService - Handles item submission to Homebox
 *
 * Responsibilities:
 * - Creating items in Homebox
 * - Uploading attachments (images, thumbnails)
 * - Progress tracking
 * - Retry failed items
 * - Submission result tracking
 */

import { items as itemsApi } from '$lib/api/index';
import { ApiError } from '$lib/api/client';
import { withRetry } from '$lib/utils/retry';
import { workflowLogger as log } from '$lib/utils/logger';
import { hasToken } from '$lib/utils/token';
import type {
	ConfirmedItem,
	Progress,
	ItemInput,
	ItemSubmissionStatus,
	SubmissionResult,
	UpdateDecision,
	MergeItemRequest,
} from '$lib/types';

// =============================================================================
// TYPES
// =============================================================================

export interface SubmitResult {
	success: boolean;
	successCount: number;
	partialSuccessCount: number;
	failCount: number;
	sessionExpired: boolean;
	/** Backend error messages for items that failed to create */
	errors: string[];
}

// =============================================================================
// SUBMISSION SERVICE CLASS
// =============================================================================

export class SubmissionService {
	/** Progress of current submission operation */
	progress = $state<Progress | null>(null);

	/** Per-item submission status */
	itemStatuses = $state<Record<number, ItemSubmissionStatus>>({});

	/** Result of last successful submission (for success page) */
	lastResult = $state<SubmissionResult | null>(null);

	/** Error messages from the last submission attempt */
	lastErrors = $state<string[]>([]);

	/** Abort controller for cancellable operations */
	private abortController: AbortController | null = null;

	// =========================================================================
	// HELPERS
	// =========================================================================

	/** Convert data URL to File */
	private async dataUrlToFile(dataUrl: string, filename: string): Promise<File> {
		// Validate data URL format
		if (!dataUrl || !dataUrl.startsWith('data:')) {
			log.warn(`Invalid data URL for ${filename}: missing or malformed`);
			throw new Error(`Invalid data URL for ${filename}`);
		}

		const response = await fetch(dataUrl);
		const blob = await response.blob();

		// Validate blob has content
		if (blob.size === 0) {
			log.warn(`Empty blob created from data URL for ${filename}`);
			throw new Error(`Empty image data for ${filename}`);
		} else if (blob.size < 1000) {
			log.warn(`Suspiciously small blob for ${filename}: ${blob.size} bytes`);
		}

		log.debug(`Converted data URL to file: ${filename}, size: ${blob.size} bytes`);
		return new File([blob], filename, { type: blob.type || 'image/jpeg' });
	}

	/**
	 * Upload attachments for a created item.
	 * Returns status indicating what succeeded/failed.
	 */
	private async uploadAttachments(
		itemId: string,
		confirmedItem: ConfirmedItem,
		signal?: AbortSignal
	): Promise<{ primaryFailed: boolean; additionalFailed: boolean }> {
		let primaryFailed = false;
		let additionalFailed = false;

		// Upload custom thumbnail (replaces original) or compressed/original image as primary
		if (confirmedItem.customThumbnail) {
			try {
				const thumbnailFile = await this.dataUrlToFile(
					confirmedItem.customThumbnail,
					`thumbnail_${confirmedItem.name.replace(/\s+/g, '_')}.jpg`
				);
				await withRetry(() => itemsApi.uploadAttachment(itemId, thumbnailFile, { signal }), {
					maxAttempts: 3,
					onRetry: (attempt) => log.debug(`Retrying thumbnail upload (attempt ${attempt})`),
				});
			} catch (error) {
				if (error instanceof Error && error.name === 'AbortError') {
					throw error;
				}
				log.error(`Failed to upload thumbnail for ${confirmedItem.name}`, error);
				primaryFailed = true;
			}
		} else if (confirmedItem.compressedDataUrl) {
			// Use compressed image if available (preferred)
			try {
				const compressedFile = await this.dataUrlToFile(
					confirmedItem.compressedDataUrl,
					`${confirmedItem.name.replace(/\s+/g, '_')}.jpg`
				);
				await withRetry(() => itemsApi.uploadAttachment(itemId, compressedFile, { signal }), {
					maxAttempts: 3,
					onRetry: (attempt) => log.debug(`Retrying compressed image upload (attempt ${attempt})`),
				});
			} catch (error) {
				if (error instanceof Error && error.name === 'AbortError') {
					throw error;
				}
				log.error(`Failed to upload compressed image for ${confirmedItem.name}`, error);
				primaryFailed = true;
			}
		} else if (confirmedItem.originalFile) {
			// Fallback to original file if no compressed version available
			try {
				await withRetry(
					() => itemsApi.uploadAttachment(itemId, confirmedItem.originalFile!, { signal }),
					{
						maxAttempts: 3,
						onRetry: (attempt) => log.debug(`Retrying image upload (attempt ${attempt})`),
					}
				);
			} catch (error) {
				if (error instanceof Error && error.name === 'AbortError') {
					throw error;
				}
				log.error(`Failed to upload image for ${confirmedItem.name}`, error);
				primaryFailed = true;
			}
		}

		// If primary image failed, don't bother with additional images
		// The item will be deleted anyway
		if (primaryFailed) {
			return { primaryFailed, additionalFailed: false };
		}

		// Upload additional images (prefer compressed versions)
		const additionalToUpload: File[] = [];

		// Use compressed additional images if available
		if (
			confirmedItem.compressedAdditionalDataUrls &&
			confirmedItem.compressedAdditionalDataUrls.length > 0
		) {
			for (let i = 0; i < confirmedItem.compressedAdditionalDataUrls.length; i++) {
				try {
					const additionalFile = await this.dataUrlToFile(
						confirmedItem.compressedAdditionalDataUrls[i],
						`${confirmedItem.name.replace(/\s+/g, '_')}_${i + 1}.jpg`
					);
					additionalToUpload.push(additionalFile);
				} catch (error) {
					log.error(`Failed to convert compressed additional image ${i}`, error);
					additionalFailed = true;
				}
			}
		} else if (confirmedItem.additionalImages && confirmedItem.additionalImages.length > 0) {
			// Fallback to original additional images
			additionalToUpload.push(...confirmedItem.additionalImages);
		}

		// Upload all additional images
		for (const addImage of additionalToUpload) {
			try {
				await withRetry(() => itemsApi.uploadAttachment(itemId, addImage, { signal }), {
					maxAttempts: 3,
					onRetry: (attempt) => log.debug(`Retrying additional image upload (attempt ${attempt})`),
				});
			} catch (error) {
				if (error instanceof Error && error.name === 'AbortError') {
					throw error;
				}
				log.error(`Failed to upload additional image for ${confirmedItem.name}`, error);
				additionalFailed = true;
			}
		}

		return { primaryFailed, additionalFailed };
	}

	/**
	 * Update an existing item via merge API and upload new photos.
	 * This is called when user chose "Update Existing" on a duplicate.
	 */
	private async updateExistingItem(
		index: number,
		confirmedItem: ConfirmedItem,
		updateDecision: UpdateDecision,
		signal?: AbortSignal
	): Promise<{ status: ItemSubmissionStatus; error?: string }> {
		this.itemStatuses = { ...this.itemStatuses, [index]: 'creating' };

		try {
			// Build merge request - only include fields with values
			const mergeRequest: MergeItemRequest = {
				name: confirmedItem.name || undefined,
				description: confirmedItem.description || undefined,
				manufacturer: confirmedItem.manufacturer || undefined,
				model_number: confirmedItem.model_number || undefined,
				serial_number: confirmedItem.serial_number || undefined,
				purchase_price: confirmedItem.purchase_price || undefined,
				purchase_from: confirmedItem.purchase_from || undefined,
				notes: confirmedItem.notes || undefined,
				label_ids: confirmedItem.label_ids ?? undefined,
				exclude_field: updateDecision.matchField,
			};

			log.info(`Merging item ${confirmedItem.name} into existing item ${updateDecision.targetItemId}`);

			// Call merge API
			const mergeResponse = await withRetry(
				() => itemsApi.merge(updateDecision.targetItemId, mergeRequest, { signal }),
				{
					maxAttempts: 3,
					onRetry: (attempt) => log.debug(`Retrying merge (attempt ${attempt})`),
				}
			);

			log.info(`Merge result: ${mergeResponse.fields_updated.length} fields updated, ${mergeResponse.fields_skipped.length} skipped`);

			// Upload attachments to existing item (append photos)
			const uploadResult = await this.uploadAttachments(
				updateDecision.targetItemId,
				confirmedItem,
				signal
			);

			// For merge, we don't delete the item if primary photo fails - the item already exists
			// Just report partial success
			if (uploadResult.primaryFailed) {
				log.warn(`Primary image upload failed for merge to ${updateDecision.targetItemName}`);
				this.itemStatuses = { ...this.itemStatuses, [index]: 'partial_success' };
				return {
					status: 'partial_success',
					error: `Updated "${updateDecision.targetItemName}" but failed to upload image`,
				};
			}

			if (uploadResult.additionalFailed) {
				log.warn(`Additional images failed for merge to ${updateDecision.targetItemName}`);
				this.itemStatuses = { ...this.itemStatuses, [index]: 'partial_success' };
				return {
					status: 'partial_success',
					error: `Updated "${updateDecision.targetItemName}" but some images failed`,
				};
			}

			// Full success
			this.itemStatuses = { ...this.itemStatuses, [index]: 'success' };
			return { status: 'success' };
		} catch (error) {
			if (error instanceof Error && error.name === 'AbortError') {
				throw error;
			}
			if (error instanceof ApiError && error.status === 401) {
				throw error; // Re-throw for session handling
			}
			if (error instanceof ApiError && error.status === 404) {
				// Target item was deleted - fall back to creating new
				log.warn(`Target item ${updateDecision.targetItemId} not found, will need to create new`);
				this.itemStatuses = { ...this.itemStatuses, [index]: 'failed' };
				return {
					status: 'failed',
					error: `Existing item "${updateDecision.targetItemName}" was deleted - please create as new`,
				};
			}
			const errorMsg = error instanceof Error ? error.message : 'Unknown error';
			log.error(`Failed to merge item ${confirmedItem.name}`, error);
			this.itemStatuses = { ...this.itemStatuses, [index]: 'failed' };
			return { status: 'failed', error: errorMsg };
		}
	}

	/** Submit a single item. Updates itemStatuses. Returns status and any error message. */
	private async submitItem(
		index: number,
		confirmedItem: ConfirmedItem,
		locationId: string | null,
		parentId: string | null,
		signal?: AbortSignal
	): Promise<{ status: ItemSubmissionStatus; error?: string }> {
		this.itemStatuses = { ...this.itemStatuses, [index]: 'creating' };

		try {
			const itemInput: ItemInput = {
				name: confirmedItem.name,
				quantity: confirmedItem.quantity,
				description: confirmedItem.description,
				label_ids: confirmedItem.label_ids,
				parent_id: parentId,
				manufacturer: confirmedItem.manufacturer,
				model_number: confirmedItem.model_number,
				serial_number: confirmedItem.serial_number,
				purchase_price: confirmedItem.purchase_price,
				purchase_from: confirmedItem.purchase_from,
				notes: confirmedItem.notes,
			};

			const response = await itemsApi.create(
				{
					items: [itemInput],
					location_id: locationId,
				},
				{ signal }
			);

			// Check for backend errors (207 Multi-Status partial failure)
			if (response.errors && response.errors.length > 0) {
				// If we have both created items and errors, it's a partial success
				// For single-item submission, if there's an error, the item failed
				if (response.created.length === 0) {
					const errorMsg = response.errors[0];
					log.error(`Backend error creating item ${confirmedItem.name}: ${errorMsg}`);
					this.itemStatuses = { ...this.itemStatuses, [index]: 'failed' };
					return { status: 'failed', error: errorMsg };
				}
				// Item was created but there was also an error (shouldn't happen for single item)
				log.warn(`Item ${confirmedItem.name} created with warnings: ${response.errors.join(', ')}`);
			}

			if (response.created.length > 0) {
				const createdItem = response.created[0];

				if (createdItem?.id) {
					const uploadResult = await this.uploadAttachments(createdItem.id, confirmedItem, signal);

					// If primary image failed, delete the created item and mark as failed
					if (uploadResult.primaryFailed) {
						log.warn(
							`Primary image upload failed for ${confirmedItem.name}, deleting item ${createdItem.id}`
						);
						try {
							await itemsApi.delete(createdItem.id, signal);
							log.info(`Deleted item ${createdItem.id} after image upload failure`);
						} catch (deleteError) {
							// Log but don't fail - the item might be orphaned but that's better than hiding the failure
							log.error(
								`Failed to cleanup item ${createdItem.id} after upload failure`,
								deleteError
							);
						}
						this.itemStatuses = { ...this.itemStatuses, [index]: 'failed' };
						return {
							status: 'failed',
							error: `Failed to upload image for '${confirmedItem.name}'`,
						};
					}

					// Primary succeeded - check for additional image failures
					if (uploadResult.additionalFailed) {
						log.warn(
							`Additional images failed to upload for ${confirmedItem.name} (item created successfully)`
						);
						this.itemStatuses = { ...this.itemStatuses, [index]: 'partial_success' };
						return {
							status: 'partial_success',
							error: `Item created but some additional images failed to upload`,
						};
					}

					// All uploads succeeded
					const status: ItemSubmissionStatus = 'success';
					this.itemStatuses = { ...this.itemStatuses, [index]: status };
					return { status };
				}
				// Item created but no ID returned - log warning and treat as partial success
				log.warn(`Item ${confirmedItem.name} created but response missing 'id' field`);
				this.itemStatuses = { ...this.itemStatuses, [index]: 'partial_success' };
				return {
					status: 'partial_success',
					error: 'Item created but no ID returned - attachments skipped',
				};
			} else {
				// No created items and no errors - unexpected state
				log.error(`No items created for ${confirmedItem.name} and no error reported`);
				this.itemStatuses = { ...this.itemStatuses, [index]: 'failed' };
				return { status: 'failed', error: 'Item creation failed - no items returned' };
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
			const errorMsg = error instanceof Error ? error.message : 'Unknown error';
			log.error(`Failed to create item ${confirmedItem.name}`, error);
			this.itemStatuses = { ...this.itemStatuses, [index]: 'failed' };
			return { status: 'failed', error: errorMsg };
		}
	}

	// =========================================================================
	// PUBLIC METHODS
	// =========================================================================

	/**
	 * Submit all confirmed items to Homebox.
	 * @param items - Array of confirmed items to submit
	 * @param locationId - Target location ID
	 * @param parentId - Optional parent item ID (for sub-items)
	 * @param updateDecisions - Items marked for update (merge) instead of create
	 * @param options.validateAuth - If true, validate auth token before submitting (default: true)
	 */
	async submitAll(
		items: ConfirmedItem[],
		locationId: string | null,
		parentId: string | null,
		updateDecisions?: UpdateDecision[],
		options?: { validateAuth?: boolean }
	): Promise<SubmitResult> {
		const result: SubmitResult = {
			success: false,
			successCount: 0,
			partialSuccessCount: 0,
			failCount: 0,
			sessionExpired: false,
			errors: [],
		};

		if (items.length === 0) {
			return result;
		}

		// Validate auth token if requested (default: true)
		if (options?.validateAuth !== false) {
			if (!hasToken()) {
				result.sessionExpired = true;
				return result;
			}
		}

		this.abortController = new AbortController();

		// Initialize all items as pending
		const initialStatuses: Record<number, ItemSubmissionStatus> = {};
		items.forEach((_, index) => {
			initialStatuses[index] = 'pending';
		});
		this.itemStatuses = initialStatuses;

		this.progress = {
			current: 0,
			total: items.length,
			message: 'Creating items...',
		};

		const signal = this.abortController?.signal;

		// Build a map for quick lookup of update decisions by item index
		const updateDecisionMap = new Map<number, UpdateDecision>();
		if (updateDecisions) {
			for (const decision of updateDecisions) {
				updateDecisionMap.set(decision.itemIndex, decision);
			}
		}

		try {
			for (let i = 0; i < items.length; i++) {
				if (signal?.aborted) {
					return result;
				}

				// Check if this item should be merged into an existing item
				const updateDecision = updateDecisionMap.get(i);
				let itemResult: { status: ItemSubmissionStatus; error?: string };

				if (updateDecision) {
					// Update existing item
					itemResult = await this.updateExistingItem(i, items[i], updateDecision, signal);
				} else {
					// Create new item
					itemResult = await this.submitItem(i, items[i], locationId, parentId, signal);
				}

				if (itemResult.status === 'success') {
					result.successCount++;
				} else if (itemResult.status === 'partial_success') {
					result.partialSuccessCount++;
					// Collect warning for partial success (e.g., missing attachments)
					if (itemResult.error) {
						result.errors.push(`${items[i].name}: ${itemResult.error}`);
					}
				} else {
					result.failCount++;
					// Collect error message for failed items
					if (itemResult.error) {
						result.errors.push(itemResult.error);
					} else {
						result.errors.push(`Failed to create '${items[i].name}'`);
					}
				}

				this.progress = {
					current: i + 1,
					total: items.length,
					message: `Created ${result.successCount + result.partialSuccessCount} of ${items.length}...`,
				};
			}

			// Determine overall success
			if (result.failCount === 0) {
				result.success = true;
			} else if (result.successCount > 0 || result.partialSuccessCount > 0) {
				// Partial success - some items created
				result.success = false;
			}

			// Save errors for UI display
			this.lastErrors = result.errors;
			return result;
		} catch (error) {
			if (
				this.abortController?.signal.aborted ||
				(error instanceof Error && error.name === 'AbortError')
			) {
				this.lastErrors = result.errors;
				return result;
			}
			// Check for 401 authentication error
			if (error instanceof ApiError && error.status === 401) {
				result.sessionExpired = true;
				this.lastErrors = result.errors;
				return result;
			}
			log.error('Submission failed', error);
			const errorMsg = error instanceof Error ? error.message : 'Unknown error';
			result.errors.push(`Submission failed: ${errorMsg}`);
			this.lastErrors = result.errors;
			return result;
		} finally {
			this.abortController = null;
		}
	}

	/**
	 * Retry only failed items.
	 * @param items - Full array of confirmed items (uses itemStatuses to find failures)
	 * @param locationId - Target location ID
	 * @param parentId - Optional parent item ID (for sub-items)
	 * @param updateDecisions - Items marked for update (merge) instead of create
	 */
	async retryFailed(
		items: ConfirmedItem[],
		locationId: string | null,
		parentId: string | null,
		updateDecisions?: UpdateDecision[]
	): Promise<SubmitResult> {
		const result: SubmitResult = {
			success: false,
			successCount: 0,
			partialSuccessCount: 0,
			failCount: 0,
			sessionExpired: false,
			errors: [],
		};

		const failedIndices = Object.entries(this.itemStatuses)
			.filter(([_, status]) => status === 'failed')
			.map(([index]) => parseInt(index));

		if (failedIndices.length === 0) {
			result.success = true;
			return result;
		}

		// Validate auth token before retrying
		if (!hasToken()) {
			result.sessionExpired = true;
			return result;
		}

		this.abortController = new AbortController();
		const signal = this.abortController?.signal;

		// Build a map for quick lookup of update decisions by item index
		const updateDecisionMap = new Map<number, UpdateDecision>();
		if (updateDecisions) {
			for (const decision of updateDecisions) {
				updateDecisionMap.set(decision.itemIndex, decision);
			}
		}

		try {
			for (const i of failedIndices) {
				if (signal?.aborted) {
					return result;
				}

				// Check if this item should be merged into an existing item
				const updateDecision = updateDecisionMap.get(i);
				let itemResult: { status: ItemSubmissionStatus; error?: string };

				if (updateDecision) {
					// Update existing item
					itemResult = await this.updateExistingItem(i, items[i], updateDecision, signal);
				} else {
					// Create new item
					itemResult = await this.submitItem(i, items[i], locationId, parentId, signal);
				}

				if (itemResult.status === 'success') {
					result.successCount++;
				} else if (itemResult.status === 'partial_success') {
					result.partialSuccessCount++;
					if (itemResult.error) {
						result.errors.push(`${items[i].name}: ${itemResult.error}`);
					}
				} else {
					result.failCount++;
					if (itemResult.error) {
						result.errors.push(itemResult.error);
					} else {
						result.errors.push(`Failed to create '${items[i].name}'`);
					}
				}
			}

			// Check if all items are now successful
			const allSuccess = Object.values(this.itemStatuses).every(
				(s) => s === 'success' || s === 'partial_success'
			);

			if (allSuccess) {
				result.success = true;
			}

			// Save errors for UI display
			this.lastErrors = result.errors;
			return result;
		} catch (error) {
			if (
				this.abortController?.signal.aborted ||
				(error instanceof Error && error.name === 'AbortError')
			) {
				this.lastErrors = result.errors;
				return result;
			}
			if (error instanceof ApiError && error.status === 401) {
				result.sessionExpired = true;
				this.lastErrors = result.errors;
				return result;
			}
			log.error('Retry failed', error);
			const errorMsg = error instanceof Error ? error.message : 'Unknown error';
			result.errors.push(`Retry failed: ${errorMsg}`);
			this.lastErrors = result.errors;
			return result;
		} finally {
			this.abortController = null;
		}
	}

	/** Cancel ongoing submission */
	cancel(): void {
		if (this.abortController) {
			this.abortController.abort();
		}
	}

	/**
	 * Save submission result for success page display
	 * @param items - Confirmed items that were submitted
	 * @param locationName - Name of the target location
	 * @param locationId - ID of the target location
	 */
	saveResult(items: ConfirmedItem[], locationName: string | null, locationId: string | null): void {
		// Count successful items
		const successfulIndices = Object.entries(this.itemStatuses)
			.filter(([_, status]) => status === 'success' || status === 'partial_success')
			.map(([index]) => parseInt(index));

		const successfulItems = successfulIndices.map((i) => items[i]).filter(Boolean);

		// Calculate totals
		const itemNames = successfulItems.map((item) => item.name);
		const photoCount = successfulItems.reduce((count, item) => {
			let photos = 0;
			// Count primary image (compressed preferred, or custom thumbnail, or original file)
			if (item.compressedDataUrl || item.customThumbnail || item.originalFile) photos++;
			if (item.additionalImages) photos += item.additionalImages.length;
			return count + photos;
		}, 0);

		// Count unique labels across all items
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- Temporary collection for counting
		const allLabelIds = new Set<string>();
		successfulItems.forEach((item) => {
			item.label_ids?.forEach((id) => allLabelIds.add(id));
		});

		this.lastResult = {
			itemCount: successfulItems.length,
			photoCount,
			labelCount: allLabelIds.size,
			itemNames,
			locationName: locationName || 'Unknown',
			locationId: locationId || '',
		};
	}

	// =========================================================================
	// RESET
	// =========================================================================

	/** Reset all submission state */
	reset(): void {
		// Abort any in-progress submission before clearing state
		if (this.abortController) {
			this.abortController.abort();
			this.abortController = null;
		}
		this.progress = null;
		this.itemStatuses = {};
		this.lastResult = null;
		this.lastErrors = [];
	}

	// =========================================================================
	// GETTERS
	// =========================================================================

	/** Check if there are any failed items */
	hasFailedItems(): boolean {
		return Object.values(this.itemStatuses).some((s) => s === 'failed');
	}

	/** Check if all items were successfully submitted */
	allItemsSuccessful(): boolean {
		return (
			Object.keys(this.itemStatuses).length > 0 &&
			Object.values(this.itemStatuses).every((s) => s === 'success' || s === 'partial_success')
		);
	}

	/** Check if submission is in progress */
	get isSubmitting(): boolean {
		return this.abortController !== null;
	}
}
