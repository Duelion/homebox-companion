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
// STORES - Data stores (to be migrated gradually)
// =============================================================================
export { token, isAuthenticated, sessionExpired, logout, markSessionExpired, onReauthSuccess } from './stores/auth';
export { labels, labelsById, fetchLabels, clearLabelsCache, getLabelName, isLabelsLoading } from './stores/labels';
export {
	locationStore,
	type PathItem,
	type FlatLocation,
} from './stores/locations.svelte';
export {
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
	type Toast,
} from './stores/ui';

// =============================================================================
// API - HTTP client (to be split into modules)
// =============================================================================
export { auth, locations, labels as labelsApi, items, vision, getVersion, getConfig, getLogs, fieldPreferences, ApiError, NetworkError } from './api';
