/**
 * Settings and configuration API endpoints
 */

import { request } from './client';

// =============================================================================
// VERSION
// =============================================================================

export interface VersionResponse {
	version: string;
	latest_version: string | null;
	update_available: boolean;
}

export const getVersion = (forceCheck: boolean = false) =>
	request<VersionResponse>(`/version${forceCheck ? '?force_check=true' : ''}`);

// =============================================================================
// CONFIG
// =============================================================================

export interface ConfigResponse {
	is_demo_mode: boolean;
	homebox_url: string;
	llm_model: string;
	update_check_enabled: boolean;
	image_quality: string;
	log_level: string;
}

export const getConfig = () => request<ConfigResponse>('/config');

// =============================================================================
// LOGS
// =============================================================================

export interface LogsResponse {
	logs: string;
	filename: string | null;
	total_lines: number;
	truncated: boolean;
}

export const getLogs = (lines: number = 200) =>
	request<LogsResponse>(`/logs?lines=${lines}`);

export const downloadLogs = async (filename: string) => {
	const { requestBlobUrl } = await import('./client');

	const result = await requestBlobUrl('/logs/download');

	// Create a temporary link and trigger download
	const a = document.createElement('a');
	a.href = result.url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();

	// Cleanup
	result.revoke();
	document.body.removeChild(a);
};

// =============================================================================
// FIELD PREFERENCES
// =============================================================================

export interface FieldPreferences {
	output_language: string | null;
	default_label_id: string | null;
	name: string | null;
	description: string | null;
	quantity: string | null;
	manufacturer: string | null;
	model_number: string | null;
	serial_number: string | null;
	purchase_price: string | null;
	purchase_from: string | null;
	notes: string | null;
	naming_examples: string | null;
}

/** Effective defaults (env var if set, otherwise hardcoded fallback) */
export interface EffectiveDefaults {
	output_language: string;
	default_label_id: string | null;
	name: string;
	description: string;
	quantity: string;
	manufacturer: string;
	model_number: string;
	serial_number: string;
	purchase_price: string;
	purchase_from: string;
	notes: string;
	naming_examples: string;
}

export const fieldPreferences = {
	get: () => request<FieldPreferences>('/settings/field-preferences'),

	/** Get effective defaults (env var if set, otherwise hardcoded fallback) */
	getEffectiveDefaults: () => request<EffectiveDefaults>('/settings/effective-defaults'),

	update: (prefs: Partial<FieldPreferences>) =>
		request<FieldPreferences>('/settings/field-preferences', {
			method: 'PUT',
			body: JSON.stringify(prefs),
		}),

	reset: () =>
		request<FieldPreferences>('/settings/field-preferences', {
			method: 'DELETE',
		}),

	getPromptPreview: (prefs: Partial<FieldPreferences>) =>
		request<{ prompt: string }>('/settings/prompt-preview', {
			method: 'POST',
			body: JSON.stringify(prefs),
		}),
};

