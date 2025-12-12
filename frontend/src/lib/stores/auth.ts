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

// Session expiry state
export const sessionExpired = writable<boolean>(false);

// Queue of callbacks to retry after re-auth
let pendingRequests: Array<() => void> = [];

export function markSessionExpired(retryCallback?: () => void) {
	if (retryCallback) pendingRequests.push(retryCallback);
	sessionExpired.set(true);
}

export function onReauthSuccess(newToken: string) {
	token.set(newToken);
	sessionExpired.set(false);
	// Retry all pending requests
	pendingRequests.forEach((cb) => cb());
	pendingRequests = [];
}

export function logout() {
	token.set(null);
	sessionExpired.set(false);
	pendingRequests = [];
}





