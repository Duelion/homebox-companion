/**
 * Items API endpoints
 */

import { request, requestFormData, requestBlobUrl, type BlobUrlResult } from './client';
import { apiLogger as log } from '../utils/logger';
import type {
	BatchCreateRequest,
	BatchCreateResponse,
	ItemSummary,
	AssetIdConflict,
} from '../types';

export type { BlobUrlResult };

export interface CreateOptions {
	signal?: AbortSignal;
}

export interface UploadOptions {
	signal?: AbortSignal;
}

export interface ItemUpdateData {
	assetId?: string | null;
	name?: string;
	description?: string;
	// Add other updatable fields as needed
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

	/**
	 * Update an existing item.
	 * Used to set asset ID after creation (since asset ID cannot be set during creation).
	 */
	update: (itemId: string, data: ItemUpdateData, signal?: AbortSignal) => {
		log.debug(`Updating item ${itemId}:`, data);
		return request<unknown>(`/items/${itemId}`, {
			method: 'PUT',
			body: JSON.stringify(data),
			signal,
		});
	},

	/**
	 * Check if an asset ID is already in use.
	 * Returns conflict info if the ID exists, null otherwise.
	 */
	checkAssetId: async (assetId: string, signal?: AbortSignal): Promise<AssetIdConflict | null> => {
		try {
			// Use our backend proxy which calls Homebox GET /v1/assets/{id}
			const result = await request<{ item_id: string; item_name: string; asset_id: string }>(
				`/assets/${encodeURIComponent(assetId)}`,
				{ signal }
			);
			return result;
		} catch (error) {
			// 404 means asset ID is not in use (available)
			if (error && typeof error === 'object' && 'status' in error && error.status === 404) {
				return null;
			}
			throw error;
		}
	},

	uploadAttachment: (itemId: string, file: File, options: UploadOptions = {}) => {
		// Log file details for diagnostics - helps identify empty/corrupted uploads
		log.debug(`Uploading attachment: item=${itemId}, file="${file.name}", size=${file.size} bytes`);
		if (file.size === 0) {
			log.warn(`Empty file being uploaded to item ${itemId}: ${file.name}`);
		} else if (file.size < 1000) {
			log.warn(
				`Suspiciously small file being uploaded to item ${itemId}: ${file.name} (${file.size} bytes)`
			);
		}

		const formData = new FormData();
		formData.append('file', file);
		return requestFormData<unknown>(`/items/${itemId}/attachments`, formData, {
			errorMessage: 'Failed to upload attachment',
			signal: options.signal,
		});
	},

	/**
	 * Fetch a thumbnail image and return a blob URL with cleanup function.
	 *
	 * IMPORTANT: Call `result.revoke()` when done to avoid memory leaks.
	 *
	 * @throws {ApiError} When the server returns a non-OK response (e.g., 404 for missing thumbnail)
	 * @throws {NetworkError} When a network-level error occurs (connection, DNS, timeout)
	 */
	getThumbnail: (
		itemId: string,
		attachmentId: string,
		signal?: AbortSignal
	): Promise<BlobUrlResult> =>
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
