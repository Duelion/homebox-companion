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
	openai_model: string;
	update_check_enabled: boolean;
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
}

export const fieldPreferences = {
	get: () => request<FieldPreferences>('/settings/field-preferences'),

	update: (prefs: Partial<FieldPreferences>) =>
		request<FieldPreferences>('/settings/field-preferences', {
			method: 'PUT',
			body: JSON.stringify(prefs),
		}),

	reset: () =>
		request<FieldPreferences>('/settings/field-preferences', {
			method: 'DELETE',
		}),
};

