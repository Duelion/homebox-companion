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
	show_token_usage: boolean;
	enrichment_enabled: boolean;
	enrichment_auto_enrich: boolean;
	enrichment_cache_ttl_hours: number;
	// Web search settings
	search_provider: string;
	search_tavily_api_key: string | null;
	search_google_api_key: string | null;
	search_google_engine_id: string | null;
	search_searxng_url: string | null;
	// Custom retailer domains
	enrichment_retailer_domains: string[];
	// Effective values
	effective_homebox_url: string;
	effective_image_quality: string;
	image_quality_options: string[];
}

export interface AppPreferencesInput {
	homebox_url_override: string | null;
	image_quality_override: string | null;
	duplicate_detection_enabled: boolean;
	show_token_usage: boolean;
	enrichment_enabled: boolean;
	enrichment_auto_enrich: boolean;
	enrichment_cache_ttl_hours: number;
	// Web search settings
	search_provider: string;
	search_tavily_api_key: string | null;
	search_google_api_key: string | null;
	search_google_engine_id: string | null;
	search_searxng_url: string | null;
	// Custom retailer domains
	enrichment_retailer_domains: string[];
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
