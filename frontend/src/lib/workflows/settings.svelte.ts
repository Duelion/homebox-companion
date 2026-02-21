/**
 * SettingsService - Centralized state management for the Settings page
 *
 * Manages all settings-related data fetching, state, and mutations.
 * Follows the same pattern as ScanWorkflow with Svelte 5 runes.
 */

import { settingsLogger as log } from '$lib/utils/logger';
import {
	getConfig,
	getLogs,
	downloadLogs,
	getLLMDebugLogs,
	downloadLLMDebugLogs,
	getVersion,
	fieldPreferences,
	customFields,
	setDemoMode,
	getEmptyPreferences,
	type ConfigResponse,
	type LogsResponse,
	type FieldPreferences,
	type EffectiveDefaults,
	type CustomFieldDefinition,
} from '$lib/api/settings';
import { tags as tagsApi } from '$lib/api';
import type { Tag } from '$lib/types';
import { getLogBuffer, clearLogBuffer, exportLogs, type LogEntry } from '$lib/utils/logger';
import { chatStore } from '$lib/stores/chat.svelte';

// =============================================================================
// ERROR HANDLING HELPER
// =============================================================================

/**
 * Safely extract a user-friendly error message from any error type.
 * Handles Error instances, ApiError, objects with message properties,
 * arrays, and primitives. Returns a fallback string for unhandled cases.
 */
function getErrorMessage(error: unknown, fallback: string): string {
	if (error instanceof Error) {
		return error.message;
	}
	if (typeof error === 'string') {
		return error;
	}
	// Handle plain objects with a message property
	if (error && typeof error === 'object' && 'message' in error) {
		const msg = (error as { message: unknown }).message;
		if (typeof msg === 'string') {
			return msg;
		}
	}
	return fallback;
}

/** Default number of log lines to fetch */
const DEFAULT_LOG_LINES = 300;

// =============================================================================
// FIELD METADATA
// =============================================================================

export interface FieldMeta {
	key: keyof FieldPreferences;
	label: string;
}

/** Field metadata for display in the preferences form */
export const FIELD_META: FieldMeta[] = [
	{ key: 'name', label: 'Name' },
	{ key: 'description', label: 'Description' },
	{ key: 'quantity', label: 'Quantity' },
	{ key: 'manufacturer', label: 'Manufacturer' },
	{ key: 'model_number', label: 'Model Number' },
	{ key: 'serial_number', label: 'Serial Number' },
	{ key: 'purchase_price', label: 'Purchase Price' },
	{ key: 'purchase_from', label: 'Purchase From' },
	{ key: 'notes', label: 'Notes' },
];

/** Environment variable mapping for export */
export const ENV_VAR_MAPPING: Record<keyof FieldPreferences, string> = {
	output_language: 'HBC_AI_OUTPUT_LANGUAGE',
	default_tag_id: 'HBC_AI_DEFAULT_TAG_ID',
	name: 'HBC_AI_NAME',
	description: 'HBC_AI_DESCRIPTION',
	quantity: 'HBC_AI_QUANTITY',
	manufacturer: 'HBC_AI_MANUFACTURER',
	model_number: 'HBC_AI_MODEL_NUMBER',
	serial_number: 'HBC_AI_SERIAL_NUMBER',
	purchase_price: 'HBC_AI_PURCHASE_PRICE',
	purchase_from: 'HBC_AI_PURCHASE_FROM',
	notes: 'HBC_AI_NOTES',
	naming_examples: 'HBC_AI_NAMING_EXAMPLES',
};

// =============================================================================
// SETTINGS SERVICE CLASS
// =============================================================================

class SettingsService {
	// =========================================================================
	// CORE CONFIG STATE
	// =========================================================================

	config = $state<ConfigResponse | null>(null);
	availableTags = $state<Tag[]>([]);

	// =========================================================================
	// VERSION/UPDATE STATE
	// =========================================================================

