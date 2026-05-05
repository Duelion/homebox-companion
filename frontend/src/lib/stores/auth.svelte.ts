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
const EMAIL_KEY = 'hbc_user_email';

/** Token refresh threshold in milliseconds (5 minutes) */
const TOKEN_REFRESH_THRESHOLD_MS = 5 * 60 * 1000;

// =============================================================================
// INITIAL STATE FROM STORAGE
// =============================================================================

const storedToken = browser ? localStorage.getItem(TOKEN_KEY) : null;
const storedExpires = browser ? localStorage.getItem(EXPIRES_KEY) : null;
const storedEmail = browser ? localStorage.getItem(EMAIL_KEY) : null;

// Diagnostic: log what we found in localStorage on module load
if (browser) {
	log.debug(
		`[AUTH INIT] localStorage state: token=${storedToken ? `present (${storedToken.length} chars)` : 'MISSING'}, ` +
			`expires=${storedExpires ?? 'MISSING'}, email=${storedEmail ?? 'MISSING'}`
	);
	if (storedExpires) {
		const expiresDate = new Date(storedExpires);
		const remainingMs = expiresDate.getTime() - Date.now();
		log.debug(
			`[AUTH INIT] Token expires: ${expiresDate.toISOString()}, ` +
				`remaining: ${Math.round(remainingMs / 1000 / 60)} minutes ` +
				`(${remainingMs > 0 ? 'VALID' : 'EXPIRED'})`
		);
	}
}

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

	/** User email address */
	private _email = $state<string | null>(storedEmail);

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

	/** Get the user email */
	get email(): string | null {
		return this._email;
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
		const needsRefresh = remaining < TOKEN_REFRESH_THRESHOLD_MS;
		if (needsRefresh) {
			log.debug(
				`[AUTH CHECK] tokenNeedsRefresh=true, remaining=${Math.round(remaining / 1000)}s, ` +
					`expiresAt=${this._expiresAt.toISOString()}`
			);
		}
		return needsRefresh;
	}

	/**
	 * Check if token is expired
	 */
	tokenIsExpired(): boolean {
		if (!this._expiresAt) {
			log.warn('[AUTH CHECK] tokenIsExpired=true (no expiresAt set)');
			return true;
		}
		const remaining = this._expiresAt.getTime() - Date.now();
		const expired = remaining < 0;
		log.debug(
			`[AUTH CHECK] tokenIsExpired=${expired}, remaining=${Math.round(remaining / 1000)}s, ` +
				`expiresAt=${this._expiresAt.toISOString()}, now=${new Date().toISOString()}`
		);
		return expired;
	}

	/**
	 * Mark the session as expired and show re-auth modal
	 */
	markSessionExpired(): void {
		const expiresAt = this._expiresAt;
		const remaining = expiresAt ? expiresAt.getTime() - Date.now() : null;
		log.info(
			`[AUTH] markSessionExpired called. ` +
				`expiresAt=${expiresAt?.toISOString() ?? 'null'}, ` +
				`remaining=${remaining !== null ? Math.round(remaining / 1000) + 's' : 'N/A'}, ` +
				`hasToken=${!!this._token}, caller=${new Error().stack?.split('\n')[2]?.trim() ?? 'unknown'}`
		);
		this._sessionExpired = true;
	}

	/**
	 * Set authenticated state atomically with all required side effects.
	 * This is the canonical way to update auth state.
	 */
	setAuthenticatedState(newToken: string, expiresAt: Date, email?: string): void {
		const remainingMs = expiresAt.getTime() - Date.now();
		log.debug(
			`[AUTH] setAuthenticatedState: expires=${expiresAt.toISOString()}, ` +
				`remaining=${Math.round(remainingMs / 1000 / 60)} minutes, ` +
				`token=${newToken.length} chars, wasExpired=${this._sessionExpired}`
		);
		this._token = newToken;
		this._expiresAt = expiresAt;
		this._sessionExpired = false;

		// Only update email if provided (preserves existing email on token refresh)
		if (email !== undefined) {
			this._email = email;
		}

		// Persist to localStorage
		if (browser) {
			localStorage.setItem(TOKEN_KEY, newToken);
			localStorage.setItem(EXPIRES_KEY, expiresAt.toISOString());
			if (email !== undefined) {
				localStorage.setItem(EMAIL_KEY, email);
			}
			// Diagnostic: verify what was actually stored
			const verifyExpires = localStorage.getItem(EXPIRES_KEY);
			log.debug(`[AUTH] localStorage verified: expires=${verifyExpires}`);
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
		const expiresAt = this._expiresAt;
		const remaining = expiresAt ? expiresAt.getTime() - Date.now() : null;
		log.info(
			`[AUTH] logout called. ` +
				`expiresAt=${expiresAt?.toISOString() ?? 'null'}, ` +
				`remaining=${remaining !== null ? Math.round(remaining / 1000) + 's' : 'N/A'}, ` +
				`sessionExpired=${this._sessionExpired}, ` +
				`caller=${new Error().stack?.split('\n')[2]?.trim() ?? 'unknown'}`
		);
		stopRefreshTimer();
		this._token = null;
		this._expiresAt = null;
		this._email = null;
		this._sessionExpired = false;

		// Clear from localStorage
		if (browser) {
			localStorage.removeItem(TOKEN_KEY);
			localStorage.removeItem(EXPIRES_KEY);
			localStorage.removeItem(EMAIL_KEY);
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
			import('./tags.svelte.ts')
				.then(({ clearTagsCache }) => clearTagsCache())
				.catch((err) => log.warn('Failed to clear tags cache:', err)),
			import('../workflows/scan.svelte.ts')
				.then(({ scanWorkflow }) => scanWorkflow.reset())
				.catch((err) => log.warn('Failed to reset scan workflow:', err)),
		];
		await Promise.allSettled(cleanupTasks);
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const authStore = new AuthStore();

/** Mark the session as expired and show re-auth modal */
export const markSessionExpired = () => authStore.markSessionExpired();
