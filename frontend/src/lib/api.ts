/**
 * API client for Homebox Companion backend
 */

import { get } from 'svelte/store';
import { token, markSessionExpired } from './stores/auth';

// Re-export types for backwards compatibility
export type {
	LocationData,
	LocationTreeNode,
	LocationCreateData,
	LocationUpdateData,
	LabelData,
	DetectedItem,
	DetectionResponse,
	ItemInput,
	BatchCreateRequest,
	BatchCreateResponse,
	MergeItem,
	MergedItemResponse,
	AdvancedItemDetails,
	CorrectionResponse,
	BatchDetectionResult,
	BatchDetectionResponse,
} from './types';

import type {
	LocationData,
	LocationTreeNode,
	LocationCreateData,
	LocationUpdateData,
	LabelData,
	DetectedItem,
	DetectionResponse,
	BatchCreateRequest,
	BatchCreateResponse,
	MergeItem,
	MergedItemResponse,
	AdvancedItemDetails,
	CorrectionResponse,
	BatchDetectionResponse,
} from './types';

const BASE_URL = '/api';

/**
 * Check if response is a 401 and trigger session expired modal
 * Returns true if session expired was triggered
 */
function handleUnauthorized(response: Response): boolean {
	if (response.status === 401) {
		// Only mark as expired if we had a token (avoid triggering on initial login failure)
		const authToken = get(token);
		if (authToken) {
			markSessionExpired();
			return true;
		}
	}
	return false;
}

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

/**
 * Make a JSON API request with automatic auth header and error handling
 */
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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
		// Check for session expiry first
		if (handleUnauthorized(response)) {
			throw new ApiError(401, 'Session expired');
		}

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

/**
 * Make a FormData API request with automatic auth header and error handling.
 * Use this for file uploads and multipart form submissions.
 */
async function requestFormData<T>(
	endpoint: string,
	formData: FormData,
	errorMessage: string = 'Request failed'
): Promise<T> {
	const authToken = get(token);

	const response = await fetch(`${BASE_URL}${endpoint}`, {
		method: 'POST',
		headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
		body: formData,
	});

	if (!response.ok) {
		if (handleUnauthorized(response)) {
			throw new ApiError(401, 'Session expired');
		}
		const error = await response.json().catch(() => ({}));
		throw new ApiError(
			response.status,
			(error as { detail?: string }).detail || errorMessage
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
		const params =
			filterChildren !== undefined ? `?filterChildren=${filterChildren}` : '';
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

// Vision tool endpoints
export const vision = {
	detect: (
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

		return requestFormData<DetectionResponse>(
			'/tools/vision/detect',
			formData,
			'Detection failed'
		);
	},

	/**
	 * Detect items from multiple images in parallel on the server.
	 * This is more efficient than calling detect() multiple times.
	 */
	detectBatch: (
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

		return requestFormData<BatchDetectionResponse>(
			'/tools/vision/detect-batch',
			formData,
			'Batch detection failed'
		);
	},

	analyze: (
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

		return requestFormData<AdvancedItemDetails>(
			'/tools/vision/analyze',
			formData,
			'Analysis failed'
		);
	},

	merge: (itemsToMerge: MergeItem[]) =>
		request<MergedItemResponse>('/tools/vision/merge', {
			method: 'POST',
			body: JSON.stringify({ items: itemsToMerge }),
		}),

	correct: (
		image: File,
		currentItem: MergeItem,
		correctionInstructions: string
	): Promise<CorrectionResponse> => {
		const formData = new FormData();
		formData.append('image', image);
		formData.append('current_item', JSON.stringify(currentItem));
		formData.append('correction_instructions', correctionInstructions);

		return requestFormData<CorrectionResponse>(
			'/tools/vision/correct',
			formData,
			'Correction failed'
		);
	},
};

// Version endpoint
export interface VersionResponse {
	version: string;
	latest_version: string | null;
	update_available: boolean;
}

export const getVersion = (forceCheck: boolean = false) =>
	request<VersionResponse>(`/version${forceCheck ? '?force_check=true' : ''}`);

// Config endpoint
export interface ConfigResponse {
	is_demo_mode: boolean;
	openai_model: string;
	update_check_enabled: boolean;
}

export const getConfig = () => request<ConfigResponse>('/config');

// Logs endpoint
export interface LogsResponse {
	logs: string;
	filename: string | null;
	total_lines: number;
	truncated: boolean;
}

export const getLogs = (lines: number = 200) =>
	request<LogsResponse>(`/logs?lines=${lines}`);