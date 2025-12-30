/**
 * Homebox Companion Frontend Library
 * 
 * Barrel exports for all shared modules.
 */

// =============================================================================
// TYPES - All type definitions
// =============================================================================
export * from './types';

// =============================================================================
// WORKFLOWS - Business logic layer
// =============================================================================
export { scanWorkflow } from './workflows/scan.svelte';

// =============================================================================
// STORES - Svelte 5 class-based stores
// =============================================================================
export { authStore, logout, markSessionExpired, setAuthenticatedState } from './stores/auth.svelte';
export { labelStore, labels, labelsById, fetchLabels, clearLabelsCache, getLabelName, isLabelsLoading } from './stores/labels.svelte';
export {
	locationStore,
	type PathItem,
	type FlatLocation,
} from './stores/locations.svelte';
export {
	uiStore,
	isLoading,
	loadingMessage,
	toasts,
	showToast,
	dismissToast,
	isOnline,
	appVersion,
	latestVersion,
	updateDismissed,
	setLoading,
	clearAllToasts,
	TOAST_DURATION_MS,
	type Toast,
} from './stores/ui.svelte';

// =============================================================================
// API - HTTP client (to be split into modules)
// =============================================================================
export { auth, locations, labels as labelsApi, items, vision, getVersion, getConfig, getLogs, fieldPreferences, setDemoMode, ApiError, NetworkError } from './api';