	updateAvailable = $state(false);
	latestVersion = $state<string | null>(null);

	// =========================================================================
	// SERVER LOGS STATE
	// =========================================================================

	serverLogs = $state<LogsResponse | null>(null);
	showServerLogs = $state(false);

	// =========================================================================
	// FRONTEND LOGS STATE
	// =========================================================================

	frontendLogs = $state<LogEntry[]>([]);
	showFrontendLogs = $state(false);

	// =========================================================================
	// LLM DEBUG LOG STATE (raw LLM request/response pairs for debugging)
	// =========================================================================

	llmDebugLog = $state<LogsResponse | null>(null);
	showLLMDebugLog = $state(false);

	// =========================================================================
	// FIELD PREFERENCES STATE
	// =========================================================================

	fieldPrefs = $state<FieldPreferences>(getEmptyPreferences());
	effectiveDefaults = $state<EffectiveDefaults | null>(null);
	showFieldPrefs = $state(false);
	showGeneralSettings = $state(false);
	showDefaultFields = $state(false);
	promptPreview = $state<string | null>(null);
	showPromptPreview = $state(false);

	// =========================================================================
	// CUSTOM FIELDS STATE
	// =========================================================================

	customFieldDefs = $state<CustomFieldDefinition[]>([]);
	showCustomFields = $state(false);
	customFieldsSaveState = $state<'idle' | 'saving' | 'success' | 'error'>('idle');

	// =========================================================================
	// LOADING STATES
	// =========================================================================

	isLoading = $state({
		config: true,
		serverLogs: false,
		llmDebugLog: false,
		fieldPrefs: false,
		promptPreview: false,
		updateCheck: false,
	});

	// =========================================================================
	// SAVE STATE FOR FIELD PREFS
	// =========================================================================

	saveState = $state<'idle' | 'saving' | 'success' | 'error'>('idle');

	// =========================================================================
	// ERROR STATES
	// =========================================================================

	errors = $state({
		init: null as string | null,
		serverLogs: null as string | null,
		llmDebugLog: null as string | null,
		fieldPrefs: null as string | null,
		updateCheck: null as string | null,
	});

	// =========================================================================
	// UI STATES
	// =========================================================================

	showAboutDetails = $state(false);
	updateCheckDone = $state(false);

	// Track cleanup timeouts
	private _timeoutIds: number[] = [];

	// =========================================================================
	// INITIALIZATION
	// =========================================================================

	/**
	 * Initialize settings data.
	 * Fetches config, version info, and tags in parallel.
	 */
	async initialize(): Promise<void> {
		this.isLoading.config = true;
		this.errors.init = null;

		try {
			const [configResult, versionResult, tagsResult] = await Promise.all([
				getConfig(),
				getVersion(true), // Force check for updates
				tagsApi.list(), // Auth-required call to detect expired sessions early
			]);

			this.config = configResult;
			setDemoMode(configResult.is_demo_mode, configResult.demo_mode_explicit);
			this.availableTags = tagsResult;

			// Set update info
			if (versionResult.update_available && versionResult.latest_version) {
				this.updateAvailable = true;
				this.latestVersion = versionResult.latest_version;
			}
		} catch (error) {
			// If it's a 401, the session expired modal will already be shown
			log.error('Failed to load settings data:', error);
			this.errors.init = getErrorMessage(error, 'Failed to load settings');
		} finally {
			this.isLoading.config = false;
		}
	}

	// =========================================================================
	// SERVER LOGS
	// =========================================================================

	async toggleServerLogs(): Promise<void> {
		if (this.serverLogs) {
			this.showServerLogs = !this.showServerLogs;
			return;
		}

		this.isLoading.serverLogs = true;
		this.errors.serverLogs = null;

		try {
			this.serverLogs = await getLogs(DEFAULT_LOG_LINES);
			this.showServerLogs = true;
		} catch (error) {
			log.error('Failed to load logs:', error);
			this.errors.serverLogs = getErrorMessage(error, 'Failed to load logs');
		} finally {
			this.isLoading.serverLogs = false;
		}
	}

