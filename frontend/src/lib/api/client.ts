/**
 * Base API client with error handling and authentication
 */

import { get } from 'svelte/store';
import { token, markSessionExpired } from '../stores/auth';
import { apiLogger as log } from '../utils/logger';

const BASE_URL = '/api';

/**
 * API Error class with status and data
 */
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
 * Check if response is a 401 and trigger session expired modal
 */
function handleUnauthorized(response: Response): boolean {
	if (response.status === 401) {
		const authToken = get(token);
		if (authToken) {
			markSessionExpired();
			return true;
		}
	}
	return false;
}

/**
 * Check if response has JSON content based on Content-Type header
 */
function isJsonResponse(response: Response): boolean {
	const contentType = response.headers.get('content-type');
	return contentType !== null && contentType.includes('application/json');
}

/**
 * Safely parse response body based on status and content type.
 * Returns undefined for 204 No Content or empty responses.
 */
async function parseResponseBody<T>(response: Response): Promise<T> {
	// 204 No Content - return undefined
	if (response.status === 204) {
		return undefined as T;
	}

	// Check Content-Length for empty body
	const contentLength = response.headers.get('content-length');
	if (contentLength === '0') {
		return undefined as T;
	}

	// Parse based on content type
	if (isJsonResponse(response)) {
		return response.json();
	}

	// Non-JSON response - return text as-is (caller can handle)
	const text = await response.text();
	// If empty text, return undefined
	if (!text) {
		return undefined as T;
	}
	// Return text (type assertion since caller expects T)
	return text as T;
}

export interface RequestOptions extends RequestInit {
	signal?: AbortSignal;
}

/**
 * Make a JSON API request with automatic auth header and error handling
 */
export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
	const authToken = get(token);

	const headers: HeadersInit = {
		...options.headers,
	};

	if (authToken) {
		(headers as Record<string, string>)['Authorization'] = `Bearer ${authToken}`;
	}

	if (options.body && typeof options.body === 'string') {
		(headers as Record<string, string>)['Content-Type'] = 'application/json';
	}

	const response = await fetch(`${BASE_URL}${endpoint}`, {
		...options,
		headers,
		signal: options.signal,
	});

	if (!response.ok) {
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

	return parseResponseBody<T>(response);
}

export interface FormDataRequestOptions {
	signal?: AbortSignal;
	errorMessage?: string;
}

/**
 * Result of a blob URL request, including the URL and a cleanup function.
 */
export interface BlobUrlResult {
	/** The blob URL for use in img.src, etc. */
	url: string;
	/** Call this function to revoke the URL and free memory. */
	revoke: () => void;
}

/**
 * Fetch a binary resource (image, file) with authentication and return a blob URL with cleanup.
 * 
 * IMPORTANT: Blob URLs hold references to underlying data and MUST be revoked to avoid memory leaks.
 * Call `result.revoke()` when the URL is no longer needed (e.g., in onDestroy or when removing an image).
 * 
 * @param endpoint - API endpoint to fetch
 * @param signal - Optional AbortSignal for cancellation
 * @returns BlobUrlResult with url and revoke function, or null if the request fails
 * 
 * @example
 * ```typescript
 * const result = await requestBlobUrl('/items/123/thumbnail');
 * if (result) {
 *   img.src = result.url;
 *   // Later, when done with the image:
 *   result.revoke();
 * }
 * ```
 */
export async function requestBlobUrl(endpoint: string, signal?: AbortSignal): Promise<BlobUrlResult | null> {
	const authToken = get(token);

	try {
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			signal,
		});

		if (!response.ok) {
			if (handleUnauthorized(response)) {
				return null;
			}
			log.debug(`Blob request failed for ${endpoint}: ${response.status}`);
			return null;
		}

		const blob = await response.blob();
		const url = URL.createObjectURL(blob);
		
		return {
			url,
			revoke: () => URL.revokeObjectURL(url)
		};
	} catch (error) {
		if (error instanceof Error && error.name === 'AbortError') {
			// Request was cancelled, not an error
			return null;
		}
		log.debug(`Blob request error for ${endpoint}:`, error);
		return null;
	}
}

/**
 * Make a FormData API request with automatic auth header and error handling.
 * Use this for file uploads and multipart form submissions.
 */
export async function requestFormData<T>(
	endpoint: string,
	formData: FormData,
	options: FormDataRequestOptions | string = {}
): Promise<T> {
	// Support legacy string errorMessage parameter for backwards compatibility
	const opts: FormDataRequestOptions = typeof options === 'string' 
		? { errorMessage: options } 
		: options;
	const errorMessage = opts.errorMessage ?? 'Request failed';
	
	const authToken = get(token);

	try {
		log.debug(`FormData request to ${endpoint}`);
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			method: 'POST',
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			body: formData,
			signal: opts.signal,
		});

		log.debug(`Response from ${endpoint}:`, response.status, response.statusText);

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

		return parseResponseBody<T>(response);
	} catch (error) {
		// Log network errors before re-throwing
		if (error instanceof ApiError) {
			// Already handled above, just re-throw
			throw error;
		}
		log.error(`Network error for ${endpoint}`, error);
		throw error;
	}
}

