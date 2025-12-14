/**
 * Base API client with error handling and authentication
 */

import { get } from 'svelte/store';
import { token, markSessionExpired, logout } from '../stores/auth';
import { apiLogger as log } from '../utils/logger';

const BASE_URL = '/api';

/**
 * Default request timeout in milliseconds.
 * Applies when no AbortSignal is provided by the caller.
 */
export const DEFAULT_REQUEST_TIMEOUT_MS = 60_000;

/**
 * Create a combined AbortSignal that aborts when either:
 * - The caller's signal aborts (if provided)
 * - The default timeout elapses
 * 
 * @param callerSignal - Optional signal from the caller
 * @param timeoutMs - Timeout in milliseconds
 * @returns AbortSignal that respects both conditions
 */
function createTimeoutSignal(callerSignal?: AbortSignal, timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS): AbortSignal {
	const timeoutSignal = AbortSignal.timeout(timeoutMs);
	
	if (!callerSignal) {
		return timeoutSignal;
	}
	
	// Combine caller signal with timeout signal
	// AbortSignal.any() combines multiple signals - aborts when any one aborts
	return AbortSignal.any([callerSignal, timeoutSignal]);
}

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
 * Check if response is a 401 and handle authentication failure.
 * 
 * - If a token exists: marks session as expired (shows re-auth modal)
 * - If no token exists: calls logout() to clear any stale state
 * 
 * @returns true if session expired modal was triggered, false otherwise
 */
function handleUnauthorized(response: Response): boolean {
	if (response.status === 401) {
		const authToken = get(token);
		if (authToken) {
			// Token exists but was rejected - session expired
			markSessionExpired('expired');
			return true;
		} else {
			// No token but got 401 - likely login failure or stale state
			// Clear any potential stale auth state to ensure clean UI
			logout();
			return false;
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
	/**
	 * Request timeout in milliseconds.
	 * Defaults to DEFAULT_REQUEST_TIMEOUT_MS (60 seconds).
	 * Set to 0 or Infinity to disable timeout.
	 */
	timeout?: number;
}

/**
 * Make a JSON API request with automatic auth header, timeout, and error handling.
 * 
 * By default, requests will timeout after DEFAULT_REQUEST_TIMEOUT_MS (60 seconds)
 * unless a custom timeout is specified or a caller-provided signal aborts earlier.
 */
export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
	const authToken = get(token);
	const timeoutMs = options.timeout ?? DEFAULT_REQUEST_TIMEOUT_MS;

	const headers: HeadersInit = {
		...options.headers,
	};

	if (authToken) {
		(headers as Record<string, string>)['Authorization'] = `Bearer ${authToken}`;
	}

	if (options.body && typeof options.body === 'string') {
		(headers as Record<string, string>)['Content-Type'] = 'application/json';
	}

	// Create signal with default timeout, combining with caller's signal if provided
	const signal = timeoutMs > 0 && timeoutMs < Infinity 
		? createTimeoutSignal(options.signal, timeoutMs)
		: options.signal;

	const response = await fetch(`${BASE_URL}${endpoint}`, {
		...options,
		headers,
		signal,
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
	/**
	 * Request timeout in milliseconds.
	 * Defaults to DEFAULT_REQUEST_TIMEOUT_MS (60 seconds).
	 * Set to 0 or Infinity to disable timeout.
	 */
	timeout?: number;
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

export interface BlobUrlRequestOptions {
	signal?: AbortSignal;
	/**
	 * Request timeout in milliseconds.
	 * Defaults to DEFAULT_REQUEST_TIMEOUT_MS (60 seconds).
	 * Set to 0 or Infinity to disable timeout.
	 */
	timeout?: number;
}

/**
 * Fetch a binary resource (image, file) with authentication, timeout, and return a blob URL with cleanup.
 * 
 * IMPORTANT: Blob URLs hold references to underlying data and MUST be revoked to avoid memory leaks.
 * Call `result.revoke()` when the URL is no longer needed (e.g., in onDestroy or when removing an image).
 * 
 * By default, requests will timeout after DEFAULT_REQUEST_TIMEOUT_MS (60 seconds)
 * unless a custom timeout is specified or a caller-provided signal aborts earlier.
 * 
 * @param endpoint - API endpoint to fetch
 * @param options - Optional signal for cancellation and/or custom timeout
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
export async function requestBlobUrl(
	endpoint: string, 
	options?: AbortSignal | BlobUrlRequestOptions
): Promise<BlobUrlResult | null> {
	// Support both legacy AbortSignal parameter and new options object
	const opts: BlobUrlRequestOptions = options instanceof AbortSignal 
		? { signal: options } 
		: (options ?? {});
	const timeoutMs = opts.timeout ?? DEFAULT_REQUEST_TIMEOUT_MS;
	
	const authToken = get(token);

	// Create signal with default timeout, combining with caller's signal if provided
	const signal = timeoutMs > 0 && timeoutMs < Infinity
		? createTimeoutSignal(opts.signal, timeoutMs)
		: opts.signal;

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
 * Make a FormData API request with automatic auth header, timeout, and error handling.
 * Use this for file uploads and multipart form submissions.
 * 
 * By default, requests will timeout after DEFAULT_REQUEST_TIMEOUT_MS (60 seconds)
 * unless a custom timeout is specified or a caller-provided signal aborts earlier.
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
	const timeoutMs = opts.timeout ?? DEFAULT_REQUEST_TIMEOUT_MS;
	
	const authToken = get(token);

	// Create signal with default timeout, combining with caller's signal if provided
	const signal = timeoutMs > 0 && timeoutMs < Infinity
		? createTimeoutSignal(opts.signal, timeoutMs)
		: opts.signal;

	try {
		log.debug(`FormData request to ${endpoint}`);
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			method: 'POST',
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			body: formData,
			signal,
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

