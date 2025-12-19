/**
 * Token validation utilities
 */

import { get } from 'svelte/store';
import { token, markSessionExpired } from '../stores/auth';

/**
 * Check if the current auth token exists locally.
 * 
 * Note: This does NOT validate against the server. If the token is invalid,
 * any subsequent API call will trigger a 401 → automatic refresh → retry flow.
 * 
 * The caller should handle missing tokens appropriately (e.g., show error, redirect).
 * The session expired modal is automatically triggered by 401 responses from the API.
 * 
 * @returns true if token exists locally, false if no token
 */
export function checkAuth(): boolean {
	const currentToken = get(token);
	return !!currentToken;
}

