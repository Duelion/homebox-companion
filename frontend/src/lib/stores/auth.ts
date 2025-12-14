/**
 * Authentication store
 */
import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

// Token stored in sessionStorage
const storedToken = browser ? sessionStorage.getItem('hbc_token') : null;

export const token = writable<string | null>(storedToken);

// Persist token to sessionStorage with proper HMR cleanup
let tokenUnsubscribe: (() => void) | undefined;

if (browser) {
	// Clean up any existing subscription (handles HMR)
	tokenUnsubscribe?.();

	tokenUnsubscribe = token.subscribe((value) => {
		if (value) {
			sessionStorage.setItem('hbc_token', value);
		} else {
			sessionStorage.removeItem('hbc_token');
		}
	});
}

// Clean up subscription during Vite HMR
if (import.meta.hot) {
	import.meta.hot.dispose(() => {
		tokenUnsubscribe?.();
	});
}

export const isAuthenticated = derived(token, ($token) => !!$token);

/**
 * Reason for session expiry - helps show appropriate UI feedback
 */
export type SessionExpiredReason = 
	| 'expired'      // Token expired (401 from server)
	| 'network'      // Network error (couldn't reach server)
	| 'server_error' // Server error (5xx response)
	| 'unknown';     // Unknown error

// Session expiry state
export const sessionExpired = writable<boolean>(false);

// Reason for session expiry (for differentiated UI feedback)
export const sessionExpiredReason = writable<SessionExpiredReason | null>(null);

// Queue of callbacks to retry after re-auth
let pendingRequests: Array<() => void> = [];

/**
 * Clear all pending retry callbacks.
 * Call this when the session expired modal is dismissed without re-auth,
 * or during cleanup to prevent memory leaks.
 */
export function clearPendingRequests(): void {
	pendingRequests = [];
}

// Clean up pending requests during Vite HMR
if (import.meta.hot) {
	import.meta.hot.dispose(() => {
		clearPendingRequests();
	});
}

export function markSessionExpired(reason: SessionExpiredReason = 'expired', retryCallback?: () => void) {
	if (retryCallback) pendingRequests.push(retryCallback);
	sessionExpiredReason.set(reason);
	sessionExpired.set(true);
}

export function onReauthSuccess(newToken: string) {
	token.set(newToken);
	sessionExpired.set(false);
	sessionExpiredReason.set(null);
	// Retry all pending requests
	const callbacks = pendingRequests;
	pendingRequests = [];
	callbacks.forEach((cb) => cb());
}

/**
 * Dismiss the session expired modal without re-authenticating.
 * Clears any pending retry callbacks to prevent memory leaks.
 */
export function dismissSessionExpired(): void {
	sessionExpired.set(false);
	sessionExpiredReason.set(null);
	clearPendingRequests();
}

export function logout() {
	token.set(null);
	sessionExpired.set(false);
	sessionExpiredReason.set(null);
	clearPendingRequests();
}





