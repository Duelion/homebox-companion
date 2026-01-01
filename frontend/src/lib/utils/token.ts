/**
 * Token validation utilities
 */

import { authStore } from '../stores/auth.svelte';

/**
 * Check if an auth token exists locally.
 *
 * This is a SYNCHRONOUS check - it does NOT validate against the server.
 * If the token is invalid/expired, any subsequent API call will trigger
 * a 401 → automatic refresh → retry flow.
 *
 * @returns true if token exists locally, false if no token
 */
export function hasToken(): boolean {
	return !!authStore.token;
}

/**
 * @deprecated Use hasToken() instead. This alias exists for backward compatibility.
 */
export const checkAuth = hasToken;
