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
	setDemoMode,
	getEmptyPreferences,
	type ConfigResponse,
	type LogsResponse,
	type FieldPreferences,
	type EffectiveDefaults,
} from '$lib/api/settings';
import { labels as labelsApi, type LabelData } from '$lib/api';
import { items as itemsApi } from '$lib/api/items';
import { getLogBuffer, clearLogBuffer, exportLogs, type LogEntry } from '$lib/utils/logger';
import { chatStore } from '$lib/stores/chat.svelte';
import {
	getAIConfig,
	updateAIConfig,
	resetAIConfig,
	testProviderConnection,
	type AIConfigResponse,
	type AIConfigInput,
	type TestConnectionResponse,
} from '$lib/api/aiConfig';
import {
	getAppPreferences,
	updateAppPreferences,
	type AppPreferencesResponse,
	type AppPreferencesInput,
} from '$lib/api/appPreferences';
import { clearEnrichmentCache } from '$lib/api/enrichment';
import type { DuplicateIndexStatus } from '$lib/types';

// =============================================================================
// FIELD METADATA
// =============================================================================

export interface FieldMeta {
	key: keyof FieldPreferences;
	label: string;
	example: string;
}

/** Field metadata for display in the preferences form */
export const FIELD_META: FieldMeta[] = [
	{
		key: 'name',
		label: 'Name',
		example: '"Ball Bearing 6900-2RS 10x22x6mm", "LED Strip COB Green 5V 1M"',
	},
	{
		key: 'naming_examples',
		label: 'Naming Examples',
		example: 'Comma-separated examples that show the AI how to format names',
	},
	{
		key: 'description',
		label: 'Description',
		example: '"Minor scratches on casing", "New in packaging"',
	},
	{
		key: 'quantity',
		label: 'Quantity',
		example: '5 identical screws = qty 5, but 2 sizes = 2 separate items',
	},
	{
		key: 'manufacturer',
		label: 'Manufacturer',
		example: 'DeWalt, Vallejo (NOT "Shenzhen XYZ Technology Co.")',
	},
	{
		key: 'model_number',
		label: 'Model Number',
		example: '"DCD771C2", "72.034"',
	},
	{
		key: 'serial_number',
		label: 'Serial Number',
		example: 'Look for "S/N:", "Serial:" markings',
	},
	{
		key: 'purchase_price',
		label: 'Purchase Price',
		example: '29.99 (not "$29.99")',
	},
	{
		key: 'purchase_from',
		label: 'Purchase From',
		example: '"Amazon", "Home Depot"',
	},
	{
		key: 'notes',
		label: 'Notes',
		example: 'For defects/warnings only. Include GOOD/BAD examples for clarity.',
	},
];

