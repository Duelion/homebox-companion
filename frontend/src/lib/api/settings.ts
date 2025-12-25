/**
 * Settings and configuration API endpoints
 */

import { request } from './client';

// =============================================================================
// DEMO MODE STORAGE
// =============================================================================

const DEMO_PREFS_KEY = 'hbc_demo_field_preferences';
let isDemoMode = false;

/** Set demo mode status (called after fetching config) */
export function setDemoMode(demoMode: boolean): void {
	isDemoMode = demoMode;
}

/** Get current demo mode status */
export function getIsDemoMode(): boolean {
	return isDemoMode;
}

/** Get default empty preferences */
function getEmptyPreferences(): FieldPreferences {
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
	} catch {
		// Ignore parsing errors
	}
	return getEmptyPreferences();
}

/** Save preferences to sessionStorage (demo mode) */
function saveDemoPreferences(prefs: FieldPreferences): void {
	try {
		sessionStorage.setItem(DEMO_PREFS_KEY, JSON.stringify(prefs));
	} catch {
		// Ignore storage errors (e.g., quota exceeded)
	}
}

/** Clear preferences from sessionStorage (demo mode) */
function clearDemoPreferences(): void {
	try {
		sessionStorage.removeItem(DEMO_PREFS_KEY);
	} catch {
		// Ignore removal errors
	}
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
			body: JSON.stringify(prefs),
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
			body: JSON.stringify(prefs),
		}),
};

