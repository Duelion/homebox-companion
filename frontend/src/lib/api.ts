/**
 * API client for Homebox Companion backend
 */

import { get } from 'svelte/store';
import { token } from './stores/auth';

const BASE_URL = '/api';

export class ApiError extends Error {
	status: number;
	data: unknown;

	constructor(status: number, message: string, data?: unknown) {
		super(message);
		this.status = status;
		this.data = data;
		this.name = 'ApiError';
	}
}

async function request<T>(
	endpoint: string,
	options: RequestInit = {}
): Promise<T> {
	const authToken = get(token);

	const headers: HeadersInit = {
		...options.headers,
	};

	// Add auth header if we have a token
	if (authToken) {
		(headers as Record<string, string>)['Authorization'] = `Bearer ${authToken}`;
	}

	// Add content-type for JSON bodies
	if (options.body && typeof options.body === 'string') {
		(headers as Record<string, string>)['Content-Type'] = 'application/json';
	}

	const response = await fetch(`${BASE_URL}${endpoint}`, {
		...options,
		headers,
	});

	if (!response.ok) {
		let errorData: unknown;
		try {
			errorData = await response.json();
		} catch {
			errorData = await response.text();
		}
		throw new ApiError(
			response.status,
			typeof errorData === 'object' && errorData !== null && 'detail' in errorData
				? String((errorData as { detail: unknown }).detail)
				: `Request failed with status ${response.status}`,
			errorData
		);
	}

	return response.json();
}

// Auth endpoints
export const auth = {
	login: (username: string, password: string) =>
		request<{ token: string; message: string }>('/login', {
			method: 'POST',
			body: JSON.stringify({ username, password }),
		}),
};

// Location endpoints
export const locations = {
	list: (filterChildren?: boolean) => {
		const params = filterChildren !== undefined 
			? `?filterChildren=${filterChildren}` 
			: '';
		return request<LocationData[]>(`/locations${params}`);
	},
	tree: () => request<LocationTreeNode[]>('/locations/tree'),
	get: (id: string) => request<LocationData>(`/locations/${id}`),
	create: (data: LocationCreateData) =>
		request<LocationData>('/locations', {
			method: 'POST',
			body: JSON.stringify(data),
		}),
	update: (id: string, data: LocationUpdateData) =>
		request<LocationData>(`/locations/${id}`, {
			method: 'PUT',
			body: JSON.stringify(data),
		}),
};

// Label endpoints
export const labels = {
	list: () => request<LabelData[]>('/labels'),
};

// Item endpoints
export const items = {
	create: (data: BatchCreateRequest) =>
		request<BatchCreateResponse>('/items', {
			method: 'POST',
			body: JSON.stringify(data),
		}),
	uploadAttachment: async (itemId: string, file: File) => {
		const formData = new FormData();
		formData.append('file', file);
		
		const authToken = get(token);
		const response = await fetch(`${BASE_URL}/items/${itemId}/attachments`, {
			method: 'POST',
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			body: formData,
		});
		
		if (!response.ok) {
			throw new ApiError(response.status, 'Failed to upload attachment');
		}
		return response.json();
	},
};

