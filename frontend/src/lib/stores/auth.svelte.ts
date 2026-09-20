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

export type AuthMode = 'legacy' | 'api_key';
export type AuthPhase =
	| 'initializing'
	| 'signed_out'
	| 'connecting'
	| 'ready'
	| 'session_expired'
	| 'connection_error';

export interface HomeboxConnection {
	connected: true;
	context_id: string;
	user_id: string;
	default_group_id: string | null;
}

interface VerifiedScope {
	contextId: string;
	groupId: string | null;
}

// =============================================================================
// AUTH STORE CLASS
// =============================================================================

class AuthStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Auth token */
	private _token = $state<string | null>(null);

	/** Token expiration date */
	private _expiresAt = $state<Date | null>(null);

	/** User email address */
	private _email = $state<string | null>(null);
	private _mode = $state<AuthMode | null>(null);
	private _phase = $state<AuthPhase>('initializing');
	private _connection = $state<HomeboxConnection | null>(null);
	private _connectionError = $state<string | null>(null);
	/** Last ready scope survives connection failures so reconnects can reconcile in-memory work. */
	private _verifiedScope: VerifiedScope | null = null;

	/** Whether initial auth check has completed */
	private _initialized = $state(false);

	/** Whether the session has expired (shows re-auth modal) */
	private _sessionExpired = $state(false);

	/** Whether the connection and collection discovery are ready. */
	private _isAuthenticated = $derived.by(() => this._phase === 'ready');

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
	get mode(): AuthMode | null {
		return this._mode;
	}
	get phase(): AuthPhase {
		return this._phase;
	}
	get connection(): HomeboxConnection | null {
		return this._connection;
	}
	get contextId(): string | null {
		return this._connection?.context_id ?? null;
	}
	get verifiedScope(): Readonly<VerifiedScope> | null {
		return this._verifiedScope;
	}
	get connectionError(): string | null {
		return this._connectionError;
	}
	get isLegacy(): boolean {
		return this._mode === 'legacy';
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

	beginMode(mode: AuthMode): void {
		this._mode = mode;
		this._phase = mode === 'api_key' ? 'connecting' : 'initializing';
		this._connection = null;
		this._connectionError = null;
		if (mode === 'api_key') this.clearLegacyStorage();
	}

	loadLegacyStorage(): void {
		if (!browser || this._mode !== 'legacy') return;
		this._token = localStorage.getItem(TOKEN_KEY);
		const expires = localStorage.getItem(EXPIRES_KEY);
		this._expiresAt = expires ? new Date(expires) : null;
		this._email = localStorage.getItem(EMAIL_KEY);
	}

	setSignedOut(): void {
		this._phase = 'signed_out';
		this._connection = null;
	}

	beginConnection(): void {
		this._phase = 'connecting';
		this._connection = null;
		this._connectionError = null;
	}

	setConnection(connection: HomeboxConnection, ready = true): void {
		this._connection = connection;
		this._connectionError = null;
		if (ready) this._phase = 'ready';
	}

	markReady(): void {
		if (this._connection) this._phase = 'ready';
	}

	rememberVerifiedScope(groupId: string | null): void {
		if (this._connection) {
			this._verifiedScope = { contextId: this._connection.context_id, groupId };
		}
	}

	setConnectionError(message: string): void {
		this._connection = null;
		this._connectionError = message;
		this._phase = 'connection_error';
	}

	private clearLegacyStorage(): void {
		stopRefreshTimer();
		this._token = null;
		this._expiresAt = null;
		this._email = null;
		this._sessionExpired = false;
		if (browser) {
			localStorage.removeItem(TOKEN_KEY);
			localStorage.removeItem(EXPIRES_KEY);
			localStorage.removeItem(EMAIL_KEY);
		}
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
		if (this._mode !== 'legacy') return;
		const expiresAt = this._expiresAt;
		const remaining = expiresAt ? expiresAt.getTime() - Date.now() : null;
		log.info(
			`[AUTH] markSessionExpired called. ` +
				`expiresAt=${expiresAt?.toISOString() ?? 'null'}, ` +
				`remaining=${remaining !== null ? Math.round(remaining / 1000) + 's' : 'N/A'}, ` +
				`hasToken=${!!this._token}, caller=${new Error().stack?.split('\n')[2]?.trim() ?? 'unknown'}`
		);
		this._sessionExpired = true;
		this._phase = 'session_expired';
	}

	/**
	 * Set authenticated state atomically with all required side effects.
	 * This is the canonical way to update auth state.
	 */
	setAuthenticatedState(newToken: string, expiresAt: Date, email?: string): void {
		if (this._mode !== 'legacy') return;
		const remainingMs = expiresAt.getTime() - Date.now();
		log.debug(
			`[AUTH] setAuthenticatedState: expires=${expiresAt.toISOString()}, ` +
				`remaining=${Math.round(remainingMs / 1000 / 60)} minutes, ` +
				`token=${newToken.length} chars, wasExpired=${this._sessionExpired}`
		);
		this._token = newToken;
		this._expiresAt = expiresAt;
		this._sessionExpired = false;
		this._phase = this._connection ? 'ready' : 'connecting';

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
		if (this._mode !== 'legacy') return;
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
		this._phase = 'signed_out';

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
			import('./collection.svelte.ts')
				.then(({ collectionStore }) => collectionStore.clear())
				.catch((err) => log.warn('Failed to clear collection state:', err)),
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
