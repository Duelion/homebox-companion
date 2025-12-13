/**
 * Items API endpoints
 */

import { request, requestFormData, requestBlobUrl } from './client';
import type { BatchCreateRequest, BatchCreateResponse, ItemSummary } from '../types';

export interface CreateOptions {
	signal?: AbortSignal;
}

export interface UploadOptions {
	signal?: AbortSignal;
}

export const items = {
	list: (locationId?: string) =>
		request<ItemSummary[]>(`/items${locationId ? `?location_id=${locationId}` : ''}`),

	create: (data: BatchCreateRequest, options: CreateOptions = {}) =>
		request<BatchCreateResponse>('/items', {
			method: 'POST',
			body: JSON.stringify(data),
			signal: options.signal,
		}),

	uploadAttachment: (itemId: string, file: File, options: UploadOptions = {}) => {
		const formData = new FormData();
		formData.append('file', file);
		return requestFormData<unknown>(
			`/items/${itemId}/attachments`,
			formData,
			{ errorMessage: 'Failed to upload attachment', signal: options.signal }
		);
	},

	/**
	 * Fetch a thumbnail image and return a blob URL for use in <img> src.
	 * Returns null if the thumbnail doesn't exist or fails to load.
	 */
	getThumbnail: (itemId: string, attachmentId: string, signal?: AbortSignal) =>
		requestBlobUrl(`/items/${itemId}/attachments/${attachmentId}`, signal),
};

