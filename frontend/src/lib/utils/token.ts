/**
 * Token validation utilities
 */

import { get } from 'svelte/store';
import { token, markSessionExpired } from '../stores/auth';

/**
 * Check if the current auth token exists locally.
 * If no token exists, triggers the session expired modal.
 * 
 * Note: This does NOT validate against the server. If the token is invalid,
 * any subsequent API call will trigger a 401 → automatic refresh → retry flow.
 * 
 * @returns true if token exists locally, false if no token
 */
export async function checkAuth(): Promise<boolean> {
	const currentToken = get(token);
	
	// No token means not authenticated
	if (!currentToken) {
		markSessionExpired();
		return false;
	}
	
	return true;
}

