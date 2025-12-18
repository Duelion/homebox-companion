/**
 * Authentication store
 */
import { writable, derived, get } from 'svelte/store';
import { browser } from '$app/environment';

// Storage keys
const TOKEN_KEY = 'hbc_token';
const EXPIRES_KEY = 'hbc_token_expires';

// Load from localStorage
const storedToken = browser ? localStorage.getItem(TOKEN_KEY) : null;
const storedExpires = browser ? localStorage.getItem(EXPIRES_KEY) : null;

export const token = writable<string | null>(storedToken);
export const tokenExpiresAt = writable<Date | null>(
	storedExpires ? new Date(storedExpires) : null
);

// Persist token to localStorage with proper HMR cleanup
let tokenUnsubscribe: (() => void) | undefined;
let expiresUnsubscribe: (() => void) | undefined;

if (browser) {
	// Clean up any existing subscriptions (handles HMR)
	tokenUnsubscribe?.();
	expiresUnsubscribe?.();

	tokenUnsubscribe = token.subscribe((value) => {
		if (value) {
			localStorage.setItem(TOKEN_KEY, value);
		} else {
			localStorage.removeItem(TOKEN_KEY);
		}
	});

	expiresUnsubscribe = tokenExpiresAt.subscribe((value) => {
		if (value) {
			localStorage.setItem(EXPIRES_KEY, value.toISOString());
		} else {
			localStorage.removeItem(EXPIRES_KEY);
		}
	});
}

// Clean up subscriptions during Vite HMR
if (import.meta.hot) {
	import.meta.hot.dispose(() => {
		tokenUnsubscribe?.();
		expiresUnsubscribe?.();
	});
}

export const isAuthenticated = derived(token, ($token) => !!$token);

/**
 * Check if token needs refresh (< 5 minutes remaining)
 */
export function tokenNeedsRefresh(): boolean {
	const expires = get(tokenExpiresAt);
	if (!expires) return false;
	const remaining = expires.getTime() - Date.now();
	return remaining < 5 * 60 * 1000; // < 5 minutes
}

/**
 * Check if token is expired
 */
export function tokenIsExpired(): boolean {
	const expires = get(tokenExpiresAt);
	if (!expires) return true;
	return expires.getTime() < Date.now();
}

// Session expiry state
export const sessionExpired = writable<boolean>(false);

/**
 * Mark the session as expired and show re-auth modal
 */
export function markSessionExpired(): void {
	sessionExpired.set(true);
}

/**
 * Called after successful re-authentication
 */
export function onReauthSuccess(newToken: string): void {
	token.set(newToken);
	sessionExpired.set(false);
}

/**
 * Logout and clear all auth state
 */
export function logout(): void {
	token.set(null);
	tokenExpiresAt.set(null);
	sessionExpired.set(false);
}