	async refreshServerLogs(): Promise<void> {
		this.isLoading.serverLogs = true;
		this.errors.serverLogs = null;

		try {
			this.serverLogs = await getLogs(DEFAULT_LOG_LINES);
		} catch (error) {
			log.error('Failed to refresh logs:', error);
			this.errors.serverLogs = getErrorMessage(error, 'Failed to load logs');
		} finally {
			this.isLoading.serverLogs = false;
		}
	}

	async downloadServerLogs(): Promise<void> {
		if (!this.serverLogs?.filename) return;

		try {
			await downloadLogs(this.serverLogs.filename);
		} catch (error) {
			log.error('Failed to download logs:', error);
			this.errors.serverLogs = getErrorMessage(error, 'Failed to download logs');
		}
	}

	// =========================================================================
	// FRONTEND LOGS
	// =========================================================================

	toggleFrontendLogs(): void {
		this.frontendLogs = [...getLogBuffer()];
		this.showFrontendLogs = !this.showFrontendLogs;
	}

	refreshFrontendLogs(): void {
		this.frontendLogs = [...getLogBuffer()];
	}

	clearFrontendLogs(): void {
		clearLogBuffer();
		this.frontendLogs = [];
	}

	exportFrontendLogs(): void {
		const json = exportLogs();
		const blob = new Blob([json], { type: 'application/json' });
		const url = window.URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `frontend-logs-${new Date().toISOString().split('T')[0]}.json`;
		document.body.appendChild(a);
		a.click();
		window.URL.revokeObjectURL(url);
		document.body.removeChild(a);
	}

	// =========================================================================
	// LLM DEBUG LOG (raw LLM request/response pairs for debugging)
	// =========================================================================

	async toggleLLMDebugLog(): Promise<void> {
		if (this.llmDebugLog) {
			this.showLLMDebugLog = !this.showLLMDebugLog;
			return;
		}

		this.isLoading.llmDebugLog = true;
		this.errors.llmDebugLog = null;

		try {
			this.llmDebugLog = await getLLMDebugLogs(DEFAULT_LOG_LINES);
			this.showLLMDebugLog = true;
		} catch (error) {
			log.error('Failed to load LLM debug log:', error);
			this.errors.llmDebugLog = getErrorMessage(error, 'Failed to load LLM debug log');
		} finally {
			this.isLoading.llmDebugLog = false;
		}
	}

	async refreshLLMDebugLog(): Promise<void> {
		this.isLoading.llmDebugLog = true;
		this.errors.llmDebugLog = null;

		try {
			this.llmDebugLog = await getLLMDebugLogs(DEFAULT_LOG_LINES);
		} catch (error) {
			log.error('Failed to refresh LLM debug log:', error);
			this.errors.llmDebugLog = getErrorMessage(error, 'Failed to load LLM debug log');
		} finally {
			this.isLoading.llmDebugLog = false;
		}
	}

	async downloadLLMDebugLogs(): Promise<void> {
		if (!this.llmDebugLog?.filename) return;

		try {
			await downloadLLMDebugLogs(this.llmDebugLog.filename);
		} catch (error) {
			log.error('Failed to download LLM debug logs:', error);
			this.errors.llmDebugLog = getErrorMessage(error, 'Failed to download LLM debug logs');
		}
	}

	// =========================================================================
	// CHAT TRANSCRIPT (user-visible conversation from localStorage)
	// =========================================================================

