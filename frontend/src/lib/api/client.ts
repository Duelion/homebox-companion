/**
 * Base API client with error handling and authentication
 */

import { authStore } from '../stores/auth.svelte';
import { abortSignalAny, abortSignalTimeout } from '../utils/abortSignal';
import { apiLogger as log } from '../utils/logger';
import { refreshToken } from '../services/tokenRefresh';

const BASE_URL = '/api';

/**
 * Default request timeout in milliseconds.
 * Applies when no AbortSignal is provided by the caller.
 */
export const DEFAULT_REQUEST_TIMEOUT_MS = 60_000;

/**
 * WeakSet to track AbortSignals created for timeout purposes.
 * This allows us to reliably distinguish timeout aborts from user-initiated cancellations
 * without relying on browser-specific error messages.
 */
const timeoutSignals = new WeakSet<AbortSignal>();

/**
 * Create a combined AbortSignal that aborts when either:
 * - The caller's signal aborts (if provided)
 * - The default timeout elapses
 *
 * @param callerSignal - Optional signal from the caller
 * @param timeoutMs - Timeout in milliseconds
 * @returns AbortSignal that respects both conditions
 */
function createTimeoutSignal(
	callerSignal?: AbortSignal,
	timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS
): AbortSignal {
	const timeoutSignal = abortSignalTimeout(timeoutMs);
	// Track this signal as a timeout signal for reliable detection later
	timeoutSignals.add(timeoutSignal);

	if (!callerSignal) {
		return timeoutSignal;
	}

	// Combine caller signal with timeout signal
	// Uses abortSignalAny for browser compatibility (AbortSignal.any not in older Safari/Chrome)
	const combinedSignal = abortSignalAny([callerSignal, timeoutSignal]);
	// Mark the combined signal as timeout-capable
	timeoutSignals.add(combinedSignal);
	return combinedSignal;
}

/**
 * API Error class with status and data.
 * Thrown when the server returns a non-OK HTTP response.
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
 * Network Error class for connection-level failures.
 * Thrown when fetch fails due to network issues, DNS failures, or timeouts.
 *
 * NOTE: User-initiated abort errors (when the user cancels a request) are NOT
 * wrapped in NetworkError. They are thrown as raw AbortError to preserve the
 * existing cancellation detection pattern (checking error.name === 'AbortError').
 */
export class NetworkError extends Error {
	/** The original error that caused this network failure */
	cause: Error;
	/** Whether this was a timeout error */
	isTimeout: boolean;

	constructor(message: string, cause: Error, options: { isTimeout?: boolean } = {}) {
		super(message);
		this.cause = cause;
		this.isTimeout = options.isTimeout ?? false;
		this.name = 'NetworkError';
	}
}

// =============================================================================
// TOKEN REFRESH DEDUPLICATION (Module-level Singleton)
// =============================================================================
//
// This module-scoped promise implements a singleton pattern to deduplicate
// concurrent token refresh attempts. When multiple API requests receive 401s
// simultaneously, only one refresh is performed and the result is shared.
//
// This is intentional global state for the SPA lifecycle.
//
// Testing note: This state persists across test cases unless the module is
// reloaded. Consider this when writing integration tests.
// =============================================================================

let refreshPromise: Promise<boolean> | null = null;

/**
 * Attempt to refresh the token once, preventing concurrent refresh attempts.
 * Uses a single promise reference with .finally() cleanup for atomic state management.
 */
async function attemptRefreshOnce(): Promise<boolean> {
	// If a refresh is already in progress, return the existing promise
	if (refreshPromise) {
		return refreshPromise;
	}

	// Start a new refresh and store the promise
	// Use .finally() to ensure cleanup happens atomically after the promise settles
	refreshPromise = refreshToken().finally(() => {
		refreshPromise = null;
	});

	return refreshPromise;
}

/**
 * Handle 401 response with automatic token refresh and retry.
 *
 * NOTE: This function reads authStore.token imperatively (not reactively).
 * This is intentional - we need the current value at call time, not a
 * reactive subscription. Changes to the token won't trigger re-execution.
 *
 * - If no token exists: returns false (user not logged in)
 * - If token exists: attempts refresh and signals whether to retry
 * - If refresh fails: shows re-auth modal
 *
 * @param response - The 401 response
 * @returns true if request should be retried with new token, false otherwise
 */
