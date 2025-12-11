/**
 * Base API client with error handling and authentication
 */

import { get } from 'svelte/store';
import { token, markSessionExpired } from '../stores/auth';

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

	return response.json();
}

export interface FormDataRequestOptions {
	signal?: AbortSignal;
	errorMessage?: string;
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
		console.log(`[API] Sending FormData request to ${endpoint}`);
		const response = await fetch(`${BASE_URL}${endpoint}`, {
			method: 'POST',
			headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
			body: formData,
			signal: opts.signal,
		});

		console.log(`[API] Response from ${endpoint}: ${response.status} ${response.statusText}`);

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
	} catch (error) {
		// Log network errors before re-throwing
		if (error instanceof ApiError) {
			// Already handled above, just re-throw
			throw error;
		}
		console.error(`[API] Network error for ${endpoint}:`, error);
		throw error;
	}
}