	/**
	 * Export chat transcript (user-visible conversation) as JSON.
	 * This is the human-readable conversation the user sees in the chat UI.
	 */
	exportChatTranscript(): void {
		if (chatStore.messageCount === 0) {
			log.warn('No chat messages to export');
			return;
		}

		const json = chatStore.exportTranscript();
		const blob = new Blob([json], { type: 'application/json' });
		const url = window.URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `chat-transcript-${new Date().toISOString().split('T')[0]}.json`;
		document.body.appendChild(a);
		a.click();
		window.URL.revokeObjectURL(url);
		document.body.removeChild(a);
		log.success(`Exported ${chatStore.messageCount} chat messages`);
	}

	/**
	 * Clear all chat data: frontend localStorage and backend session.
	 * Uses chatStore.clearHistory() to ensure consistent state across all stores.
	 * Note: LLM debug logs are preserved (managed by loguru with automatic retention).
	 */
	async clearAllChatData(): Promise<void> {
		try {
			await chatStore.clearHistory();
			// Reset our local view of the LLM debug log (will reload from files on next toggle)
			this.llmDebugLog = null;
			this.showLLMDebugLog = false;
			log.success('All chat data cleared');
		} catch (error) {
			log.error('Failed to clear chat data:', error);
		}
	}

	// =========================================================================
	// FIELD PREFERENCES
	// =========================================================================

	async toggleFieldPrefs(): Promise<void> {
		// If loading, do nothing (prevent race condition)
		if (this.isLoading.fieldPrefs) {
			return;
		}

		// If already loaded, just toggle visibility
		if (this.effectiveDefaults !== null) {
			this.showFieldPrefs = !this.showFieldPrefs;
			return;
		}

		this.isLoading.fieldPrefs = true;
		this.errors.fieldPrefs = null;

		try {
			const [prefsResult, defaultsResult] = await Promise.all([
				fieldPreferences.get(),
				fieldPreferences.getEffectiveDefaults(),
			]);
			this.fieldPrefs = prefsResult;
			this.effectiveDefaults = defaultsResult;
			this.showFieldPrefs = true;
		} catch (error) {
			log.error('Failed to load field preferences:', error);
			this.errors.fieldPrefs = getErrorMessage(error, 'Failed to load preferences');
		} finally {
			this.isLoading.fieldPrefs = false;
		}
	}

	async saveFieldPrefs(): Promise<void> {
		this.saveState = 'saving';
		this.errors.fieldPrefs = null;

		try {
			// Unwrap the $state proxy to get a plain object for serialization
			const prefsToSave = $state.snapshot(this.fieldPrefs);
			const result = await fieldPreferences.update(prefsToSave);
			this.fieldPrefs = result;
			this.saveState = 'success';

			// Reset to idle after showing success (with cleanup)
			this._scheduleTimeout(() => {
				this.saveState = 'idle';
			}, 2000);
		} catch (error) {
			log.error('Failed to save field preferences:', error);
			this.errors.fieldPrefs = getErrorMessage(error, 'Failed to save preferences');
			this.saveState = 'error';

			this._scheduleTimeout(() => {
				this.saveState = 'idle';
			}, 3000);
		}
	}

	/**
	 * Update a single field preference value.
	 * Also clears the prompt preview cache.
	 */
	updateFieldPref(key: keyof FieldPreferences, value: string): void {
		this.fieldPrefs[key] = value.trim() || null;
		this.promptPreview = null; // Clear cached preview
	}

	/**
	 * Reset a single field preference to null (default).
	 * Local-only: user must Save to persist.
	 */
	resetSingleFieldPref(key: keyof FieldPreferences): void {
		this.fieldPrefs[key] = null;
		this.promptPreview = null;
	}

	/**
	 * Reset all General Settings fields (output_language, default_tag_id, naming_examples).
	 * Local-only: user must Save to persist.
	 */
	resetGeneralSettings(): void {
		this.fieldPrefs.output_language = null;
		this.fieldPrefs.default_tag_id = null;
		this.fieldPrefs.naming_examples = null;
		this.promptPreview = null;
	}

