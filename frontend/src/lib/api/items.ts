/**
 * Items API endpoints
 */

import { request, requestFormData, requestBlobUrl, type BlobUrlResult } from './client';
import { apiLogger as log } from '../utils/logger';
import type { BatchCreateRequest, BatchCreateResponse, ItemSummary } from '../types';

export type { BlobUrlResult };

export interface CreateOptions {
	signal?: AbortSignal;
}

export interface UploadOptions {
	signal?: AbortSignal;
}

export const items = {
	list: (locationId?: string, signal?: AbortSignal) =>
		request<ItemSummary[]>(`/items${locationId ? `?location_id=${locationId}` : ''}`, { signal }),

	create: (data: BatchCreateRequest, options: CreateOptions = {}) =>
		request<BatchCreateResponse>('/items', {
			method: 'POST',
			body: JSON.stringify(data),
			signal: options.signal,
		}),

	uploadAttachment: (itemId: string, file: File, options: UploadOptions = {}) => {
		// Log file details for diagnostics - helps identify empty/corrupted uploads
		log.debug(`Uploading attachment: item=${itemId}, file="${file.name}", size=${file.size} bytes`);
		if (file.size === 0) {
			log.warn(`Empty file being uploaded to item ${itemId}: ${file.name}`);
		} else if (file.size < 1000) {
			log.warn(`Suspiciously small file being uploaded to item ${itemId}: ${file.name} (${file.size} bytes)`);
		}

		const formData = new FormData();
		formData.append('file', file);
		return requestFormData<unknown>(
			`/items/${itemId}/attachments`,
			formData,
			{ errorMessage: 'Failed to upload attachment', signal: options.signal }
		);
	},

	/**
	 * Fetch a thumbnail image and return a blob URL with cleanup function.
	 * 
	 * IMPORTANT: Call `result.revoke()` when done to avoid memory leaks.
	 * 
	 * @throws {ApiError} When the server returns a non-OK response (e.g., 404 for missing thumbnail)
	 * @throws {NetworkError} When a network-level error occurs (connection, DNS, timeout)
	 */
	getThumbnail: (itemId: string, attachmentId: string, signal?: AbortSignal): Promise<BlobUrlResult> =>
		requestBlobUrl(`/items/${itemId}/attachments/${attachmentId}`, signal),

	/**
	 * Delete an item from Homebox.
	 * Used for cleanup when item creation succeeds but attachment upload fails.
	 */
	delete: (itemId: string, signal?: AbortSignal) => {
		log.debug(`Deleting item: ${itemId}`);
		return request<{ message: string }>(`/items/${itemId}`, {
			method: 'DELETE',
			signal,
		});
	},
};

