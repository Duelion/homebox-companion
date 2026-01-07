/**
 * App Preferences API endpoints
 */

import { request } from './client';

// =============================================================================
// TYPES
// =============================================================================

export interface AppPreferencesResponse {
	homebox_url_override: string | null;
	image_quality_override: string | null;
	duplicate_detection_enabled: boolean;
	enrichment_enabled: boolean;
	enrichment_auto_enrich: boolean;
	enrichment_cache_ttl_hours: number;
	effective_homebox_url: string;
	effective_image_quality: string;
	image_quality_options: string[];
}

export interface AppPreferencesInput {
	homebox_url_override: string | null;
	image_quality_override: string | null;
	duplicate_detection_enabled: boolean;
	enrichment_enabled: boolean;
	enrichment_auto_enrich: boolean;
	enrichment_cache_ttl_hours: number;
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Get current app preferences
 */
export const getAppPreferences = () =>
	request<AppPreferencesResponse>('/settings/app-preferences');

/**
 * Update app preferences
 */
export const updateAppPreferences = (prefs: AppPreferencesInput) =>
	request<AppPreferencesResponse>('/settings/app-preferences', {
		method: 'PUT',
		body: JSON.stringify(prefs),
	});