	/**
	 * Reset all Default Fields (FIELD_META keys).
	 * Local-only: user must Save to persist.
	 */
	resetDefaultFields(): void {
		for (const field of FIELD_META) {
			this.fieldPrefs[field.key] = null;
		}
		this.promptPreview = null;
	}

	toggleGeneralSettings(): void {
		this.showGeneralSettings = !this.showGeneralSettings;
	}

	toggleDefaultFields(): void {
		this.showDefaultFields = !this.showDefaultFields;
	}

	// =========================================================================
	// CUSTOM FIELDS
	// =========================================================================

	async toggleCustomFields(): Promise<void> {
		// If already loaded, just toggle visibility
		if (this.customFieldDefs.length > 0 || this.showCustomFields) {
			this.showCustomFields = !this.showCustomFields;
			return;
		}

		// Load from server
		await this.loadCustomFields();
		this.showCustomFields = true;
	}

	async loadCustomFields(): Promise<void> {
		try {
			this.customFieldDefs = await customFields.list();
		} catch (error) {
			log.error('Failed to load custom fields:', error);
		}
	}

	addCustomField(): void {
		this.customFieldDefs = [...this.customFieldDefs, { name: '', ai_instruction: '' }];
	}

	updateCustomFieldProp(index: number, prop: keyof CustomFieldDefinition, value: string): void {
		this.customFieldDefs[index][prop] = value;
		this.promptPreview = null; // Clear cached preview
	}

	removeCustomField(index: number): void {
		this.customFieldDefs = this.customFieldDefs.filter((_, i) => i !== index);
	}

	async saveCustomFields(): Promise<void> {
		this.customFieldsSaveState = 'saving';

		try {
			// Filter out empty definitions before saving
			const valid = this.customFieldDefs.filter((f) => f.name.trim() && f.ai_instruction.trim());
			const snapshot = $state.snapshot(valid);
			this.customFieldDefs = await customFields.update(snapshot);
			this.customFieldsSaveState = 'success';
			this.promptPreview = null; // Clear cached preview

			this._scheduleTimeout(() => {
				this.customFieldsSaveState = 'idle';
			}, 2000);
		} catch (error) {
			log.error('Failed to save custom fields:', error);
			this.customFieldsSaveState = 'error';

			this._scheduleTimeout(() => {
				this.customFieldsSaveState = 'idle';
			}, 3000);
		}
	}

	// =========================================================================
	// PROMPT PREVIEW
	// =========================================================================

	async togglePromptPreview(): Promise<void> {
		// If already showing, just toggle off
		if (this.showPromptPreview) {
			this.showPromptPreview = false;
			return;
		}

		// If we have cached preview, just show it
		if (this.promptPreview) {
			this.showPromptPreview = true;
			return;
		}

		// Otherwise fetch the preview
		this.isLoading.promptPreview = true;

		try {
			// Ensure field preferences are loaded first (they're needed for the preview)
			if (this.effectiveDefaults === null) {
				const [prefsResult, defaultsResult] = await Promise.all([
					fieldPreferences.get(),
					fieldPreferences.getEffectiveDefaults(),
				]);
				this.fieldPrefs = prefsResult;
				this.effectiveDefaults = defaultsResult;
			}

			// Ensure custom fields are loaded (they're included in the preview)
			if (this.customFieldDefs.length === 0) {
				await this.loadCustomFields();
			}

			// Unwrap the $state proxy to get a plain object for serialization
			const prefsForPreview = $state.snapshot(this.fieldPrefs);
			const customFieldsSnapshot = $state.snapshot(this.customFieldDefs);
			const result = await fieldPreferences.getPromptPreview(prefsForPreview, customFieldsSnapshot);
			this.promptPreview = result.prompt;
			this.showPromptPreview = true;
		} catch (error) {
			log.error('Failed to load prompt preview:', error);
			this.errors.fieldPrefs = getErrorMessage(error, 'Failed to load preview');
		} finally {
			this.isLoading.promptPreview = false;
		}
	}

