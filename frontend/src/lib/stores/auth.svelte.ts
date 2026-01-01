/**
 * Authentication Store - Svelte 5 Class-based State
 *
 * Manages authentication state using Svelte 5 runes for fine-grained reactivity.
 */
import { browser } from '$app/environment';
import { stopRefreshTimer } from '../services/tokenRefresh';
import { authLogger as log } from '../utils/logger';

// Note: scheduleRefresh is imported dynamically in setAuthenticatedState to avoid circular dependency

// =============================================================================
// CONSTANTS
// =============================================================================

const TOKEN_KEY = 'hbc_token';
const EXPIRES_KEY = 'hbc_token_expires';

/** Token refresh threshold in milliseconds (5 minutes) */
const TOKEN_REFRESH_THRESHOLD_MS = 5 * 60 * 1000;

// =============================================================================
// INITIAL STATE FROM STORAGE
// =============================================================================

const storedToken = browser ? localStorage.getItem(TOKEN_KEY) : null;
const storedExpires = browser ? localStorage.getItem(EXPIRES_KEY) : null;

// =============================================================================
// AUTH STORE CLASS
// =============================================================================

class AuthStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Auth token */
	private _token = $state<string | null>(storedToken);

	/** Token expiration date */
	private _expiresAt = $state<Date | null>(storedExpires ? new Date(storedExpires) : null);

	/** Whether initial auth check has completed */
	private _initialized = $state(false);

	/** Whether the session has expired (shows re-auth modal) */
	private _sessionExpired = $state(false);

	/** Whether user is authenticated - derived from token presence */
	private _isAuthenticated = $derived.by(() => !!this._token);

	// =========================================================================
	// GETTERS (read-only access to state)
	// =========================================================================

	/** Get the auth token */
	get token(): string | null {
		return this._token;
	}

	/** Get the token expiration date */
	get expiresAt(): Date | null {
		return this._expiresAt;
	}

	/** Check if user is authenticated (reactive via $derived) */
	get isAuthenticated(): boolean {
		return this._isAuthenticated;
	}

	/** Check if auth has been initialized */
	get initialized(): boolean {
		return this._initialized;
	}

	/** Check if session has expired */
	get sessionExpired(): boolean {
		return this._sessionExpired;
	}

	// =========================================================================
	// SETTERS (controlled mutations)
	// =========================================================================

	/** Mark auth as initialized */
	setInitialized(value: boolean): void {
		this._initialized = value;
	}

	/** Mark session as expired */
	setSessionExpired(value: boolean): void {
		this._sessionExpired = value;
	}

	// =========================================================================
	// AUTH METHODS
	// =========================================================================

	/**
	 * Check if token needs refresh (< 5 minutes remaining)
	 */
	tokenNeedsRefresh(): boolean {
		if (!this._expiresAt) return false;
		const remaining = this._expiresAt.getTime() - Date.now();
		return remaining < TOKEN_REFRESH_THRESHOLD_MS;
	}

	/**
	 * Check if token is expired
	 */
	tokenIsExpired(): boolean {
		if (!this._expiresAt) return true;
		return this._expiresAt.getTime() < Date.now();
	}

	/**
	 * Mark the session as expired and show re-auth modal
	 */
	markSessionExpired(): void {
		log.info('Session expired, showing re-auth modal');
		this._sessionExpired = true;
	}

	/**
	 * Set authenticated state atomically with all required side effects.
	 * This is the canonical way to update auth state.
	 */
	setAuthenticatedState(newToken: string, expiresAt: Date): void {
		log.debug('Setting authenticated state, expires:', expiresAt.toISOString());
		this._token = newToken;
		this._expiresAt = expiresAt;
		this._sessionExpired = false;

		// Persist to localStorage
		if (browser) {
			localStorage.setItem(TOKEN_KEY, newToken);
			localStorage.setItem(EXPIRES_KEY, expiresAt.toISOString());
		}

		// Schedule token refresh
		this.scheduleRefresh();
	}

	/**
	 * Schedule token refresh via dynamic import.
	 * Dynamic import avoids circular dependency with tokenRefresh.ts.
	 */
	private async scheduleRefresh(): Promise<void> {
		try {
			const { scheduleRefresh } = await import('../services/tokenRefresh');
			scheduleRefresh();
		} catch (err) {
			// Dynamic imports rarely fail; log and continue (session may expire unexpectedly)
			log.error('Failed to schedule token refresh - session may expire unexpectedly:', err);
		}
	}

	/**
	 * Logout and clear all auth state.
	 * Note: Store cleanup uses dynamic imports to avoid circular dependencies.
	 * Cleanup failures are logged but do not block logout completion.
	 *
	 * @remarks This method is intentionally synchronous (returns void, not Promise).
	 * Callers should not need to await logout completion. Related store cleanup
	 * happens asynchronously in the background via cleanupRelatedStores().
	 */
	logout(): void {
		log.info('User logout');
		stopRefreshTimer();
		this._token = null;
		this._expiresAt = null;
		this._sessionExpired = false;

		// Clear from localStorage
		if (browser) {
			localStorage.removeItem(TOKEN_KEY);
			localStorage.removeItem(EXPIRES_KEY);
		}

		// Clear related stores (non-blocking, errors logged)
		// Uses Promise.allSettled to ensure all cleanup attempts run
		this.cleanupRelatedStores();
	}

	/**
	 * Clear related stores on logout. Non-critical failures are logged.
	 * Uses Promise.allSettled to run all cleanup in parallel.
	 */
	private async cleanupRelatedStores(): Promise<void> {
		const cleanupTasks = [
			import('./locations.svelte.ts')
				.then(({ locationStore }) => locationStore.clear())
				.catch((err) => log.warn('Failed to clear location state:', err)),
			import('./labels.svelte.ts')
				.then(({ clearLabelsCache }) => clearLabelsCache())
				.catch((err) => log.warn('Failed to clear labels cache:', err)),
		];
		await Promise.allSettled(cleanupTasks);
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const authStore = new AuthStore();

// =============================================================================
// FUNCTION EXPORTS (backward compatibility)
// =============================================================================

// These re-export methods as standalone functions for backward compatibility.
// Prefer using authStore.method() directly in new code.

export const tokenNeedsRefresh = () => authStore.tokenNeedsRefresh();
export const tokenIsExpired = () => authStore.tokenIsExpired();
export const markSessionExpired = () => authStore.markSessionExpired();
export const setAuthenticatedState = (token: string, expiresAt: Date) =>
	authStore.setAuthenticatedState(token, expiresAt);
export const logout = () => authStore.logout();
