/**
 * Token refresh service
 * Handles automatic token refresh and scheduling
 */
import { get } from 'svelte/store';
import { token, tokenExpiresAt, tokenNeedsRefresh, tokenIsExpired } from '../stores/auth';
import { auth } from '../api';

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Refresh the current token
 * @returns true if refresh succeeded, false otherwise
 */
export async function refreshToken(): Promise<boolean> {
	try {
		const response = await auth.refresh();
		token.set(response.token);
		tokenExpiresAt.set(new Date(response.expires_at));
		scheduleRefresh();
		return true;
	} catch {
		return false;
	}
}

/**
 * Schedule the next token refresh
 * Refreshes at 50% of remaining lifetime, minimum 1 minute
 */
export function scheduleRefresh(): void {
	if (refreshTimer) clearTimeout(refreshTimer);

	const expires = get(tokenExpiresAt);
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
	const currentToken = get(token);
	if (!currentToken) return;

	// Check local expiry (no server call)
	if (tokenIsExpired()) {
		// Token expired locally - clear and require re-login
		token.set(null);
		tokenExpiresAt.set(null);
		return;
	}

	// Token still valid locally - schedule refresh
	// If token is actually invalid server-side, any API call will trigger 401 → refresh → retry
	scheduleRefresh();
}

