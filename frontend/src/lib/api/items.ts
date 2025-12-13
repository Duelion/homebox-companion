/**
 * Items API endpoints
 */

import { request, requestFormData } from './client';
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
};