async function handleUnauthorized(response: Response): Promise<boolean> {
	if (response.status !== 401) {
		return false;
	}

	if (!authStore.token) {
		// No token - user isn't logged in, nothing to do
		return false;
	}

	// Token exists but was rejected - try to refresh
	const refreshSucceeded = await attemptRefreshOnce();
	if (!refreshSucceeded) {
		// Refresh failed - show re-auth modal
		authStore.markSessionExpired();
		return false;
	}

	// Refresh succeeded - caller should retry the request
	return true;
}

/**
 * Wraps a fetch error into a typed NetworkError.
 * Handles timeout errors and generic network failures.
 *
 * NOTE: User-initiated abort errors (AbortError without timeout) are re-thrown
 * directly to preserve the existing cancellation detection pattern used
 * throughout the codebase (checking error.name === 'AbortError').
 *
 * @param error - The error from a failed fetch call
 * @param endpoint - The endpoint that was being fetched (for error message)
 * @param signal - The AbortSignal used in the request (to check if it was a timeout signal)
 * @returns A NetworkError with appropriate type flags set
 * @throws The original error if it's a user-initiated abort
 */
function wrapFetchError(error: unknown, endpoint: string, signal?: AbortSignal): NetworkError {
	if (error instanceof Error) {
		// Check for abort errors (user cancellation or timeout)
		if (error.name === 'AbortError') {
			// Check if this was a timeout abort by seeing if the signal is tracked
			// in our timeoutSignals WeakSet (more reliable than checking error message)
			const isTimeout = signal ? timeoutSignals.has(signal) : false;
			if (isTimeout) {
				return new NetworkError(`Request to ${endpoint} timed out`, error, { isTimeout: true });
			}
			// User-initiated abort - re-throw directly to preserve existing
			// cancellation detection pattern (error.name === 'AbortError')
			throw error;
		}

		// Check for timeout explicitly (some implementations use TimeoutError)
		if (error.name === 'TimeoutError') {
			return new NetworkError(`Request to ${endpoint} timed out`, error, { isTimeout: true });
		}

		// Generic network error (connection refused, DNS failure, etc.)
		return new NetworkError(`Network error while fetching ${endpoint}: ${error.message}`, error);
	}

	// Unknown error type, wrap in a generic Error first
	const wrappedError = new Error(String(error));
	return new NetworkError(`Network error while fetching ${endpoint}`, wrappedError);
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
	/**
	 * Skip automatic 401 handling and token refresh retry.
	 * Used internally for the refresh endpoint to avoid circular retry loops.
	 * When true, a 401 response will immediately throw an ApiError.
	 */
	skipAuthRetry?: boolean;
}

/**
 * Make a JSON API request with automatic auth header, timeout, and error handling.
 * Automatically retries once if token refresh succeeds after a 401.
 *
 * By default, requests will timeout after DEFAULT_REQUEST_TIMEOUT_MS (60 seconds)
 * unless a custom timeout is specified or a caller-provided signal aborts earlier.
 *
 * @throws {ApiError} When the server returns a non-OK HTTP response
 * @throws {NetworkError} When a network-level error occurs (connection, DNS, timeout)
 */
