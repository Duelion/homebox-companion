/**
 * Token validation utilities
 */

import { get } from 'svelte/store';
import { token, markSessionExpired } from '../stores/auth';
import { auth } from '../api/auth';
import { ApiError } from '../api/client';
import { createLogger } from './logger';

const log = createLogger({ prefix: 'Auth' });

/**
 * Check if the current auth token is valid by validating with the server.
 * If invalid/expired, triggers the session expired modal.
 * @returns true if token is valid, false if expired/invalid
 */
export async function checkAuth(): Promise<boolean> {
	const currentToken = get(token);
	
	// No token means not authenticated
	if (!currentToken) {
		markSessionExpired();
		return false;
	}
	
	try {
		// Validate token against the server
		const response = await auth.validate();
		return response.valid;
	} catch (error) {
		// 401 error means token is invalid/expired
		if (error instanceof ApiError && error.status === 401) {
			// markSessionExpired() is already called by the API client's handleUnauthorized
			return false;
		}
		
		// Other errors (network issues, 5xx, etc.) - treat as invalid to avoid
		// sending users to protected routes with unverified credentials.
		// This prevents confusing loops and stale token usage.
		log.warn('Token validation failed with unexpected error:', error);
		markSessionExpired();
		return false;
	}
}