// Vision tool endpoints
export const vision = {
	detect: async (
		image: File,
		options: {
			singleItem?: boolean;
			extraInstructions?: string;
			extractExtendedFields?: boolean;
			additionalImages?: File[];
		} = {}
	): Promise<DetectionResponse> => {
		const formData = new FormData();
		formData.append('image', image);
		
		if (options.singleItem !== undefined) {
			formData.append('single_item', String(options.singleItem));
		}
		if (options.extraInstructions) {
			formData.append('extra_instructions', options.extraInstructions);
		}
		if (options.extractExtendedFields !== undefined) {
			formData.append('extract_extended_fields', String(options.extractExtendedFields));
		}
		if (options.additionalImages) {
			for (const img of options.additionalImages) {
				formData.append('additional_images', img);
			}
		}

		const authToken = get(token);
		const response = await fetch(`${BASE_URL}/tools/vision/detect`, {
			method: 'POST',
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			body: formData,
		});

		if (!response.ok) {
			const error = await response.json().catch(() => ({}));
			throw new ApiError(
				response.status,
				error.detail || 'Detection failed'
			);
		}

		return response.json();
	},

	/**
	 * Detect items from multiple images in parallel on the server.
	 * This is more efficient than calling detect() multiple times.
	 */
	detectBatch: async (
		images: File[],
		options: {
			configs?: Array<{ single_item?: boolean; extra_instructions?: string }>;
			extractExtendedFields?: boolean;
		} = {}
	): Promise<BatchDetectionResponse> => {
		const formData = new FormData();
		
		for (const img of images) {
			formData.append('images', img);
		}
		
		if (options.configs) {
			formData.append('configs', JSON.stringify(options.configs));
		}
		if (options.extractExtendedFields !== undefined) {
			formData.append('extract_extended_fields', String(options.extractExtendedFields));
		}

		const authToken = get(token);
		const response = await fetch(`${BASE_URL}/tools/vision/detect-batch`, {
			method: 'POST',
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			body: formData,
		});

		if (!response.ok) {
			const error = await response.json().catch(() => ({}));
			throw new ApiError(
				response.status,
				error.detail || 'Batch detection failed'
			);
		}

		return response.json();
	},

	analyze: async (
		images: File[],
		itemName: string,
		itemDescription?: string
	): Promise<AdvancedItemDetails> => {
		const formData = new FormData();
		for (const img of images) {
			formData.append('images', img);
		}
		formData.append('item_name', itemName);
		if (itemDescription) {
			formData.append('item_description', itemDescription);
		}

		const authToken = get(token);
		const response = await fetch(`${BASE_URL}/tools/vision/analyze`, {
			method: 'POST',
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			body: formData,
		});

		if (!response.ok) {
			throw new ApiError(response.status, 'Analysis failed');
		}

		return response.json();
	},

	merge: (itemsToMerge: MergeItem[]) =>
		request<MergedItemResponse>('/tools/vision/merge', {
			method: 'POST',
			body: JSON.stringify({ items: itemsToMerge }),
		}),

	correct: async (
		image: File,
		currentItem: MergeItem,
		correctionInstructions: string
	): Promise<CorrectionResponse> => {
		const formData = new FormData();
		formData.append('image', image);
		formData.append('current_item', JSON.stringify(currentItem));
		formData.append('correction_instructions', correctionInstructions);

		const authToken = get(token);
		const response = await fetch(`${BASE_URL}/tools/vision/correct`, {
			method: 'POST',
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			body: formData,
		});

		if (!response.ok) {
			throw new ApiError(response.status, 'Correction failed');
		}

		return response.json();
	},
};

// Version endpoint
export const getVersion = () => request<{ version: string }>('/version');

// Type definitions
export interface LocationData {
	id: string;
	name: string;
	description?: string;
	itemCount?: number;
	children?: LocationData[];
}

export interface LocationTreeNode extends LocationData {
	children: LocationData[];
}

export interface LocationCreateData {
	name: string;
	description?: string;
	parent_id?: string | null;
}

export interface LocationUpdateData {
	name: string;
	description?: string;
	parent_id?: string | null;
}

export interface LabelData {
	id: string;
	name: string;
	description?: string;
	color?: string;
}

export interface DetectedItem {
	name: string;
	quantity: number;
	description?: string | null;
	label_ids?: string[] | null;
	manufacturer?: string | null;
	model_number?: string | null;
	serial_number?: string | null;
	purchase_price?: number | null;
	purchase_from?: string | null;
	notes?: string | null;
}

export interface DetectionResponse {
	items: DetectedItem[];
	message: string;
}

export interface ItemInput {
	name: string;
	quantity?: number;
	description?: string | null;
	location_id?: string | null;
	label_ids?: string[] | null;
	serial_number?: string | null;
	model_number?: string | null;
	manufacturer?: string | null;
	purchase_price?: number | null;
	purchase_from?: string | null;
	notes?: string | null;
	insured?: boolean;
}

export interface BatchCreateRequest {
	items: ItemInput[];
	location_id?: string | null;
}

export interface BatchCreateResponse {
	created: unknown[];
	errors: string[];
	message: string;
}

export interface MergeItem {
	name: string;
	quantity: number;
	description?: string | null;
	manufacturer?: string | null;
	model_number?: string | null;
	serial_number?: string | null;
	purchase_price?: number | null;
	purchase_from?: string | null;
	notes?: string | null;
}

export interface MergedItemResponse {
	name: string;
	quantity: number;
	description?: string | null;
	label_ids?: string[] | null;
}

export interface AdvancedItemDetails {
	name?: string | null;
	description?: string | null;
	serial_number?: string | null;
	model_number?: string | null;
	manufacturer?: string | null;
	purchase_price?: number | null;
	notes?: string | null;
	label_ids?: string[] | null;
}

export interface CorrectionResponse {
	items: DetectedItem[];
	message: string;
}

export interface BatchDetectionResult {
	image_index: number;
	success: boolean;
	items: DetectedItem[];
	error?: string | null;
}

export interface BatchDetectionResponse {
	results: BatchDetectionResult[];
	total_items: number;
	successful_images: number;
	failed_images: number;
	message: string;
}