	// =========================================================================
	// ENV EXPORT
	// =========================================================================

	/**
	 * Generate environment variable string from preferences.
	 * Only includes fields that differ from effective defaults (actual customizations).
	 */
	generateEnvVars(prefs: FieldPreferences): string {
		const lines: string[] = [];
		const defaults = this.effectiveDefaults;

		for (const [key, envName] of Object.entries(ENV_VAR_MAPPING)) {
			const value = prefs[key as keyof FieldPreferences];
			const defaultValue = defaults?.[key as keyof FieldPreferences];
			// Only export if value exists AND differs from the effective default
			if (value && value !== defaultValue) {
				// Escape quotes and wrap in quotes if contains special chars
				const escaped = value.replace(/"/g, '\\"');
				lines.push(`${envName}="${escaped}"`);
			}
		}

		return lines.length > 0 ? lines.join('\n') : '# No customizations configured';
	}

	// =========================================================================
	// VERSION CHECK
	// =========================================================================

	async checkForUpdates(): Promise<void> {
		this.isLoading.updateCheck = true;
		this.errors.updateCheck = null;
		this.updateCheckDone = false;

		try {
			const versionResult = await getVersion(true);

			if (versionResult.update_available && versionResult.latest_version) {
				this.updateAvailable = true;
				this.latestVersion = versionResult.latest_version;
			} else {
				this.updateAvailable = false;
				this.latestVersion = null;
				this.updateCheckDone = true;

				this._scheduleTimeout(() => {
					this.updateCheckDone = false;
				}, 5000);
			}
		} catch (error) {
			log.error('Failed to check for updates:', error);
			this.errors.updateCheck = getErrorMessage(error, 'Failed to check for updates');
		} finally {
			this.isLoading.updateCheck = false;
		}
	}

	// =========================================================================
	// CLEANUP
	// =========================================================================

	/**
	 * Schedule a timeout with cleanup tracking.
	 */
	private _scheduleTimeout(callback: () => void, delay: number): void {
		const id = window.setTimeout(() => {
			callback();
			// Remove from tracking after execution
			const idx = this._timeoutIds.indexOf(id);
			if (idx !== -1) {
				this._timeoutIds.splice(idx, 1);
			}
		}, delay);
		this._timeoutIds.push(id);
	}

	/**
	 * Clean up any pending timeouts.
	 * Should be called when component unmounts.
	 */
	cleanup(): void {
		for (const id of this._timeoutIds) {
			window.clearTimeout(id);
		}
		this._timeoutIds = [];
	}

	/**
	 * Reset all state (useful when logging out or switching views).
	 */
	reset(): void {
		this.cleanup();

		// Reset all state
		this.config = null;
		this.availableTags = [];
		this.updateAvailable = false;
		this.latestVersion = null;
		this.serverLogs = null;
		this.showServerLogs = false;
		this.frontendLogs = [];
		this.showFrontendLogs = false;
		this.llmDebugLog = null;
		this.showLLMDebugLog = false;
		this.fieldPrefs = getEmptyPreferences();
		this.effectiveDefaults = null;
		this.showFieldPrefs = false;
		this.showGeneralSettings = false;
		this.showDefaultFields = false;
		this.promptPreview = null;
		this.showPromptPreview = false;
		this.customFieldDefs = [];
		this.showCustomFields = false;
		this.customFieldsSaveState = 'idle';
		this.showAboutDetails = false;
		this.updateCheckDone = false;
		this.saveState = 'idle';

		this.isLoading = {
			config: true,
			serverLogs: false,
			llmDebugLog: false,
			fieldPrefs: false,
			promptPreview: false,
			updateCheck: false,
		};

		this.errors = {
			init: null,
			serverLogs: null,
			llmDebugLog: null,
			fieldPrefs: null,
			updateCheck: null,
		};
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const settingsService = new SettingsService();
