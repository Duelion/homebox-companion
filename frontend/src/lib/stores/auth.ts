/**
 * Authentication store
 */
import { writable, derived, get } from 'svelte/store';
import { browser } from '$app/environment';
import { stopRefreshTimer } from '../services/tokenRefresh';
import { authLogger as log } from '../utils/logger';

// Note: scheduleRefresh is imported dynamically in setAuthenticatedState to avoid circular dependency

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
 * Tracks whether initial auth check has completed.
 * Used to prevent race conditions between layout's initializeAuth and page-level auth checks.
 */
export const authInitialized = writable<boolean>(false);

/** Token refresh threshold in milliseconds (5 minutes) */
const TOKEN_REFRESH_THRESHOLD_MS = 5 * 60 * 1000;

/**
 * Check if token needs refresh (< 5 minutes remaining)
 */
export function tokenNeedsRefresh(): boolean {
	const expires = get(tokenExpiresAt);
	if (!expires) return false;
	const remaining = expires.getTime() - Date.now();
	return remaining < TOKEN_REFRESH_THRESHOLD_MS;
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
	log.info('Session expired, showing re-auth modal');
	sessionExpired.set(true);
}

/**
 * Set authenticated state atomically with all required side effects.
 * This is the canonical way to update auth state - use this instead of
 * manually setting token/expiry/scheduling refresh.
 * 
 * @param newToken - The new auth token
 * @param expiresAt - The token expiration date
 */
export function setAuthenticatedState(newToken: string, expiresAt: Date): void {
	log.debug('Setting authenticated state, expires:', expiresAt.toISOString());
	token.set(newToken);
	tokenExpiresAt.set(expiresAt);
	sessionExpired.set(false);

	// Import scheduleRefresh dynamically to avoid circular dependency
	import('../services/tokenRefresh').then(({ scheduleRefresh }) => {
		scheduleRefresh();
	});
}

/**
 * Called after successful re-authentication
 * @param newToken - The new auth token
 * @param expiresAt - The token expiration date
 */
export function onReauthSuccess(newToken: string, expiresAt: Date): void {
	setAuthenticatedState(newToken, expiresAt);
}

/**
 * Logout and clear all auth state
 */
export function logout(): void {
	log.info('User logout');
	stopRefreshTimer();
	token.set(null);
	tokenExpiresAt.set(null);
	sessionExpired.set(false);
}