export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
	const timeoutMs = options.timeout ?? DEFAULT_REQUEST_TIMEOUT_MS;

	// Helper to build headers with current token
	const buildHeaders = (): HeadersInit => {
		const authToken = authStore.token;
		const headers: HeadersInit = {
			...options.headers,
		};

		if (authToken) {
			(headers as Record<string, string>)['Authorization'] = `Bearer ${authToken}`;
		}

		if (options.body && typeof options.body === 'string') {
			(headers as Record<string, string>)['Content-Type'] = 'application/json';
		}

		return headers;
	};

	// Create signal with default timeout, combining with caller's signal if provided
	const signal =
		timeoutMs > 0 && timeoutMs < Infinity
			? createTimeoutSignal(options.signal, timeoutMs)
			: options.signal;

	// First attempt
	let response: Response;
	try {
		response = await fetch(`${BASE_URL}${endpoint}`, {
			...options,
			headers: buildHeaders(),
			signal,
		});
	} catch (error) {
		const networkError = wrapFetchError(error, endpoint, signal);
		log.error(`Network error for ${endpoint}`, networkError);
		throw networkError;
	}

	// Handle 401 with automatic retry after refresh
	// Skip for refresh endpoint itself to avoid circular retry loops
	if (!response.ok && response.status === 401 && !options.skipAuthRetry) {
		const shouldRetry = await handleUnauthorized(response);
		if (shouldRetry) {
			// Token was refreshed - retry the request with new token
			// Create a fresh timeout signal for the retry (don't reuse the original)
			const retrySignal =
				timeoutMs > 0 && timeoutMs < Infinity
					? createTimeoutSignal(options.signal, timeoutMs)
					: options.signal;

			log.debug(`Retrying ${endpoint} after token refresh`);
			try {
				response = await fetch(`${BASE_URL}${endpoint}`, {
					...options,
					headers: buildHeaders(),
					signal: retrySignal,
				});
			} catch (error) {
				const networkError = wrapFetchError(error, endpoint, retrySignal);
				log.error(`Network error on retry for ${endpoint}`, networkError);
				throw networkError;
			}
		}
	}

	// Handle other errors
	if (!response.ok) {
		// Read body as text first, then try to parse as JSON.
		// This prevents "Body has already been consumed" errors when json() fails.
		const text = await response.text();
		let errorData: unknown;
		try {
			errorData = text ? JSON.parse(text) : undefined;
		} catch {
			errorData = text;
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
	/**
	 * Additional headers to include in the request.
	 * Authorization header is automatically added if a token exists.
	 */
	headers?: Record<string, string>;
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
 * Automatically retries once if token refresh succeeds after a 401.
 *
 * IMPORTANT: Blob URLs hold references to underlying data and MUST be revoked to avoid memory leaks.
 * Call `result.revoke()` when the URL is no longer needed (e.g., in onDestroy or when removing an image).
 *
 * By default, requests will timeout after DEFAULT_REQUEST_TIMEOUT_MS (60 seconds)
 * unless a custom timeout is specified or a caller-provided signal aborts earlier.
 *
 * @param endpoint - API endpoint to fetch
 * @param options - Optional signal for cancellation and/or custom timeout
 * @returns BlobUrlResult with url and revoke function
 * @throws {ApiError} When the server returns a non-OK HTTP response
 * @throws {NetworkError} When a network-level error occurs (connection, DNS, timeout)
 *
 * @example
 * ```typescript
 * try {
 *   const result = await requestBlobUrl('/items/123/thumbnail');
 *   img.src = result.url;
 *   // Later, when done with the image:
 *   result.revoke();
 * } catch (error) {
 *   if (error instanceof Error && error.name === 'AbortError') {
 *     // Request was cancelled by user, handle gracefully
 *   } else if (error instanceof ApiError && error.status === 404) {
 *     // Resource not found, show placeholder
 *   } else if (error instanceof NetworkError) {
 *     // Network error (connection, DNS, timeout)
 *     if (error.isTimeout) {
 *       // Handle timeout specifically
 *     }
 *   }
 * }
 * ```
 */
export async function requestBlobUrl(
	endpoint: string,
	options?: AbortSignal | BlobUrlRequestOptions
): Promise<BlobUrlResult> {
	// Support both legacy AbortSignal parameter and new options object
	const opts: BlobUrlRequestOptions =
		options instanceof AbortSignal ? { signal: options } : (options ?? {});
	const timeoutMs = opts.timeout ?? DEFAULT_REQUEST_TIMEOUT_MS;

	// Helper to build headers with current token
	const buildHeaders = (): HeadersInit => {
		const authToken = authStore.token;
		return authToken ? { Authorization: `Bearer ${authToken}` } : {};
	};

	// Create signal with default timeout, combining with caller's signal if provided
	const signal =
		timeoutMs > 0 && timeoutMs < Infinity
			? createTimeoutSignal(opts.signal, timeoutMs)
			: opts.signal;

	// First attempt
	let response: Response;
	try {
		response = await fetch(`${BASE_URL}${endpoint}`, {
			headers: buildHeaders(),
			signal,
		});
	} catch (error) {
		const networkError = wrapFetchError(error, endpoint, signal);
		log.debug(`Blob request network error for ${endpoint}:`, networkError.message);
		throw networkError;
	}

	// Handle 401 with automatic retry after refresh
	if (!response.ok && response.status === 401) {
		const shouldRetry = await handleUnauthorized(response);
		if (shouldRetry) {
			// Token was refreshed - retry the request with new token
			// Create a fresh timeout signal for the retry (don't reuse the original)
			const retrySignal =
				timeoutMs > 0 && timeoutMs < Infinity
					? createTimeoutSignal(opts.signal, timeoutMs)
					: opts.signal;

			log.debug(`Retrying blob request ${endpoint} after token refresh`);
			try {
				response = await fetch(`${BASE_URL}${endpoint}`, {
					headers: buildHeaders(),
					signal: retrySignal,
				});
			} catch (error) {
				const networkError = wrapFetchError(error, endpoint, retrySignal);
				log.debug(`Blob request network error on retry for ${endpoint}:`, networkError.message);
				throw networkError;
			}
		}
	}

	// Handle other errors
	if (!response.ok) {
		log.debug(`Blob request failed for ${endpoint}: ${response.status}`);
		throw new ApiError(response.status, `Blob request failed with status ${response.status}`);
	}

	const blob = await response.blob();
	const url = URL.createObjectURL(blob);

	return {
		url,
		revoke: () => URL.revokeObjectURL(url),
	};
}

/**
 * Make a FormData API request with automatic auth header, timeout, and error handling.
 * Automatically retries once if token refresh succeeds after a 401.
 * Use this for file uploads and multipart form submissions.
 *
 * By default, requests will timeout after DEFAULT_REQUEST_TIMEOUT_MS (60 seconds)
 * unless a custom timeout is specified or a caller-provided signal aborts earlier.
 *
 * @throws {ApiError} When the server returns a non-OK HTTP response
 * @throws {NetworkError} When a network-level error occurs (connection, DNS, timeout)
 */
export async function requestFormData<T>(
	endpoint: string,
	formData: FormData,
	options: FormDataRequestOptions = {}
): Promise<T> {
	const errorMessage = options.errorMessage ?? 'Request failed';
	const timeoutMs = options.timeout ?? DEFAULT_REQUEST_TIMEOUT_MS;

	// Helper to build headers with current token and any additional headers
	const buildHeaders = (): HeadersInit => {
		const authToken = authStore.token;
		const headers: Record<string, string> = {};

		if (authToken) {
			headers['Authorization'] = `Bearer ${authToken}`;
		}

		// Merge any additional headers from options
		if (options.headers) {
			Object.assign(headers, options.headers);
		}

		return headers;
	};

	// Create signal with default timeout, combining with caller's signal if provided
	const signal =
		timeoutMs > 0 && timeoutMs < Infinity
			? createTimeoutSignal(options.signal, timeoutMs)
			: options.signal;

	// First attempt
	let response: Response;
	try {
		log.debug(`FormData request to ${endpoint}`);
		response = await fetch(`${BASE_URL}${endpoint}`, {
			method: 'POST',
			headers: buildHeaders(),
			body: formData,
			signal,
		});
	} catch (error) {
		const networkError = wrapFetchError(error, endpoint, signal);
		log.error(`Network error for ${endpoint}`, networkError);
		throw networkError;
	}

	log.debug(`Response from ${endpoint}:`, response.status, response.statusText);

	// Handle 401 with automatic retry after refresh
	if (!response.ok && response.status === 401) {
		const shouldRetry = await handleUnauthorized(response);
		if (shouldRetry) {
			// Token was refreshed - retry the request with new token
			// Create a fresh timeout signal for the retry (don't reuse the original)
			const retrySignal =
				timeoutMs > 0 && timeoutMs < Infinity
					? createTimeoutSignal(options.signal, timeoutMs)
					: options.signal;

			log.debug(`Retrying FormData request ${endpoint} after token refresh`);
			try {
				response = await fetch(`${BASE_URL}${endpoint}`, {
					method: 'POST',
					headers: buildHeaders(),
					body: formData,
					signal: retrySignal,
				});
				log.debug(`Retry response from ${endpoint}:`, response.status, response.statusText);
			} catch (error) {
				const networkError = wrapFetchError(error, endpoint, retrySignal);
				log.error(`Network error on retry for ${endpoint}`, networkError);
				throw networkError;
			}
		}
	}

	// Handle other errors
	if (!response.ok) {
		// Read body as text first, then try to parse as JSON.
		// This prevents "Body has already been consumed" errors when json() fails.
		const text = await response.text();
		let errorData: unknown;
		try {
			errorData = text ? JSON.parse(text) : undefined;
		} catch {
			errorData = text;
		}
		throw new ApiError(
			response.status,
			typeof errorData === 'object' && errorData !== null && 'detail' in errorData
				? String((errorData as { detail: unknown }).detail)
				: errorMessage,
			errorData
		);
	}

	return parseResponseBody<T>(response);
}
