/**
 * Settings and configuration API endpoints
 */

import { request } from './client';

// =============================================================================
// DEMO MODE STORAGE
// =============================================================================

const DEMO_PREFS_KEY = 'hbc_demo_field_preferences';
let isDemoMode = false;
let isDemoModeExplicit = false;

/** Set demo mode status (called after fetching config) */
export function setDemoMode(demoMode: boolean, explicitDemoMode: boolean = false): void {
	isDemoMode = demoMode;
	isDemoModeExplicit = explicitDemoMode;
}

/** Get current demo mode status (includes URL-based detection) */
export function getIsDemoMode(): boolean {
	return isDemoMode;
}

/** Get explicit demo mode status (only HBC_DEMO_MODE env var, for security-sensitive features) */
export function getIsDemoModeExplicit(): boolean {
	return isDemoModeExplicit;
}

/** Get default empty preferences */
export function getEmptyPreferences(): FieldPreferences {
	return {
		output_language: null,
		default_label_id: null,
		name: null,
		description: null,
		quantity: null,
		manufacturer: null,
		model_number: null,
		serial_number: null,
		purchase_price: null,
		purchase_from: null,
		notes: null,
		naming_examples: null,
	};
}

/** Load preferences from sessionStorage (demo mode) */
function loadDemoPreferences(): FieldPreferences {
	try {
		const stored = sessionStorage.getItem(DEMO_PREFS_KEY);
		if (stored) {
			return JSON.parse(stored) as FieldPreferences;
		}
	} catch (e) {
		// Log parsing errors for debugging but don't break the app
		console.warn('[Demo] Failed to load preferences from sessionStorage:', e);
	}
	return getEmptyPreferences();
}

/** Save preferences to sessionStorage (demo mode) */
function saveDemoPreferences(prefs: FieldPreferences): void {
	try {
		sessionStorage.setItem(DEMO_PREFS_KEY, JSON.stringify(prefs));
	} catch (e) {
		// Log storage errors (e.g., quota exceeded) for debugging
		console.warn('[Demo] Failed to save preferences to sessionStorage:', e);
	}
}

/** Clear preferences from sessionStorage (demo mode) - used by fieldPreferences.reset() */
function clearDemoPreferences(): void {
	try {
		sessionStorage.removeItem(DEMO_PREFS_KEY);
	} catch (e) {
		// Log removal errors for debugging
		console.warn('[Demo] Failed to clear preferences from sessionStorage:', e);
	}
}

/**
 * Filter out null/undefined values from preferences object.
 * Backend expects only non-null string values (uses defaults for missing fields).
 */
function filterNullValues(prefs: Partial<FieldPreferences>): Record<string, string> {
	const result: Record<string, string> = {};
	for (const [key, value] of Object.entries(prefs)) {
		if (value !== null && value !== undefined) {
			result[key] = value;
		}
	}
	return result;
}

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
	/** Explicit demo mode from HBC_DEMO_MODE env var only (not URL detection) */
	demo_mode_explicit: boolean;
	homebox_url: string;
	llm_model: string;
	update_check_enabled: boolean;
	image_quality: string;
	log_level: string;
	capture_max_images: number;
	capture_max_file_size_mb: number;
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

export const getLogs = (lines: number = 200) => request<LogsResponse>(`/logs?lines=${lines}`);

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

export const getLLMDebugLogs = (lines: number = 200) =>
	request<LogsResponse>(`/logs/llm-debug?lines=${lines}`);

export const downloadLLMDebugLogs = async (filename: string) => {
	const { requestBlobUrl } = await import('./client');

	const result = await requestBlobUrl('/logs/llm-debug/download');

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
	get: async (): Promise<FieldPreferences> => {
		// In demo mode, use sessionStorage instead of server
		if (isDemoMode) {
			return loadDemoPreferences();
		}
		return request<FieldPreferences>('/settings/field-preferences');
	},

	/** Get effective defaults (env var if set, otherwise hardcoded fallback) */
	getEffectiveDefaults: () => request<EffectiveDefaults>('/settings/effective-defaults'),

	update: async (prefs: Partial<FieldPreferences>): Promise<FieldPreferences> => {
		// In demo mode, save to sessionStorage instead of server
		if (isDemoMode) {
			// Merge with current prefs to handle partial updates
			const current = loadDemoPreferences();
			const updated: FieldPreferences = { ...current };

			// Only update fields that are explicitly provided (not undefined)
			for (const key of Object.keys(prefs) as (keyof FieldPreferences)[]) {
				if (key in prefs) {
					updated[key] = prefs[key] ?? null;
				}
			}

			saveDemoPreferences(updated);
			return updated;
		}

		return request<FieldPreferences>('/settings/field-preferences', {
			method: 'PUT',
			body: JSON.stringify(filterNullValues(prefs)),
		});
	},

	reset: async (): Promise<FieldPreferences> => {
		// In demo mode, clear sessionStorage instead of server
		if (isDemoMode) {
			clearDemoPreferences();
			return getEmptyPreferences();
		}
		return request<FieldPreferences>('/settings/field-preferences', {
			method: 'DELETE',
		});
	},

	getPromptPreview: (prefs: Partial<FieldPreferences>) =>
		request<{ prompt: string }>('/settings/prompt-preview', {
			method: 'POST',
			body: JSON.stringify(filterNullValues(prefs)),
		}),
};

// =============================================================================
// LLM PROFILES
// =============================================================================

export type ProfileStatus = 'primary' | 'fallback' | 'off';

export interface LLMProfile {
	name: string;
	model: string;
	has_api_key: boolean;
	api_base: string | null;
	status: ProfileStatus;
}

export interface LLMProfileCreate {
	name: string;
	model: string;
	api_key?: string | null;
	api_base?: string | null;
	status?: ProfileStatus;
}

export interface LLMProfileUpdate {
	new_name?: string | null;
	model?: string | null;
	api_key?: string | null;
	api_base?: string | null;
	status?: ProfileStatus | null;
}

export interface TestConnectionResponse {
	success: boolean;
	message: string;
	model_info?: {
		model: string;
		provider: string;
	} | null;
}

export const llmProfiles = {
	/** List all LLM profiles (API keys masked) */
	list: () => request<{ profiles: LLMProfile[] }>('/llm/profiles'),

	/** Create a new LLM profile */
	create: (profile: LLMProfileCreate) =>
		request<LLMProfile>('/llm/profiles', {
			method: 'POST',
			body: JSON.stringify(profile),
		}),

	/** Update an existing LLM profile */
	update: (name: string, updates: LLMProfileUpdate) =>
		request<LLMProfile>(`/llm/profiles/${encodeURIComponent(name)}`, {
			method: 'PUT',
			body: JSON.stringify(updates),
		}),

	/** Delete an LLM profile */
	delete: (name: string) =>
		request<void>(`/llm/profiles/${encodeURIComponent(name)}`, {
			method: 'DELETE',
		}),

	/** Set a profile as the active one */
	activate: (name: string) =>
		request<LLMProfile>(`/llm/profiles/${encodeURIComponent(name)}/activate`, {
			method: 'POST',
		}),

	/** Test connection to an LLM profile */
	test: (name: string, overrides?: { model?: string; api_key?: string; api_base?: string }) =>
		request<TestConnectionResponse>(`/llm/profiles/${encodeURIComponent(name)}/test`, {
			method: 'POST',
			body: overrides ? JSON.stringify(overrides) : undefined,
		}),
};