/** Environment variable mapping for export */
export const ENV_VAR_MAPPING: Record<keyof FieldPreferences, string> = {
	output_language: 'HBC_AI_OUTPUT_LANGUAGE',
	default_label_id: 'HBC_AI_DEFAULT_LABEL_ID',
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
	availableLabels = $state<LabelData[]>([]);

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
	promptPreview = $state<string | null>(null);
	showPromptPreview = $state(false);

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
		aiConfig: false,
		duplicateIndex: false,
		appPreferences: false,
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
		aiConfig: null as string | null,
		duplicateIndex: null as string | null,
		appPreferences: null as string | null,
	});

	// =========================================================================
	// UI STATES
	// =========================================================================

	showAboutDetails = $state(false);
	updateCheckDone = $state(false);

	// =========================================================================
	// AI PROVIDER CONFIG STATE
	// =========================================================================

	aiConfig = $state<AIConfigResponse | null>(null);
	showAIConfig = $state(false);
	aiConfigSaveState = $state<'idle' | 'saving' | 'success' | 'error'>('idle');
	aiConfigTestResult = $state<TestConnectionResponse | null>(null);
	aiConfigTestingProvider = $state<string | null>(null);

	// =========================================================================
	// DUPLICATE INDEX STATE
	// =========================================================================

	duplicateIndexStatus = $state<DuplicateIndexStatus | null>(null);
	duplicateDetectionEnabled = $state(true);
	duplicateIndexMessage = $state<string | null>(null);
	duplicateIndexMessageType = $state<'success' | 'error' | null>(null);

	// =========================================================================
	// TOKEN USAGE DISPLAY STATE
	// =========================================================================

	showTokenUsage = $state(false);

	// =========================================================================
	// APP PREFERENCES STATE (Connection settings, etc.)
	// =========================================================================

	appPreferences = $state<AppPreferencesResponse | null>(null);
	showConnectionSettings = $state(false);
	connectionSettingsSaveState = $state<'idle' | 'saving' | 'success' | 'error'>('idle');

	// =========================================================================
	// ENRICHMENT STATE
	// =========================================================================

	enrichmentCacheClearing = $state(false);
	enrichmentCacheMessage = $state<string | null>(null);
	enrichmentCacheMessageType = $state<'success' | 'error' | null>(null);

	// Track cleanup timeouts
	private _timeoutIds: number[] = [];

	// =========================================================================
	// INITIALIZATION
	// =========================================================================

	/**
	 * Initialize settings data.
	 * Fetches config, version info, labels, and AI config in parallel.
	 */
	async initialize(): Promise<void> {
		this.isLoading.config = true;
		this.errors.init = null;

		try {
			const [configResult, versionResult, labelsResult, aiConfigResult] = await Promise.all([
				getConfig(),
				getVersion(true), // Force check for updates
				labelsApi.list(), // Auth-required call to detect expired sessions early
				getAIConfig().catch((e) => {
					log.warn('Failed to load AI config on init:', e);
					return null;
				}),
			]);

			this.config = configResult;
			setDemoMode(configResult.is_demo_mode, configResult.demo_mode_explicit);
			this.availableLabels = labelsResult;

			// Load AI config if successful (allows badge to show immediately)
			if (aiConfigResult) {
				this.aiConfig = aiConfigResult;
			}

			// Set update info
			if (versionResult.update_available && versionResult.latest_version) {
				this.updateAvailable = true;
				this.latestVersion = versionResult.latest_version;
			}
		} catch (error) {
			// If it's a 401, the session expired modal will already be shown
			log.error('Failed to load settings data:', error);
			this.errors.init = error instanceof Error ? error.message : 'Failed to load settings';
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
			this.serverLogs = await getLogs(300);
			this.showServerLogs = true;
		} catch (error) {
			log.error('Failed to load logs:', error);
			this.errors.serverLogs = error instanceof Error ? error.message : 'Failed to load logs';
		} finally {
			this.isLoading.serverLogs = false;
		}
	}

	async refreshServerLogs(): Promise<void> {
		this.isLoading.serverLogs = true;
		this.errors.serverLogs = null;

		try {
			this.serverLogs = await getLogs(300);
		} catch (error) {
			log.error('Failed to refresh logs:', error);
			this.errors.serverLogs = error instanceof Error ? error.message : 'Failed to load logs';
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
			this.errors.serverLogs = error instanceof Error ? error.message : 'Failed to download logs';
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
			this.llmDebugLog = await getLLMDebugLogs(300);
			this.showLLMDebugLog = true;
		} catch (error) {
			log.error('Failed to load LLM debug log:', error);
			this.errors.llmDebugLog =
				error instanceof Error ? error.message : 'Failed to load LLM debug log';
		} finally {
			this.isLoading.llmDebugLog = false;
		}
	}

	async refreshLLMDebugLog(): Promise<void> {
		this.isLoading.llmDebugLog = true;
		this.errors.llmDebugLog = null;

		try {
			this.llmDebugLog = await getLLMDebugLogs(300);
		} catch (error) {
			log.error('Failed to refresh LLM debug log:', error);
			this.errors.llmDebugLog =
				error instanceof Error ? error.message : 'Failed to load LLM debug log';
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
			this.errors.llmDebugLog =
				error instanceof Error ? error.message : 'Failed to download LLM debug logs';
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
		if (this.effectiveDefaults !== null || this.isLoading.fieldPrefs) {
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
			this.errors.fieldPrefs =
				error instanceof Error ? error.message : 'Failed to load preferences';
		} finally {
			this.isLoading.fieldPrefs = false;
		}
	}

	async saveFieldPrefs(): Promise<void> {
		this.saveState = 'saving';
		this.errors.fieldPrefs = null;

		try {
			const result = await fieldPreferences.update(this.fieldPrefs);
			this.fieldPrefs = result;
			this.saveState = 'success';

			// Reset to idle after showing success (with cleanup)
			this._scheduleTimeout(() => {
				this.saveState = 'idle';
			}, 2000);
		} catch (error) {
			log.error('Failed to save field preferences:', error);
			this.errors.fieldPrefs =
				error instanceof Error ? error.message : 'Failed to save preferences';
			this.saveState = 'error';

			this._scheduleTimeout(() => {
				this.saveState = 'idle';
			}, 3000);
		}
	}

	async resetFieldPrefs(): Promise<void> {
		this.saveState = 'saving';
		this.errors.fieldPrefs = null;

		try {
			const result = await fieldPreferences.reset();
			this.fieldPrefs = result;
			this.promptPreview = null; // Clear preview when resetting

			this.saveState = 'success';

			this._scheduleTimeout(() => {
				this.saveState = 'idle';
			}, 2000);
		} catch (error) {
			log.error('Failed to reset field preferences:', error);
			this.errors.fieldPrefs =
				error instanceof Error ? error.message : 'Failed to reset preferences';
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
			const result = await fieldPreferences.getPromptPreview(this.fieldPrefs);
			this.promptPreview = result.prompt;
			this.showPromptPreview = true;
		} catch (error) {
			log.error('Failed to load prompt preview:', error);
			this.errors.fieldPrefs = error instanceof Error ? error.message : 'Failed to load preview';
		} finally {
			this.isLoading.promptPreview = false;
		}
	}

	// =========================================================================
	// ENV EXPORT
	// =========================================================================

	/**
	 * Generate environment variable string from preferences.
	 */
	generateEnvVars(prefs: FieldPreferences): string {
		const lines: string[] = [];

		for (const [key, envName] of Object.entries(ENV_VAR_MAPPING)) {
			const value = prefs[key as keyof FieldPreferences];
			if (value) {
				// Escape quotes and wrap in quotes if contains special chars
				const escaped = value.replace(/"/g, '\\"');
				lines.push(`${envName}="${escaped}"`);
			}
		}

		return lines.length > 0 ? lines.join('\n') : '# No customizations configured';
	}

	// =========================================================================
	// AI PROVIDER CONFIG
	// =========================================================================

	/**
	 * Toggle AI config section visibility and load data if needed.
	 */
	async toggleAIConfig(): Promise<void> {
		if (this.aiConfig) {
			this.showAIConfig = !this.showAIConfig;
			return;
		}

		this.isLoading.aiConfig = true;
		this.errors.aiConfig = null;

		try {
			this.aiConfig = await getAIConfig();
			this.showAIConfig = true;
		} catch (error) {
			log.error('Failed to load AI config:', error);
			this.errors.aiConfig = error instanceof Error ? error.message : 'Failed to load AI configuration';
		} finally {
			this.isLoading.aiConfig = false;
		}
	}

	/**
	 * Save AI configuration.
	 */
	async saveAIConfig(config: AIConfigInput): Promise<void> {
		console.log('[SETTINGS_SVC] saveAIConfig called');
		console.log('[SETTINGS_SVC] Setting state to saving...');
		this.aiConfigSaveState = 'saving';
		this.errors.aiConfig = null;
		console.log('[SETTINGS_SVC] State set, scheduling failsafe...');

		// Failsafe: ensure we never get stuck in 'saving' state
		const failsafeTimeout = this._scheduleTimeout(() => {
			console.log('[SETTINGS_SVC] Failsafe timeout triggered!');
			if (this.aiConfigSaveState === 'saving') {
				log.error('AI config save timed out after 30 seconds');
				this.errors.aiConfig = 'Save operation timed out. Please try again.';
				this.aiConfigSaveState = 'error';
				this._scheduleTimeout(() => {
					this.aiConfigSaveState = 'idle';
				}, 3000);
			}
		}, 30000);

		console.log('[SETTINGS_SVC] Calling updateAIConfig API...');
		try {
			this.aiConfig = await updateAIConfig(config);
			console.log('[SETTINGS_SVC] API returned successfully');
			this.aiConfigSaveState = 'success';

			this._scheduleTimeout(() => {
				this.aiConfigSaveState = 'idle';
			}, 2000);
		} catch (error) {
			console.error('[SETTINGS_SVC] API call failed:', error);
			log.error('Failed to save AI config:', error);
			this.errors.aiConfig = error instanceof Error ? error.message : 'Failed to save AI configuration';
			this.aiConfigSaveState = 'error';

			this._scheduleTimeout(() => {
				this.aiConfigSaveState = 'idle';
			}, 3000);
		} finally {
			console.log('[SETTINGS_SVC] Finally block, clearing failsafe');
			// Clear the failsafe timeout since we got a response
			this._cancelTimeout(failsafeTimeout);
		}
	}

	/**
	 * Reset AI configuration to defaults.
	 */
	async resetAIConfigToDefaults(): Promise<void> {
		this.aiConfigSaveState = 'saving';
		this.errors.aiConfig = null;

		try {
			this.aiConfig = await resetAIConfig();
			this.aiConfigSaveState = 'success';

			this._scheduleTimeout(() => {
				this.aiConfigSaveState = 'idle';
			}, 2000);
		} catch (error) {
			log.error('Failed to reset AI config:', error);
			this.errors.aiConfig = error instanceof Error ? error.message : 'Failed to reset AI configuration';
			this.aiConfigSaveState = 'error';

			this._scheduleTimeout(() => {
				this.aiConfigSaveState = 'idle';
			}, 3000);
		}
	}

	/**
	 * Test connection to an AI provider.
	 */
	async testAIProviderConnection(provider: string, config: Record<string, unknown>): Promise<void> {
		this.aiConfigTestingProvider = provider;
		this.aiConfigTestResult = null;

		try {
			this.aiConfigTestResult = await testProviderConnection(provider, config);
		} catch (error) {
			log.error('Failed to test AI provider:', error);
			this.aiConfigTestResult = {
				success: false,
				provider,
				message: error instanceof Error ? error.message : 'Connection test failed',
				details: {},
			};
		} finally {
			this.aiConfigTestingProvider = null;
		}
	}

	/**
	 * Clear the test result.
	 */
	clearAIConfigTestResult(): void {
		this.aiConfigTestResult = null;
	}

	// =========================================================================
	// DUPLICATE DETECTION INDEX
	// =========================================================================

	/**
	 * Load duplicate index status.
	 */
	async loadDuplicateIndexStatus(): Promise<void> {
		this.isLoading.duplicateIndex = true;
		this.errors.duplicateIndex = null;

		try {
			this.duplicateIndexStatus = await itemsApi.getDuplicateIndexStatus();
		} catch (error) {
			log.error('Failed to load duplicate index status:', error);
			this.errors.duplicateIndex = error instanceof Error ? error.message : 'Failed to load index status';
		} finally {
			this.isLoading.duplicateIndex = false;
		}
	}

	/**
	 * Rebuild the duplicate detection index.
	 */
	async rebuildDuplicateIndex(): Promise<void> {
		this.isLoading.duplicateIndex = true;
		this.errors.duplicateIndex = null;
		this.duplicateIndexMessage = null;

		try {
			const result = await itemsApi.rebuildDuplicateIndex();
			this.duplicateIndexStatus = result.status;
			this.duplicateIndexMessage = result.message;
			this.duplicateIndexMessageType = 'success';

			this._scheduleTimeout(() => {
				this.duplicateIndexMessage = null;
				this.duplicateIndexMessageType = null;
			}, 5000);
		} catch (error) {
			log.error('Failed to rebuild duplicate index:', error);
			const errorMessage = error instanceof Error ? error.message : 'Failed to rebuild index';

			// Parse specific error types
			if (errorMessage.includes('401') || errorMessage.includes('auth')) {
				this.duplicateIndexMessage = 'Authentication failed. Please log in again.';
			} else if (errorMessage.includes('connect') || errorMessage.includes('network')) {
				this.duplicateIndexMessage = 'Cannot connect to Homebox. Check your connection.';
			} else {
				this.duplicateIndexMessage = errorMessage;
			}
			this.duplicateIndexMessageType = 'error';
		} finally {
			this.isLoading.duplicateIndex = false;
		}
	}

	/**
	 * Toggle duplicate detection setting.
	 */
	setDuplicateDetectionEnabled(enabled: boolean): void {
		this.duplicateDetectionEnabled = enabled;
		// This would normally persist to app preferences API
		// For now, just update local state (will be integrated with app preferences)
		log.info(`Duplicate detection ${enabled ? 'enabled' : 'disabled'}`);
	}

	/**
	 * Toggle token usage display setting.
	 */
	setShowTokenUsage(enabled: boolean): void {
		this.showTokenUsage = enabled;
		log.info(`Token usage display ${enabled ? 'enabled' : 'disabled'}`);
	}

	// =========================================================================
	// APP PREFERENCES (Connection Settings)
	// =========================================================================

	/**
	 * Toggle connection settings section and load data if needed.
	 */
	async toggleConnectionSettings(): Promise<void> {
		if (this.appPreferences) {
			this.showConnectionSettings = !this.showConnectionSettings;
			return;
		}

		this.isLoading.appPreferences = true;
		this.errors.appPreferences = null;

		try {
			this.appPreferences = await getAppPreferences();
			// Sync duplicate detection enabled state
			this.duplicateDetectionEnabled = this.appPreferences.duplicate_detection_enabled;
			// Sync token usage display state
			this.showTokenUsage = this.appPreferences.show_token_usage;
			this.showConnectionSettings = true;
		} catch (error) {
			log.error('Failed to load app preferences:', error);
			this.errors.appPreferences = error instanceof Error ? error.message : 'Failed to load preferences';
		} finally {
			this.isLoading.appPreferences = false;
		}
	}

	/**
	 * Save app preferences (connection settings).
	 */
	async saveAppPreferences(prefs: AppPreferencesInput): Promise<void> {
		this.connectionSettingsSaveState = 'saving';
		this.errors.appPreferences = null;

		try {
			this.appPreferences = await updateAppPreferences(prefs);
			// Sync duplicate detection enabled state
			this.duplicateDetectionEnabled = this.appPreferences.duplicate_detection_enabled;
			// Sync token usage display state
			this.showTokenUsage = this.appPreferences.show_token_usage;
			this.connectionSettingsSaveState = 'success';

			this._scheduleTimeout(() => {
				this.connectionSettingsSaveState = 'idle';
			}, 2000);
		} catch (error) {
			log.error('Failed to save app preferences:', error);
			this.errors.appPreferences = error instanceof Error ? error.message : 'Failed to save preferences';
			this.connectionSettingsSaveState = 'error';

			this._scheduleTimeout(() => {
				this.connectionSettingsSaveState = 'idle';
			}, 3000);
		}
	}

	// =========================================================================
	// ENRICHMENT
	// =========================================================================

	/**
	 * Clear the enrichment cache.
	 */
	async clearEnrichmentCache(): Promise<void> {
		this.enrichmentCacheClearing = true;
		this.enrichmentCacheMessage = null;

		try {
			const result = await clearEnrichmentCache();
			this.enrichmentCacheMessage = result.message;
			this.enrichmentCacheMessageType = 'success';

			this._scheduleTimeout(() => {
				this.enrichmentCacheMessage = null;
				this.enrichmentCacheMessageType = null;
			}, 5000);
		} catch (error) {
			log.error('Failed to clear enrichment cache:', error);
			this.enrichmentCacheMessage = error instanceof Error ? error.message : 'Failed to clear cache';
			this.enrichmentCacheMessageType = 'error';
		} finally {
			this.enrichmentCacheClearing = false;
		}
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
			this.errors.updateCheck =
				error instanceof Error ? error.message : 'Failed to check for updates';
		} finally {
			this.isLoading.updateCheck = false;
		}
	}

	// =========================================================================
	// CLEANUP
	// =========================================================================

	/**
	 * Schedule a timeout with cleanup tracking.
	 * Returns the timeout ID so it can be cancelled early if needed.
	 */
	private _scheduleTimeout(callback: () => void, delay: number): number {
		const id = window.setTimeout(() => {
			callback();
			// Remove from tracking after execution
			const idx = this._timeoutIds.indexOf(id);
			if (idx !== -1) {
				this._timeoutIds.splice(idx, 1);
			}
		}, delay);
		this._timeoutIds.push(id);
		return id;
	}

	/**
	 * Cancel a scheduled timeout and remove it from tracking.
	 */
	private _cancelTimeout(id: number): void {
		window.clearTimeout(id);
		const idx = this._timeoutIds.indexOf(id);
		if (idx !== -1) {
			this._timeoutIds.splice(idx, 1);
		}
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
		this.availableLabels = [];
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
		this.promptPreview = null;
		this.showPromptPreview = false;
		this.showAboutDetails = false;
		this.updateCheckDone = false;
		this.saveState = 'idle';

		// AI config state
		this.aiConfig = null;
		this.showAIConfig = false;
		this.aiConfigSaveState = 'idle';
		this.aiConfigTestResult = null;
		this.aiConfigTestingProvider = null;

		// Duplicate index state
		this.duplicateIndexStatus = null;
		this.duplicateDetectionEnabled = true;
		this.duplicateIndexMessage = null;
		this.duplicateIndexMessageType = null;

		// Token usage display state
		this.showTokenUsage = false;

		// App preferences state
		this.appPreferences = null;
		this.showConnectionSettings = false;
		this.connectionSettingsSaveState = 'idle';

		// Enrichment state
		this.enrichmentCacheClearing = false;
		this.enrichmentCacheMessage = null;
		this.enrichmentCacheMessageType = null;

		this.isLoading = {
			config: true,
			serverLogs: false,
			llmDebugLog: false,
			fieldPrefs: false,
			promptPreview: false,
			updateCheck: false,
			aiConfig: false,
			duplicateIndex: false,
			appPreferences: false,
		};

		this.errors = {
			init: null,
			serverLogs: null,
			llmDebugLog: null,
			fieldPrefs: null,
			updateCheck: null,
			aiConfig: null,
			duplicateIndex: null,
			appPreferences: null,
		};
	}
}

// =============================================================================
// SINGLETON EXPORT
// =============================================================================

export const settingsService = new SettingsService();
