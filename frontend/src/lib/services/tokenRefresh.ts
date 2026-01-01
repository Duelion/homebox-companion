/**
 * Token refresh service
 * Handles automatic token refresh and scheduling
 */
import { authStore } from '../stores/auth.svelte';
import { auth } from '../api';
import { authLogger as log } from '../utils/logger';

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Promise that resolves when auth initialization completes.
 * Used by components to await initialization instead of polling.
 */
let initPromise: Promise<void> | null = null;
let initResolve: (() => void) | null = null;

/**
 * Get a promise that resolves when auth initialization completes.
 * If already initialized, returns an immediately resolved promise.
 * @returns Promise that resolves when init is done
 */
export function getInitPromise(): Promise<void> {
	if (authStore.initialized) {
		return Promise.resolve();
	}
	if (!initPromise) {
		initPromise = new Promise((resolve) => {
			initResolve = resolve;
		});
	}
	return initPromise;
}

/**
 * Refresh the current token
 * @returns true if refresh succeeded, false otherwise
 */
export async function refreshToken(): Promise<boolean> {
	try {
		const response = await auth.refresh();
		// Use setAuthenticatedState to ensure all state updates happen atomically
		authStore.setAuthenticatedState(response.token, new Date(response.expires_at));
		return true;
	} catch (error) {
		// Log error for debugging (previously swallowed silently)
		log.error('Token refresh failed:', error);
		return false;
	}
}

/**
 * Schedule the next token refresh
 * Refreshes at 50% of remaining lifetime, minimum 1 minute
 */
export function scheduleRefresh(): void {
	if (refreshTimer) clearTimeout(refreshTimer);

	const expires = authStore.expiresAt;
	if (!expires) return;

	// Refresh at 50% of remaining lifetime, minimum 1 minute
	const remaining = expires.getTime() - Date.now();
	const delay = Math.max(remaining / 2, 60_000);

	refreshTimer = setTimeout(async () => {
		await refreshToken();
	}, delay);
}

/**
 * Stop the refresh timer
 */
export function stopRefreshTimer(): void {
	if (refreshTimer) {
		clearTimeout(refreshTimer);
		refreshTimer = null;
	}
}

/**
 * Initialize authentication on app load
 * Checks local token expiry and schedules refresh if valid
 */
export async function initializeAuth(): Promise<void> {
	try {
		const currentToken = authStore.token;
		if (!currentToken) {
			return;
		}

		// Check local expiry (no server call)
		if (authStore.tokenIsExpired()) {
			// Token expired locally - clear and require re-login
			authStore.logout();
			return;
		}

		// If token needs refresh (< 5 minutes remaining), refresh immediately
		// Otherwise, just schedule the next refresh
		if (authStore.tokenNeedsRefresh()) {
			const refreshed = await refreshToken();
			if (!refreshed) {
				// Refresh failed - token might be invalid, clear it
				authStore.logout();
			}
			// scheduleRefresh() already called by refreshToken() via setAuthenticatedState
		} else {
			// Token still has enough time - schedule refresh for later
			scheduleRefresh();
		}
	} finally {
		// Mark auth as initialized regardless of outcome
		authStore.setInitialized(true);
		// Resolve the init promise for any waiters
		if (initResolve) {
			initResolve();
			initResolve = null;
		}
	}
}
