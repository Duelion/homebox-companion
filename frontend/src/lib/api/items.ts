/**
 * Items API endpoints
 */

import { request, requestFormData } from './client';
import type { BatchCreateRequest, BatchCreateResponse } from '../types';

export const items = {
	create: (data: BatchCreateRequest) =>
		request<BatchCreateResponse>('/items', {
			method: 'POST',
			body: JSON.stringify(data),
		}),

	uploadAttachment: (itemId: string, file: File) => {
		const formData = new FormData();
		formData.append('file', file);
		return requestFormData<unknown>(
			`/items/${itemId}/attachments`,
			formData,
			'Failed to upload attachment'
		);
	},
};

