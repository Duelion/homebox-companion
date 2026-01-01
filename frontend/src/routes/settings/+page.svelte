<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { resetLocationState } from '$lib/stores/locations.svelte';
	import { uiStore } from '$lib/stores/ui.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import {
		getConfig,
		getLogs,
		downloadLogs,
		getVersion,
		labels as labelsApi,
		fieldPreferences,
		setDemoMode,
		type ConfigResponse,
		type LogsResponse,
		type FieldPreferences,
		type EffectiveDefaults,
		type LabelData,
	} from '$lib/api';
	import {
		getLogBuffer,
		clearLogBuffer,
		exportLogs,
		type LogEntry,
		settingsLogger as log,
	} from '$lib/utils/logger';
	import Button from '$lib/components/Button.svelte';

	let config = $state<ConfigResponse | null>(null);
	let logs = $state<LogsResponse | null>(null);
	let isLoadingConfig = $state(true);
	let isLoadingLogs = $state(false);
	let showLogs = $state(false);
	let logsError = $state<string | null>(null);
	let logsContainer = $state<HTMLPreElement | null>(null);
	let logsFullscreenContainer = $state<HTMLDivElement | null>(null);

	// Frontend logs state
	let frontendLogs = $state<LogEntry[]>([]);
	let showFrontendLogs = $state(false);
	let frontendLogsContainer = $state<HTMLPreElement | null>(null);
	let frontendLogsFullscreenContainer = $state<HTMLDivElement | null>(null);
	let frontendLogsFullscreen = $state(false);

	// Version update state (fetched with force_check to always show updates)
	let updateAvailable = $state(false);
	let latestVersionNumber = $state<string | null>(null);
	let isCheckingUpdates = $state(false);
	let updateCheckError = $state<string | null>(null);
	let updateCheckDone = $state(false); // Shows "Up to date" message after manual check

	// Field preferences state
	let showFieldPrefs = $state(false);
	let isLoadingFieldPrefs = $state(false);
	let saveFieldPrefsState = $state<'idle' | 'saving' | 'success' | 'error'>('idle');
	let fieldPrefsError = $state<string | null>(null);
	let availableLabels = $state<LabelData[]>([]);
	let prefs = $state<FieldPreferences>({
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
	});

	// Prompt preview state
	let showPromptPreview = $state(false);
	let isLoadingPreview = $state(false);
	let promptPreview = $state<string | null>(null);

	// Export env vars state
	let showEnvExport = $state(false);
	let envCopied = $state(false);
	let isLoadingExport = $state(false);
	let exportPrefs = $state<FieldPreferences | null>(null);

	// Effective defaults from backend (env var if set, otherwise hardcoded fallback)
	let effectiveDefaults = $state<EffectiveDefaults | null>(null);

	// Fullscreen modal states
	let logsFullscreen = $state(false);
	let promptFullscreen = $state(false);

	// Field metadata for display
	const fieldMeta: Array<{
		key: keyof FieldPreferences;
		label: string;
		example: string;
	}> = [
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

	// Redirect if not authenticated
	onMount(async () => {
		if (!authStore.isAuthenticated) {
			goto(resolve('/'));
			return;
		}

		// Fetch config and version info in parallel
		// Include labels fetch to verify auth is still valid (triggers session expired modal if not)
		try {
			const [configResult, versionResult, labelsResult] = await Promise.all([
				getConfig(),
				getVersion(true), // Force check for updates regardless of env setting
				labelsApi.list(), // Auth-required call to detect expired sessions early
			]);

			config = configResult;
			setDemoMode(configResult.is_demo_mode);
			availableLabels = labelsResult; // Cache for later use

			// Set update info
			if (versionResult.update_available && versionResult.latest_version) {
				updateAvailable = true;
				latestVersionNumber = versionResult.latest_version;
			}
		} catch (error) {
			// If it's a 401, the session expired modal will already be shown
			log.error('Failed to load settings data:', error);
		} finally {
			isLoadingConfig = false;
		}
	});

	async function loadLogs() {
		if (logs) {
			showLogs = !showLogs;
			return;
		}

		isLoadingLogs = true;
		logsError = null;

		try {
			logs = await getLogs(300);
			showLogs = true;
		} catch (error) {
			log.error('Failed to load logs:', error);
			logsError = error instanceof Error ? error.message : 'Failed to load logs';
		} finally {
			isLoadingLogs = false;
		}
	}

	async function refreshLogs() {
		isLoadingLogs = true;
		logsError = null;

		try {
			logs = await getLogs(300);
		} catch (error) {
			log.error('Failed to refresh logs:', error);
			logsError = error instanceof Error ? error.message : 'Failed to load logs';
		} finally {
			isLoadingLogs = false;
		}
	}

	async function handleDownloadLogs() {
		if (!logs?.filename) return;

		try {
			await downloadLogs(logs.filename);
		} catch (error) {
			log.error('Failed to download logs:', error);
			logsError = error instanceof Error ? error.message : 'Failed to download logs';
		}
	}

	// Auto-scroll logs to bottom when loaded or refreshed
	$effect(() => {
		if (logsContainer && logs && showLogs) {
			// Use requestAnimationFrame to ensure DOM is updated
			requestAnimationFrame(() => {
				if (logsContainer) {
					logsContainer.scrollTop = logsContainer.scrollHeight;
				}
			});
		}
	});

	// Auto-scroll fullscreen logs to bottom when opened or refreshed
	$effect(() => {
		if (logsFullscreenContainer && logs && logsFullscreen) {
			// Use requestAnimationFrame to ensure DOM is updated
			requestAnimationFrame(() => {
				if (logsFullscreenContainer) {
					logsFullscreenContainer.scrollTop = logsFullscreenContainer.scrollHeight;
				}
			});
		}
	});

	// Colorize log output like Loguru does in terminal
	// Log format: "YYYY-MM-DD HH:mm:ss | LEVEL    | module:function:line - message"
	function colorizedLogs(): string {
		if (!logs?.logs) return '';

		return logs.logs
			.split('\n')
			.map((line) => {
				// Match the log format: timestamp | level | location - message
				const match = line.match(
					/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s*\| ([^-]+)- (.*)$/
				);

				if (!match) {
					// Line doesn't match format, return escaped
					return escapeHtml(line);
				}

				const [, timestamp, level, location, message] = match;
				const levelTrimmed = level.trim();

				// Get color class based on log level (matching Loguru's default color scheme)
				// https://github.com/Delgan/loguru/blob/master/loguru/_defaults.py
				let levelClass = 'text-neutral-100 font-semibold'; // Default: bold white (INFO)
				switch (levelTrimmed) {
					case 'TRACE':
						levelClass = 'text-cyan-400 font-semibold';
						break;
					case 'DEBUG':
						levelClass = 'text-blue-400 font-semibold';
						break;
					case 'INFO':
						levelClass = 'text-neutral-100 font-semibold';
						break;
					case 'SUCCESS':
						levelClass = 'text-success-500 font-semibold';
						break;
					case 'WARNING':
						levelClass = 'text-warning-500 font-semibold';
						break;
					case 'ERROR':
						levelClass = 'text-error-500 font-semibold';
						break;
					case 'CRITICAL':
						levelClass = 'text-error-700 font-bold';
						break;
				}

				// Build colorized line matching Loguru's format:
				// <green>timestamp</green> | <level>LEVEL</level> | <cyan>location</cyan> - <level>message</level>
				return (
					`<span class="text-success-500">${escapeHtml(timestamp)}</span> | ` +
					`<span class="${levelClass}">${escapeHtml(level)}</span>| ` +
					`<span class="text-cyan-400">${escapeHtml(location)}</span>- ` +
					`<span class="${levelClass}">${escapeHtml(message)}</span>`
				);
			})
			.join('\n');
	}

	function escapeHtml(text: string): string {
		return text
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;')
			.replace(/'/g, '&#039;');
	}

	// Frontend logs functions
	function loadFrontendLogs() {
		frontendLogs = [...getLogBuffer()];
		showFrontendLogs = !showFrontendLogs;
	}

	function refreshFrontendLogs() {
		frontendLogs = [...getLogBuffer()];
	}

	function handleClearFrontendLogs() {
		clearLogBuffer();
		frontendLogs = [];
	}

	function handleExportFrontendLogs() {
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

	// Auto-scroll frontend logs to bottom when loaded or refreshed
	$effect(() => {
		if (frontendLogsContainer && frontendLogs.length > 0 && showFrontendLogs) {
			requestAnimationFrame(() => {
				if (frontendLogsContainer) {
					frontendLogsContainer.scrollTop = frontendLogsContainer.scrollHeight;
				}
			});
		}
	});

	// Auto-scroll fullscreen frontend logs to bottom when opened or refreshed
	$effect(() => {
		if (frontendLogsFullscreenContainer && frontendLogs.length > 0 && frontendLogsFullscreen) {
			requestAnimationFrame(() => {
				if (frontendLogsFullscreenContainer) {
					frontendLogsFullscreenContainer.scrollTop = frontendLogsFullscreenContainer.scrollHeight;
				}
			});
		}
	});

	// Colorize frontend logs (similar to backend logs but adapted for LogEntry format)
	function colorizedFrontendLogs(): string {
		if (!frontendLogs || frontendLogs.length === 0) return '';

		return frontendLogs
			.map((entry) => {
				// Format timestamp from ISO to match backend format
				const date = new Date(entry.timestamp);
				const timestamp = date.toISOString().replace('T', ' ').substring(0, 19);

				// Get color class based on log level
				let levelClass = 'text-neutral-100 font-semibold';
				switch (entry.level) {
					case 'TRACE':
						levelClass = 'text-cyan-400 font-semibold';
						break;
					case 'DEBUG':
						levelClass = 'text-blue-400 font-semibold';
						break;
					case 'INFO':
						levelClass = 'text-neutral-100 font-semibold';
						break;
					case 'SUCCESS':
						levelClass = 'text-success-500 font-semibold';
						break;
					case 'WARNING':
						levelClass = 'text-warning-500 font-semibold';
						break;
					case 'ERROR':
						levelClass = 'text-error-500 font-semibold';
						break;
					case 'CRITICAL':
						levelClass = 'text-error-700 font-bold';
						break;
				}

				// Pad level to 8 characters for alignment
				const paddedLevel = entry.level.padEnd(8, ' ');

				// Build display message: include error summary (first line only) if present
				let displayMessage = entry.message;
				if (entry.error) {
					// Get first line of error (the error message, not the full stack)
					const errorFirstLine = entry.error.split('\n')[0];
					displayMessage = `${entry.message} [${errorFirstLine}]`;
				}

				// Build colorized line matching Loguru's format
				return (
					`<span class="text-success-500">${escapeHtml(timestamp)}</span> | ` +
					`<span class="${levelClass}">${escapeHtml(paddedLevel)}</span>| ` +
					`<span class="text-cyan-400">${escapeHtml(entry.module)}</span>- ` +
					`<span class="${levelClass}">${escapeHtml(displayMessage)}</span>`
				);
			})
			.join('\n');
	}

	function handleLogout() {
		scanWorkflow.reset();
		resetLocationState();
		authStore.logout();
		goto(resolve('/'));
	}

	async function checkForUpdates() {
		isCheckingUpdates = true;
		updateCheckError = null;
		updateCheckDone = false;

		try {
			const versionResult = await getVersion(true); // Force check for updates

			if (versionResult.update_available && versionResult.latest_version) {
				updateAvailable = true;
				latestVersionNumber = versionResult.latest_version;
			} else {
				updateAvailable = false;
				latestVersionNumber = null;
				updateCheckDone = true; // Show "Up to date" message
				setTimeout(() => {
					updateCheckDone = false;
				}, 5000); // Clear after 5 seconds
			}
		} catch (error) {
			log.error('Failed to check for updates:', error);
			updateCheckError = error instanceof Error ? error.message : 'Failed to check for updates';
		} finally {
			isCheckingUpdates = false;
		}
	}

	async function loadFieldPrefs() {
		if (effectiveDefaults !== null || isLoadingFieldPrefs) {
			showFieldPrefs = !showFieldPrefs;
			return;
		}

		isLoadingFieldPrefs = true;
		fieldPrefsError = null;

		try {
			// Load preferences and effective defaults in parallel (labels already loaded in onMount)
			const [prefsResult, defaultsResult] = await Promise.all([
				fieldPreferences.get(),
				fieldPreferences.getEffectiveDefaults(),
			]);
			prefs = prefsResult;
			effectiveDefaults = defaultsResult;
			showFieldPrefs = true;
		} catch (error) {
			log.error('Failed to load field preferences:', error);
			fieldPrefsError = error instanceof Error ? error.message : 'Failed to load preferences';
		} finally {
			isLoadingFieldPrefs = false;
		}
	}

	async function saveFieldPrefs() {
		saveFieldPrefsState = 'saving';
		fieldPrefsError = null;

		try {
			const result = await fieldPreferences.update(prefs);
			prefs = result;

			// Show success state
			saveFieldPrefsState = 'success';

			// Reset to idle after showing success
			setTimeout(() => {
				saveFieldPrefsState = 'idle';
			}, 2000);
		} catch (error) {
			log.error('Failed to save field preferences:', error);
			fieldPrefsError = error instanceof Error ? error.message : 'Failed to save preferences';
			saveFieldPrefsState = 'error';
			// Reset error state after a delay
			setTimeout(() => {
				saveFieldPrefsState = 'idle';
			}, 3000);
		}
	}

	async function resetFieldPrefs() {
		saveFieldPrefsState = 'saving';
		fieldPrefsError = null;

		try {
			const result = await fieldPreferences.reset();
			prefs = result;
			promptPreview = null; // Clear preview when resetting

			// Show success state
			saveFieldPrefsState = 'success';

			// Reset to idle after showing success
			setTimeout(() => {
				saveFieldPrefsState = 'idle';
			}, 2000);
		} catch (error) {
			log.error('Failed to reset field preferences:', error);
			fieldPrefsError = error instanceof Error ? error.message : 'Failed to reset preferences';
			saveFieldPrefsState = 'error';
			// Reset error state after a delay
			setTimeout(() => {
				saveFieldPrefsState = 'idle';
			}, 3000);
		}
	}

	function handleFieldInput(key: keyof FieldPreferences, value: string) {
		prefs[key] = value.trim() || null;
		promptPreview = null; // Clear preview when editing
	}

	async function loadPromptPreview() {
		// If already showing, just toggle off
		if (showPromptPreview) {
			showPromptPreview = false;
			return;
		}

		// If we have cached preview, just show it
		if (promptPreview) {
			showPromptPreview = true;
			return;
		}

		// Otherwise fetch the preview
		isLoadingPreview = true;

		try {
			const result = await fieldPreferences.getPromptPreview(prefs);
			promptPreview = result.prompt;
			showPromptPreview = true;
		} catch (error) {
			log.error('Failed to load prompt preview:', error);
			fieldPrefsError = error instanceof Error ? error.message : 'Failed to load preview';
		} finally {
			isLoadingPreview = false;
		}
	}

	// Generate env vars string from current preferences
	function generateEnvVars(prefsToExport: FieldPreferences): string {
		const envMapping: Record<keyof FieldPreferences, string> = {
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

		const lines: string[] = [];
		for (const [key, envName] of Object.entries(envMapping)) {
			const value = prefsToExport[key as keyof FieldPreferences];
			if (value) {
				// Escape quotes and wrap in quotes if contains special chars
				const escaped = value.replace(/"/g, '\\"');
				lines.push(`${envName}="${escaped}"`);
			}
		}

		return lines.length > 0 ? lines.join('\n') : '# No customizations configured';
	}

	async function toggleEnvExport() {
		if (showEnvExport) {
			showEnvExport = false;
			return;
		}

		// Fetch fresh prefs for export
		isLoadingExport = true;
		try {
			exportPrefs = await fieldPreferences.get();
			showEnvExport = true;
		} catch (error) {
			log.error('Failed to load preferences for export:', error);
			fieldPrefsError = error instanceof Error ? error.message : 'Failed to load preferences';
		} finally {
			isLoadingExport = false;
		}
	}

	async function copyEnvVars() {
		if (!exportPrefs) return;
		const envVars = generateEnvVars(exportPrefs);
		try {
			await navigator.clipboard.writeText(envVars);
			envCopied = true;
			setTimeout(() => {
				envCopied = false;
			}, 2000);
		} catch (error) {
			log.warn('Failed to copy to clipboard:', error);
		}
	}
</script>

<svelte:head>
	<title>Settings - Homebox Companion</title>
</svelte:head>

<div class="animate-in space-y-6">
	<div>
		<h1 class="text-h1 font-bold text-neutral-100">Settings</h1>
		<p class="mt-1 text-body-sm text-neutral-400">App configuration and information</p>
	</div>

	<!-- About Section -->
	<section class="card space-y-4">
		<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
			<svg
				class="h-5 w-5 text-primary-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<circle cx="12" cy="12" r="10" />
				<line x1="12" y1="16" x2="12" y2="12" />
				<line x1="12" y1="8" x2="12.01" y2="8" />
			</svg>
			About
		</h2>

		<div class="space-y-3">
			<!-- Version -->
			<div class="flex items-center justify-between py-2">
				<span class="text-neutral-400">Version</span>
				<div class="flex items-center gap-2">
					<span class="font-mono text-neutral-100">{uiStore.appVersion || 'Loading...'}</span>
					{#if updateAvailable && latestVersionNumber}
						<a
							href="https://github.com/Duelion/homebox-companion/releases/latest"
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex items-center gap-1 rounded-full bg-warning-500/20 px-2 py-0.5 text-xs text-warning-500 transition-colors hover:bg-warning-500/30"
							title="Click to view release"
						>
							<svg
								class="h-3 w-3"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
								<polyline points="7 10 12 15 17 10" />
								<line x1="12" y1="15" x2="12" y2="3" />
							</svg>
							<span>v{latestVersionNumber}</span>
						</a>
					{:else if updateCheckDone}
						<span
							class="inline-flex items-center gap-1 rounded-full bg-success-500/20 px-2 py-0.5 text-xs text-success-500"
						>
							<svg
								class="h-3 w-3"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<polyline points="20 6 9 17 4 12" />
							</svg>
							<span>Up to date</span>
						</span>
					{/if}
				</div>
			</div>

			<!-- Check for Updates Button -->
			<div class="border-t border-neutral-800 py-2">
				<button
					type="button"
					class="flex w-full items-center justify-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-2.5 text-sm text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100 disabled:cursor-not-allowed disabled:opacity-50"
					onclick={checkForUpdates}
					disabled={isCheckingUpdates}
				>
					{#if isCheckingUpdates}
						<div
							class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
						></div>
						<span>Checking for updates...</span>
					{:else}
						<svg
							class="h-4 w-4"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
						</svg>
						<span>Check for Updates</span>
					{/if}
				</button>
				{#if updateCheckError}
					<p class="mt-2 text-xs text-error-500">
						{updateCheckError}
					</p>
				{/if}
			</div>

			<!-- Configuration Info -->
			{#if config}
				<!-- Homebox URL -->
				<div class="flex items-center justify-between border-t border-neutral-800 py-2">
					<span class="flex-shrink-0 text-neutral-400">Homebox URL</span>
					<div class="flex min-w-0 items-center gap-2">
						<!-- eslint-disable svelte/no-navigation-without-resolve -- External URL, not an app route -->
						<a
							href={config.homebox_url}
							target="_blank"
							rel="noopener noreferrer"
							class="flex max-w-[200px] items-center gap-1 truncate font-mono text-sm text-neutral-100 transition-colors hover:text-primary-400"
							title={config.homebox_url}
						>
							<!-- eslint-enable svelte/no-navigation-without-resolve -->
							<span class="truncate">{config.homebox_url}</span>
							<svg
								class="h-3 w-3 flex-shrink-0 opacity-70"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
								<polyline points="15 3 21 3 21 9" />
								<line x1="10" y1="14" x2="21" y2="3" />
							</svg>
						</a>
						{#if config.is_demo_mode}
							<span
								class="inline-flex flex-shrink-0 items-center gap-1 rounded-full bg-warning-500/20 px-2 py-0.5 text-xs text-warning-500"
							>
								Demo
							</span>
						{/if}
					</div>
				</div>

				<!-- AI Model -->
				<div class="flex items-center justify-between border-t border-neutral-800 py-2">
					<span class="text-neutral-400">AI Model</span>
					<span class="font-mono text-sm text-neutral-100">{config.llm_model}</span>
				</div>

				<!-- Image Quality -->
				<div class="flex items-center justify-between border-t border-neutral-800 py-2">
					<span class="text-neutral-400">Image Quality</span>
					<span class="font-mono text-sm capitalize text-neutral-100">{config.image_quality}</span>
				</div>
			{:else if isLoadingConfig}
				<div class="flex items-center justify-center py-4">
					<div
						class="h-5 w-5 animate-spin rounded-full border-2 border-primary-500 border-t-transparent"
					></div>
				</div>
			{/if}

			<!-- GitHub Link -->
			<div class="space-y-2 border-t border-neutral-800 pt-2">
				<a
					href="https://github.com/Duelion/homebox-companion"
					target="_blank"
					rel="noopener noreferrer"
					class="group flex items-center justify-between py-2 text-neutral-400 transition-colors hover:text-neutral-100"
				>
					<span class="flex items-center gap-2">
						<svg class="h-5 w-5" fill="currentColor" viewBox="0 0 16 16">
							<path
								d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
							/>
						</svg>
						<span>View on GitHub</span>
					</span>
					<svg
						class="h-4 w-4 opacity-50 transition-opacity group-hover:opacity-100"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
						<polyline points="15 3 21 3 21 9" />
						<line x1="10" y1="14" x2="21" y2="3" />
					</svg>
				</a>
				<p class="flex items-start gap-1.5 text-xs text-neutral-500">
					<svg class="mt-0.5 h-3.5 w-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 16 16">
						<path
							d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z"
						/>
					</svg>
					<span>Enjoying the app? Consider giving us a star on GitHub!</span>
				</p>
			</div>
		</div>
	</section>

	<!-- Logs Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
					<polyline points="14 2 14 8 20 8" />
					<line x1="16" y1="13" x2="8" y2="13" />
					<line x1="16" y1="17" x2="8" y2="17" />
					<polyline points="10 9 9 9 8 9" />
				</svg>
				Application Logs
			</h2>
			{#if showLogs && logs}
				<div class="flex items-center gap-1.5">
					<button
						type="button"
						class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
						onclick={refreshLogs}
						disabled={isLoadingLogs}
						title="Refresh logs"
						aria-label="Refresh logs"
					>
						<svg
							class="h-5 w-5 {isLoadingLogs ? 'animate-spin' : ''}"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
						</svg>
					</button>
					<button
						type="button"
						class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
						onclick={handleDownloadLogs}
						disabled={!logs.filename}
						title="Download full log file"
						aria-label="Download logs"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
							<polyline points="7 10 12 15 17 10" />
							<line x1="12" y1="15" x2="12" y2="3" />
						</svg>
					</button>
					<button
						type="button"
						class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
						onclick={() => (logsFullscreen = true)}
						title="Expand fullscreen"
						aria-label="View logs fullscreen"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
						</svg>
					</button>
				</div>
			{/if}
		</div>

		<p class="text-body-sm text-neutral-400">
			View recent application logs for debugging and reference.
		</p>

		<button
			type="button"
			class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
			onclick={loadLogs}
			disabled={isLoadingLogs}
		>
			{#if isLoadingLogs}
				<div
					class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
				></div>
				<span>Loading logs...</span>
			{:else}
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
					<polyline points="14 2 14 8 20 8" />
					<line x1="16" y1="13" x2="8" y2="13" />
					<line x1="16" y1="17" x2="8" y2="17" />
					<polyline points="10 9 9 9 8 9" />
				</svg>
				<span>Show Logs</span>
				<svg
					class="ml-auto h-4 w-4 transition-transform {showLogs ? 'rotate-180' : ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if showLogs}
			{#if logsError}
				<div
					class="rounded-xl border border-error-500/30 bg-error-500/10 p-4 text-sm text-error-500"
				>
					{logsError}
				</div>
			{:else if logs}
				<div class="mt-3 space-y-2">
					{#if logs.filename}
						<div class="flex items-center justify-between text-xs text-neutral-500">
							<span>{logs.filename}</span>
							<span>
								{logs.truncated
									? `Last ${logs.total_lines > 300 ? 300 : logs.total_lines} of ${logs.total_lines}`
									: `${logs.total_lines}`} lines
							</span>
						</div>
					{/if}
					<div class="overflow-hidden rounded-xl border border-neutral-700 bg-neutral-950">
						<!-- eslint-disable svelte/no-at-html-tags -- Colorized log output from trusted server data -->
						<pre
							bind:this={logsContainer}
							class="max-h-80 overflow-x-auto overflow-y-auto whitespace-pre-wrap break-all p-4 font-mono text-xs text-neutral-400">{@html colorizedLogs()}</pre>
						<!-- eslint-enable svelte/no-at-html-tags -->
					</div>
				</div>
			{/if}
		{/if}
	</section>

	<!-- Frontend Logs Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
					/>
				</svg>
				Frontend Logs
			</h2>
			{#if showFrontendLogs && frontendLogs.length > 0}
				<div class="flex items-center gap-1.5">
					<button
						type="button"
						class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
						onclick={refreshFrontendLogs}
						title="Refresh logs"
						aria-label="Refresh logs"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
						</svg>
					</button>
					<button
						type="button"
						class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
						onclick={handleExportFrontendLogs}
						title="Export as JSON"
						aria-label="Export logs"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
							<polyline points="7 10 12 15 17 10" />
							<line x1="12" y1="15" x2="12" y2="3" />
						</svg>
					</button>
					<button
						type="button"
						class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
						onclick={handleClearFrontendLogs}
						title="Clear logs"
						aria-label="Clear logs"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
							/>
						</svg>
					</button>
					<button
						type="button"
						class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
						onclick={() => (frontendLogsFullscreen = true)}
						title="Expand fullscreen"
						aria-label="View logs fullscreen"
					>
						<svg
							class="h-5 w-5"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
						</svg>
					</button>
				</div>
			{/if}
		</div>

		<p class="text-body-sm text-neutral-400">
			View browser console logs stored in memory. Logs are cleared on page refresh.
		</p>

		<button
			type="button"
			class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
			onclick={loadFrontendLogs}
		>
			<svg
				class="h-5 w-5 text-primary-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
				/>
			</svg>
			<span>Show Frontend Logs</span>
			<svg
				class="ml-auto h-4 w-4 transition-transform {showFrontendLogs ? 'rotate-180' : ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<polyline points="6 9 12 15 18 9" />
			</svg>
		</button>

		{#if showFrontendLogs}
			{#if frontendLogs.length === 0}
				<div
					class="rounded-xl border border-neutral-700 bg-neutral-800/50 p-4 text-center text-sm text-neutral-400"
				>
					No frontend logs available. Logs will appear here as you use the app.
				</div>
			{:else}
				<div class="mt-3 space-y-2">
					<div class="flex items-center justify-between text-xs text-neutral-500">
						<span>In-memory buffer</span>
						<span
							>{frontendLogs.length}
							{frontendLogs.length === 1 ? 'entry' : 'entries'}</span
						>
					</div>
					<div class="overflow-hidden rounded-xl border border-neutral-700 bg-neutral-950">
						<!-- eslint-disable svelte/no-at-html-tags -- Colorized log output from trusted local storage -->
						<pre
							bind:this={frontendLogsContainer}
							class="max-h-80 overflow-x-auto overflow-y-auto whitespace-pre-wrap break-all p-4 font-mono text-xs text-neutral-400">{@html colorizedFrontendLogs()}</pre>
						<!-- eslint-enable svelte/no-at-html-tags -->
					</div>
				</div>
			{/if}
		{/if}
	</section>

	<!-- AI Output Configuration Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4"
					/>
				</svg>
				Configure AI Output
			</h2>
			{#if showFieldPrefs && saveFieldPrefsState === 'success'}
				<span
					class="inline-flex items-center gap-2 rounded-full bg-success-500/20 px-3 py-1.5 text-sm font-medium text-success-500"
				>
					<svg
						class="h-4 w-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2.5"
					>
						<polyline points="20 6 9 17 4 12" />
					</svg>
					Saved
				</span>
			{/if}
		</div>

		<p class="text-body-sm text-neutral-400">
			Customize how the AI generates item data. Leave fields empty to use default behavior.
		</p>

		<button
			type="button"
			class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
			onclick={loadFieldPrefs}
			disabled={isLoadingFieldPrefs}
		>
			{#if isLoadingFieldPrefs}
				<div
					class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
				></div>
				<span>Loading...</span>
			{:else}
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4"
					/>
				</svg>
				<span>Configure Fields</span>
				<svg
					class="ml-auto h-4 w-4 transition-transform {showFieldPrefs ? 'rotate-180' : ''}"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if showFieldPrefs}
			{#if fieldPrefsError}
				<div
					class="rounded-xl border border-error-500/30 bg-error-500/10 p-4 text-sm text-error-500"
				>
					{fieldPrefsError}
				</div>
			{/if}

			<!-- Output Language Setting -->
			<div class="space-y-3 rounded-xl border border-primary-500/20 bg-primary-600/10 p-4">
				<div class="flex items-center gap-2">
					<svg
						class="h-5 w-5 text-primary-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"
						/>
					</svg>
					<label for="output_language" class="font-semibold text-neutral-100">Output Language</label
					>
				</div>
				<p class="text-xs text-neutral-400">
					Choose what language the AI should use for item names, descriptions, and notes.
				</p>
				<input
					type="text"
					id="output_language"
					value={prefs.output_language || ''}
					oninput={(e) => handleFieldInput('output_language', e.currentTarget.value)}
					placeholder={effectiveDefaults ? effectiveDefaults.output_language : 'Loading...'}
					class="input"
				/>
				<div class="rounded-lg border border-warning-500/30 bg-warning-500/10 p-2">
					<p class="flex items-start gap-2 text-xs text-warning-500">
						<svg
							class="mt-0.5 h-4 w-4 flex-shrink-0"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<path
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
							/>
						</svg>
						<span
							><strong>Note:</strong> Field customization instructions below should still be written in
							English. Only the AI output will be in the configured language.</span
						>
					</p>
				</div>
			</div>

			<!-- Default Label Setting -->
			<div class="space-y-3 rounded-xl border border-primary-500/20 bg-primary-600/10 p-4">
				<div class="flex items-center gap-2">
					<svg
						class="h-5 w-5 text-primary-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
						/>
					</svg>
					<label for="default_label" class="font-semibold text-neutral-100">Default Label</label>
				</div>
				<p class="text-xs text-neutral-400">
					Automatically tag all items created via Homebox Companion with this label.
				</p>
				<select
					id="default_label"
					value={prefs.default_label_id || ''}
					onchange={(e) => {
						prefs.default_label_id = e.currentTarget.value || null;
					}}
					class="input"
				>
					<option value="">No default label</option>
					{#each availableLabels as label (label.id)}
						<option value={label.id}
							>{label.name}{effectiveDefaults?.default_label_id === label.id
								? ' (env default)'
								: ''}</option
						>
					{/each}
				</select>
				<p class="text-xs text-neutral-500">
					Useful for identifying items added through this app in your Homebox inventory.
				</p>
			</div>

			<!-- Field Customizations - 2-column grid on wider screens -->
			<div class="grid gap-4 sm:grid-cols-2">
				{#each fieldMeta as field (field.key)}
					<div class="space-y-2 rounded-lg border border-neutral-700/50 bg-neutral-800/50 p-3">
						<label for={field.key} class="block text-sm font-semibold text-neutral-100">
							{field.label}
						</label>
						<div
							class="rounded border border-neutral-700/30 bg-neutral-950/50 px-2 py-1.5 text-xs text-neutral-400"
						>
							<span class="text-neutral-500">Default:</span>
							{effectiveDefaults?.[field.key] ?? 'Loading...'}
						</div>
						<input
							type="text"
							id={field.key}
							value={prefs[field.key] || ''}
							oninput={(e) => handleFieldInput(field.key, e.currentTarget.value)}
							placeholder="Leave empty for default..."
							class="input text-sm"
						/>
						<p class="line-clamp-2 text-xs text-neutral-500">
							Example: {field.example}
						</p>
					</div>
				{/each}
			</div>

			<div class="flex gap-3 pt-2">
				<Button
					variant="primary"
					onclick={saveFieldPrefs}
					disabled={saveFieldPrefsState === 'saving' || saveFieldPrefsState === 'success'}
				>
					{#if saveFieldPrefsState === 'saving'}
						<div
							class="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"
						></div>
						<span>Saving...</span>
					{:else if saveFieldPrefsState === 'success'}
						<div class="flex h-8 w-8 items-center justify-center rounded-full bg-success-500/20">
							<svg
								class="h-5 w-5 text-success-500"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2.5"
							>
								<polyline points="20 6 9 17 4 12" />
							</svg>
						</div>
						<span>Saved!</span>
					{:else}
						<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M5 13l4 4L19 7"
							/>
						</svg>
						<span>Save</span>
					{/if}
				</Button>
				<Button
					variant="secondary"
					onclick={resetFieldPrefs}
					disabled={saveFieldPrefsState === 'saving' || saveFieldPrefsState === 'success'}
				>
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						/>
					</svg>
					<span>Reset</span>
				</Button>
			</div>
		{/if}

		<!-- Docker Persistence Warning & Export - Moved up for visibility -->
		<div class="space-y-3 rounded-xl border border-warning-500/30 bg-warning-500/10 p-4">
			<div class="flex items-start gap-2">
				<svg
					class="mt-0.5 h-5 w-5 flex-shrink-0 text-warning-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				<div>
					<p class="mb-1 text-sm font-medium text-warning-500">Docker users</p>
					<p class="text-xs text-neutral-400">
						Customizations are stored in a config file that may be lost when updating your
						container. Export as environment variables to persist settings.
					</p>
				</div>
			</div>

			<button
				type="button"
				class="flex w-full items-center justify-center gap-2 rounded-lg border border-warning-500/30 bg-warning-500/20 px-4 py-2.5 text-sm font-medium text-warning-500 transition-all hover:bg-warning-500/30"
				onclick={toggleEnvExport}
				disabled={isLoadingExport}
			>
				{#if isLoadingExport}
					<div
						class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
					></div>
					<span>Loading...</span>
				{:else}
					<svg
						class="h-4 w-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
						/>
					</svg>
					<span>Export as Environment Variables</span>
				{/if}
			</button>
		</div>

		{#if showEnvExport && exportPrefs}
			<div class="space-y-2">
				<div class="flex items-center justify-between">
					<span class="text-xs font-medium text-neutral-400"
						>Add these to your docker-compose.yml or .env file</span
					>
					<button
						type="button"
						class="flex min-h-[36px] items-center gap-1 rounded-lg bg-primary-600/20 px-3 py-1.5 text-xs text-primary-400 transition-colors hover:bg-primary-600/30"
						onclick={copyEnvVars}
						aria-label="Copy environment variables"
					>
						{#if envCopied}
							<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<polyline points="20 6 9 17 4 12" />
							</svg>
							<span>Copied!</span>
						{:else}
							<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
								<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
							</svg>
							<span>Copy</span>
						{/if}
					</button>
				</div>
				<div class="overflow-hidden rounded-xl border border-neutral-700 bg-neutral-950">
					<pre
						class="overflow-x-auto whitespace-pre-wrap break-words p-4 font-mono text-xs text-neutral-400">{generateEnvVars(
							exportPrefs
						)}</pre>
				</div>
			</div>
		{/if}

		<!-- Prompt Preview Section -->
		<div class="border-t border-neutral-800 pt-4">
			<button
				type="button"
				class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
				onclick={loadPromptPreview}
				disabled={isLoadingPreview}
			>
				{#if isLoadingPreview}
					<div
						class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
					></div>
					<span>Generating preview...</span>
				{:else}
					<svg
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
						<path
							d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z"
						/>
					</svg>
					<span>Preview AI Prompt</span>
					<svg
						class="ml-auto h-4 w-4 transition-transform {showPromptPreview ? 'rotate-180' : ''}"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<polyline points="6 9 12 15 18 9" />
					</svg>
				{/if}
			</button>

			{#if showPromptPreview && promptPreview}
				<div class="mt-3 space-y-2">
					<div class="flex items-center justify-between">
						<span class="text-xs font-medium text-neutral-400">System Prompt Preview</span>
						<button
							type="button"
							class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
							onclick={() => (promptFullscreen = true)}
							title="Expand fullscreen"
							aria-label="View prompt fullscreen"
						>
							<svg
								class="h-5 w-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
							</svg>
						</button>
					</div>
					<div class="overflow-hidden rounded-xl border border-neutral-700 bg-neutral-950">
						<pre
							class="max-h-80 overflow-x-auto overflow-y-auto whitespace-pre-wrap break-words p-4 font-mono text-xs text-neutral-400">{promptPreview}</pre>
					</div>
					<p class="text-xs text-neutral-500">
						This is what the AI will see when analyzing your images. Labels shown are examples;
						actual labels from your Homebox instance will be used.
					</p>
				</div>
			{/if}
		</div>
	</section>

	<!-- Account Section -->
	<section class="card space-y-4">
		<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
			<svg
				class="h-5 w-5 text-primary-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
				<circle cx="12" cy="7" r="4" />
			</svg>
			Account
		</h2>

		<Button variant="danger" full onclick={handleLogout}>
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
				<polyline points="16 17 21 12 16 7" />
				<line x1="21" y1="12" x2="9" y2="12" />
			</svg>
			<span>Sign Out</span>
		</Button>
	</section>

	<!-- Bottom spacing for nav -->
	<div class="h-4"></div>
</div>

<!-- Fullscreen Logs Modal -->
{#if logsFullscreen && logs}
	<div class="fixed inset-0 z-[60] flex flex-col bg-neutral-950">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-neutral-700 bg-neutral-900 p-4">
			<div class="flex items-center gap-3">
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
					<polyline points="14 2 14 8 20 8" />
					<line x1="16" y1="13" x2="8" y2="13" />
					<line x1="16" y1="17" x2="8" y2="17" />
					<polyline points="10 9 9 9 8 9" />
				</svg>
				<div>
					<h2 class="text-body-lg font-semibold text-neutral-100">Application Logs</h2>
					{#if logs.filename}
						<p class="text-xs text-neutral-500">
							{logs.filename} • {logs.truncated
								? `Last ${logs.total_lines > 300 ? 300 : logs.total_lines} of ${logs.total_lines}`
								: logs.total_lines} lines
						</p>
					{/if}
				</div>
			</div>
			<div class="flex items-center gap-2">
				<button
					type="button"
					class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
					onclick={refreshLogs}
					disabled={isLoadingLogs}
					title="Refresh logs"
					aria-label="Refresh logs"
				>
					<svg
						class="h-5 w-5 {isLoadingLogs ? 'animate-spin' : ''}"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path d="M23 4v6h-6M1 20v-6h6" />
						<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
					</svg>
				</button>
				<button
					type="button"
					class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
					onclick={handleDownloadLogs}
					disabled={!logs.filename}
					title="Download full log file"
					aria-label="Download logs"
				>
					<svg
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
						<polyline points="7 10 12 15 17 10" />
						<line x1="12" y1="15" x2="12" y2="3" />
					</svg>
				</button>
				<button
					type="button"
					class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
					onclick={() => (logsFullscreen = false)}
					title="Close fullscreen"
					aria-label="Close"
				>
					<svg
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path d="M18 6L6 18M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>
		<!-- Content -->
		<div bind:this={logsFullscreenContainer} class="flex-1 overflow-auto p-4 pb-24">
			<!-- eslint-disable svelte/no-at-html-tags -- Colorized log output from trusted server data -->
			<pre
				class="whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-neutral-400">{@html colorizedLogs()}</pre>
			<!-- eslint-enable svelte/no-at-html-tags -->
		</div>
	</div>
{/if}

<!-- Fullscreen Prompt Preview Modal -->
{#if promptFullscreen && promptPreview}
	<div class="fixed inset-0 z-[60] flex flex-col bg-neutral-950">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-neutral-700 bg-neutral-900 p-4">
			<div class="flex items-center gap-3">
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
					<path
						d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z"
					/>
				</svg>
				<div>
					<h2 class="text-body-lg font-semibold text-neutral-100">AI System Prompt</h2>
					<p class="text-xs text-neutral-500">
						This is what the AI sees when analyzing your images
					</p>
				</div>
			</div>
			<button
				type="button"
				class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
				onclick={() => (promptFullscreen = false)}
				title="Close fullscreen"
				aria-label="Close"
			>
				<svg
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M18 6L6 18M6 6l12 12" />
				</svg>
			</button>
		</div>
		<!-- Content -->
		<div class="flex-1 overflow-auto p-4 pb-24">
			<pre
				class="whitespace-pre-wrap break-words font-mono text-sm leading-relaxed text-neutral-400">{promptPreview}</pre>
		</div>
	</div>
{/if}

<!-- Fullscreen Frontend Logs Modal -->
{#if frontendLogsFullscreen && frontendLogs.length > 0}
	<div class="fixed inset-0 z-[60] flex flex-col bg-neutral-950">
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-neutral-700 bg-neutral-900 p-4">
			<div class="flex items-center gap-3">
				<svg
					class="h-5 w-5 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
					/>
				</svg>
				<div>
					<h2 class="text-body-lg font-semibold text-neutral-100">Frontend Logs</h2>
					<p class="text-xs text-neutral-500">
						In-memory buffer • {frontendLogs.length}
						{frontendLogs.length === 1 ? 'entry' : 'entries'}
					</p>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<button
					type="button"
					class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
					onclick={refreshFrontendLogs}
					title="Refresh logs"
					aria-label="Refresh logs"
				>
					<svg
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path d="M23 4v6h-6M1 20v-6h6" />
						<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
					</svg>
				</button>
				<button
					type="button"
					class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
					onclick={handleExportFrontendLogs}
					title="Export as JSON"
					aria-label="Export logs"
				>
					<svg
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
						<polyline points="7 10 12 15 17 10" />
						<line x1="12" y1="15" x2="12" y2="3" />
					</svg>
				</button>
				<button
					type="button"
					class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
					onclick={handleClearFrontendLogs}
					title="Clear logs"
					aria-label="Clear logs"
				>
					<svg
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
						/>
					</svg>
				</button>
				<button
					type="button"
					class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-100"
					onclick={() => (frontendLogsFullscreen = false)}
					title="Close fullscreen"
					aria-label="Close"
				>
					<svg
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path d="M18 6L6 18M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>
		<!-- Content -->
		<div bind:this={frontendLogsFullscreenContainer} class="flex-1 overflow-auto p-4 pb-24">
			<!-- eslint-disable svelte/no-at-html-tags -- Colorized log output from trusted local storage -->
			<pre
				class="whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-neutral-400">{@html colorizedFrontendLogs()}</pre>
			<!-- eslint-enable svelte/no-at-html-tags -->
		</div>
	</div>
{/if}
