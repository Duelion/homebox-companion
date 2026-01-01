/**
 * UI Store - Svelte 5 Class-based State
 *
 * Manages application-wide UI state including loading states,
 * toast notifications, online status, and version information.
 */

// =============================================================================
// TYPES
// =============================================================================

export interface Toast {
	id: number;
	message: string;
	type: 'info' | 'success' | 'warning' | 'error';
	exiting?: boolean;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const MAX_VISIBLE_TOASTS = 2;

/** Default toast display duration in milliseconds */
export const TOAST_DURATION_MS = 4000;

// =============================================================================
// UI STORE CLASS
// =============================================================================

class UIStore {
	// =========================================================================
	// STATE
	// =========================================================================

	/** Whether a global loading indicator should be shown */
	private _isLoading = $state(false);

	/** Message to display with the loading indicator */
	private _loadingMessage = $state('');

	/** Active toast notifications */
	private _toasts = $state<Toast[]>([]);

	/** Whether the app is online */
	private _isOnline = $state(true);

	/** Current app version */
	private _appVersion = $state('');

	/** Latest available version (null if no update) */
	private _latestVersion = $state<string | null>(null);

	/** Whether the update banner has been dismissed */
	private _updateDismissed = $state(false);

	// =========================================================================
	// INTERNAL STATE
	// =========================================================================

	/** Counter for generating unique toast IDs */
	private toastIdCounter = 0;

	/** Track all active timers per toast for cleanup */
	private toastTimers = new Map<number, Set<ReturnType<typeof setTimeout>>>();

	// =========================================================================
	// GETTERS (read-only access to state)
	// =========================================================================

	get isLoading(): boolean {
		return this._isLoading;
	}

	get loadingMessage(): string {
		return this._loadingMessage;
	}

	get toasts(): Toast[] {
		return this._toasts;
	}

	get isOnline(): boolean {
		return this._isOnline;
	}

	get appVersion(): string {
		return this._appVersion;
	}

	get latestVersion(): string | null {
		return this._latestVersion;
	}

	get updateDismissed(): boolean {
		return this._updateDismissed;
	}

	// =========================================================================
	// SETTERS
	// =========================================================================

	setOnline(value: boolean): void {
		this._isOnline = value;
	}

	setAppVersion(value: string): void {
		this._appVersion = value;
	}

	setLatestVersion(value: string | null): void {
		this._latestVersion = value;
	}

	setUpdateDismissed(value: boolean): void {
		this._updateDismissed = value;
	}

	// =========================================================================
	// LOADING METHODS
	// =========================================================================

	/** Set loading state with optional message */
	setLoading(loading: boolean, message = ''): void {
		this._isLoading = loading;
		this._loadingMessage = message;
	}

	// =========================================================================
	// TOAST METHODS
	// =========================================================================

	/** Register a timer for a toast (for cleanup tracking) */
	private registerTimer(id: number, timerId: ReturnType<typeof setTimeout>): void {
		let timers = this.toastTimers.get(id);
		if (!timers) {
			// eslint-disable-next-line svelte/prefer-svelte-reactivity -- Internal timer tracking, not reactive state
			timers = new Set();
			this.toastTimers.set(id, timers);
		}
		timers.add(timerId);
	}

	/** Clear all timers for a toast */
	private clearToastTimers(id: number): void {
		const timers = this.toastTimers.get(id);
		if (timers) {
			for (const timerId of timers) {
				clearTimeout(timerId);
			}
			this.toastTimers.delete(id);
		}
	}

	/** Remove a toast with exit animation */
	private removeToast(id: number): void {
		// Clear any pending timers for this toast first
		this.clearToastTimers(id);

		// First mark as exiting for animation
		this._toasts = this._toasts.map((toast) =>
			toast.id === id ? { ...toast, exiting: true } : toast
		);

		// Then remove after animation completes
		const animationTimer = setTimeout(() => {
			this._toasts = this._toasts.filter((toast) => toast.id !== id);
		}, 300);
		// Track the animation timer
		this.registerTimer(id, animationTimer);
	}

	/** Show a toast notification */
	showToast(message: string, type: Toast['type'] = 'info', duration = TOAST_DURATION_MS): number {
		const id = ++this.toastIdCounter;

		this._toasts = [...this._toasts, { id, message, type }];

		// If we exceed max, mark oldest non-exiting toast for removal
		const visibleToasts = this._toasts.filter((toast) => !toast.exiting);
		if (visibleToasts.length > MAX_VISIBLE_TOASTS) {
			const oldestId = visibleToasts[0].id;
			// Schedule removal of oldest toast
			const overflowTimer = setTimeout(() => this.removeToast(oldestId), 50);
			this.registerTimer(oldestId, overflowTimer);
		}

		if (duration > 0) {
			const dismissTimer = setTimeout(() => this.removeToast(id), duration);
			this.registerTimer(id, dismissTimer);
		}

		return id;
	}

	/** Dismiss a toast by ID */
	dismissToast(id: number): void {
		this.removeToast(id);
	}

	/** Clear all toasts and their timers */
	clearAllToasts(): void {
		// Clear all tracked timers
		for (const id of this.toastTimers.keys()) {
			this.clearToastTimers(id);
		}
		this._toasts = [];
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const uiStore = new UIStore();

// =============================================================================
// FUNCTION EXPORTS (backward compatibility)
// =============================================================================

// These re-export methods as standalone functions for backward compatibility.
// Prefer using uiStore.method() directly in new code.

export const setLoading = (loading: boolean, message?: string) =>
	uiStore.setLoading(loading, message);
export const showToast = (message: string, type?: Toast['type'], duration?: number) =>
	uiStore.showToast(message, type, duration);
export const dismissToast = (id: number) => uiStore.dismissToast(id);
export const clearAllToasts = () => uiStore.clearAllToasts();

// =============================================================================
// DEPRECATED EXPORTS
// =============================================================================
//
// These exports provide limited backward compatibility for code migrating from
// Svelte 4 stores. They expose a `.value` getter for reactive access but do NOT
// provide the full Svelte 4 store contract (subscribe, set, update).
//
// MIGRATION: Replace usage with direct uiStore property access:
//   - isLoading.value → uiStore.isLoading
//   - loadingMessage.value → uiStore.loadingMessage
//   - toasts.value → uiStore.toasts
//   - etc.
//
// These will be removed in a future version.

/** @deprecated Use uiStore.isLoading directly */
export const isLoading = {
	get value() {
		return uiStore.isLoading;
	},
	set: (value: boolean) => uiStore.setLoading(value),
};

export const loadingMessage = {
	get value() {
		return uiStore.loadingMessage;
	},
};

export const toasts = {
	get value() {
		return uiStore.toasts;
	},
};

export const isOnline = {
	get value() {
		return uiStore.isOnline;
	},
	set: (value: boolean) => uiStore.setOnline(value),
};

export const appVersion = {
	get value() {
		return uiStore.appVersion;
	},
	set: (value: string) => uiStore.setAppVersion(value),
};

export const latestVersion = {
	get value() {
		return uiStore.latestVersion;
	},
	set: (value: string | null) => uiStore.setLatestVersion(value),
};

export const updateDismissed = {
	get value() {
		return uiStore.updateDismissed;
	},
	set: (value: boolean) => uiStore.setUpdateDismissed(value),
};
