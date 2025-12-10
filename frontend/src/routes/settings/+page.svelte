<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { isAuthenticated, logout } from '$lib/stores/auth';
	import { resetLocationState } from '$lib/stores/locations';
	import { appVersion } from '$lib/stores/ui';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { getConfig, getLogs, downloadLogs, getVersion, labels as labelsApi, fieldPreferences, type ConfigResponse, type LogsResponse, type FieldPreferences, type EffectiveDefaults, type LabelData } from '$lib/api';
	import Button from '$lib/components/Button.svelte';

	let config = $state<ConfigResponse | null>(null);
	let logs = $state<LogsResponse | null>(null);
	let isLoadingConfig = $state(true);
	let isLoadingLogs = $state(false);
	let showLogs = $state(false);
	let logsError = $state<string | null>(null);
	let logsContainer = $state<HTMLPreElement | null>(null);
	let logsFullscreenContainer = $state<HTMLDivElement | null>(null);

	// Version update state (fetched with force_check to always show updates)
	let updateAvailable = $state(false);
	let latestVersionNumber = $state<string | null>(null);

	// Field preferences state
	let showFieldPrefs = $state(false);
	let isLoadingFieldPrefs = $state(false);
	let isSavingFieldPrefs = $state(false);
	let fieldPrefsError = $state<string | null>(null);
	let fieldPrefsSaved = $state(false);
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
	const fieldMeta: Array<{ key: keyof FieldPreferences; label: string; example: string }> = [
		{
			key: 'name',
			label: 'Name',
			example: '"Ball Bearing 6900-2RS 10x22x6mm", "LED Strip COB Green 5V 1M"'
		},
		{
			key: 'naming_examples',
			label: 'Naming Examples',
			example: 'Comma-separated examples that show the AI how to format names'
		},
		{
			key: 'description',
			label: 'Description',
			example: '"Minor scratches on casing", "New in packaging"'
		},
		{
			key: 'quantity',
			label: 'Quantity',
			example: '5 identical screws = qty 5, but 2 sizes = 2 separate items'
		},
		{
			key: 'manufacturer',
			label: 'Manufacturer',
			example: 'DeWalt, Vallejo (NOT "Shenzhen XYZ Technology Co.")'
		},
		{
			key: 'model_number',
			label: 'Model Number',
			example: '"DCD771C2", "72.034"'
		},
		{
			key: 'serial_number',
			label: 'Serial Number',
			example: 'Look for "S/N:", "Serial:" markings'
		},
		{
			key: 'purchase_price',
			label: 'Purchase Price',
			example: '29.99 (not "$29.99")'
		},
		{
			key: 'purchase_from',
			label: 'Purchase From',
			example: '"Amazon", "Home Depot"'
		},
		{
			key: 'notes',
			label: 'Notes',
			example: 'For defects/warnings only. Include GOOD/BAD examples for clarity.'
		},
	];

	// Redirect if not authenticated
	onMount(async () => {
		if (!$isAuthenticated) {
			goto('/');
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
			availableLabels = labelsResult; // Cache for later use

			// Set update info
			if (versionResult.update_available && versionResult.latest_version) {
				updateAvailable = true;
				latestVersionNumber = versionResult.latest_version;
			}
		} catch (error) {
			// If it's a 401, the session expired modal will already be shown
			console.error('Failed to load settings data:', error);
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
			console.error('Failed to load logs:', error);
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
			console.error('Failed to refresh logs:', error);
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
			console.error('Failed to download logs:', error);
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
			.map(line => {
				// Match the log format: timestamp | level | location - message
				const match = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s*\| ([^-]+)- (.*)$/);
				
				if (!match) {
					// Line doesn't match format, return escaped
					return escapeHtml(line);
				}
				
				const [, timestamp, level, location, message] = match;
				const levelTrimmed = level.trim();
				
				// Get color class based on log level (matching Loguru's default color scheme)
				// https://github.com/Delgan/loguru/blob/master/loguru/_defaults.py
				let levelClass = 'text-text font-semibold'; // Default: bold white (INFO)
				switch (levelTrimmed) {
					case 'TRACE':
						levelClass = 'text-cyan-400 font-semibold';
						break;
					case 'DEBUG':
						levelClass = 'text-blue-400 font-semibold';
						break;
					case 'INFO':
						levelClass = 'text-text font-semibold';
						break;
					case 'SUCCESS':
						levelClass = 'text-green-400 font-semibold';
						break;
					case 'WARNING':
						levelClass = 'text-yellow-400 font-semibold';
						break;
					case 'ERROR':
						levelClass = 'text-red-400 font-semibold';
						break;
					case 'CRITICAL':
						levelClass = 'text-red-500 font-bold';
						break;
				}
				
				// Build colorized line matching Loguru's format:
				// <green>timestamp</green> | <level>LEVEL</level> | <cyan>location</cyan> - <level>message</level>
				return `<span class="text-green-400">${escapeHtml(timestamp)}</span> | ` +
					`<span class="${levelClass}">${escapeHtml(level)}</span>| ` +
					`<span class="text-cyan-400">${escapeHtml(location)}</span>- ` +
					`<span class="${levelClass}">${escapeHtml(message)}</span>`;
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

	function handleLogout() {
		scanWorkflow.reset();
		resetLocationState();
		logout();
		goto('/');
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
			console.error('Failed to load field preferences:', error);
			fieldPrefsError = error instanceof Error ? error.message : 'Failed to load preferences';
		} finally {
			isLoadingFieldPrefs = false;
		}
	}

	async function saveFieldPrefs() {
		isSavingFieldPrefs = true;
		fieldPrefsError = null;
		fieldPrefsSaved = false;

		try {
			const result = await fieldPreferences.update(prefs);
			prefs = result;
			fieldPrefsSaved = true;
			setTimeout(() => { fieldPrefsSaved = false; }, 2000);
		} catch (error) {
			console.error('Failed to save field preferences:', error);
			fieldPrefsError = error instanceof Error ? error.message : 'Failed to save preferences';
		} finally {
			isSavingFieldPrefs = false;
		}
	}

	async function resetFieldPrefs() {
		isSavingFieldPrefs = true;
		fieldPrefsError = null;

		try {
			const result = await fieldPreferences.reset();
			prefs = result;
			fieldPrefsSaved = true;
			promptPreview = null; // Clear preview when resetting
			setTimeout(() => { fieldPrefsSaved = false; }, 2000);
		} catch (error) {
			console.error('Failed to reset field preferences:', error);
			fieldPrefsError = error instanceof Error ? error.message : 'Failed to reset preferences';
		} finally {
			isSavingFieldPrefs = false;
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
			console.error('Failed to load prompt preview:', error);
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
			console.error('Failed to load preferences for export:', error);
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
			setTimeout(() => { envCopied = false; }, 2000);
		} catch (error) {
			console.error('Failed to copy to clipboard:', error);
		}
	}
</script>

<svelte:head>
	<title>Settings - Homebox Companion</title>
</svelte:head>

<div class="animate-in space-y-6">
	<div>
		<h1 class="text-2xl font-bold text-text">Settings</h1>
		<p class="text-text-muted text-sm mt-1">App configuration and information</p>
	</div>

	<!-- About Section -->
	<section class="card space-y-4">
		<h2 class="text-lg font-semibold text-text flex items-center gap-2">
			<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<circle cx="12" cy="12" r="10" />
				<line x1="12" y1="16" x2="12" y2="12" />
				<line x1="12" y1="8" x2="12.01" y2="8" />
			</svg>
			About
		</h2>

		<div class="space-y-3">
			<!-- Version -->
			<div class="flex items-center justify-between py-2">
				<span class="text-text-muted">Version</span>
				<div class="flex items-center gap-2">
					<span class="text-text font-mono">{$appVersion || 'Loading...'}</span>
					{#if updateAvailable && latestVersionNumber}
						<a
							href="https://github.com/Duelion/homebox-companion/releases/latest"
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-500/20 text-amber-300 rounded-full text-xs hover:bg-amber-500/30 transition-colors"
							title="Click to view release"
						>
							<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
								<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
								<polyline points="7 10 12 15 17 10" />
								<line x1="12" y1="15" x2="12" y2="3" />
							</svg>
							<span>v{latestVersionNumber}</span>
						</a>
					{/if}
				</div>
			</div>

			<!-- AI Model -->
			{#if config}
				<div class="flex items-center justify-between py-2 border-t border-border/20">
					<span class="text-text-muted">AI Model</span>
					<span class="text-text font-mono text-sm">{config.openai_model}</span>
				</div>
			{:else if isLoadingConfig}
				<div class="flex items-center justify-center py-4">
					<div class="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
				</div>
			{/if}

			<!-- GitHub Link -->
			<div class="pt-2 border-t border-border/20">
				<a
					href="https://github.com/Duelion/homebox-companion"
					target="_blank"
					rel="noopener noreferrer"
					class="flex items-center justify-between py-2 text-text-muted hover:text-text transition-colors group"
				>
					<span class="flex items-center gap-2">
						<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 16 16">
							<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
						</svg>
						<span>View on GitHub</span>
					</span>
					<svg class="w-4 h-4 opacity-50 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
						<polyline points="15 3 21 3 21 9" />
						<line x1="10" y1="14" x2="21" y2="3" />
					</svg>
				</a>
			</div>
		</div>
	</section>

	<!-- Logs Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2 class="text-lg font-semibold text-text flex items-center gap-2">
				<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
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
						class="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-all"
						onclick={refreshLogs}
						disabled={isLoadingLogs}
						title="Refresh logs"
					>
						<svg
							class="w-4 h-4 {isLoadingLogs ? 'animate-spin' : ''}"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="2"
						>
							<path d="M23 4v6h-6M1 20v-6h6" />
							<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
						</svg>
					</button>
					<button
						type="button"
						class="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-all"
						onclick={handleDownloadLogs}
						disabled={!logs.filename}
						title="Download full log file"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
							<polyline points="7 10 12 15 17 10" />
							<line x1="12" y1="15" x2="12" y2="3" />
						</svg>
					</button>
					<button
						type="button"
						class="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-all"
						onclick={() => (logsFullscreen = true)}
						title="Expand fullscreen"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
						</svg>
					</button>
				</div>
			{/if}
		</div>

	<p class="text-sm text-text-muted">
		View recent application logs for debugging and reference.
	</p>

	<button
		type="button"
		class="w-full py-3 px-4 bg-surface-elevated/50 hover:bg-surface-hover border border-border rounded-xl text-text-muted hover:text-text transition-all flex items-center gap-2"
		onclick={loadLogs}
		disabled={isLoadingLogs}
	>
		{#if isLoadingLogs}
			<div class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
			<span>Loading logs...</span>
		{:else}
			<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
				<polyline points="14 2 14 8 20 8" />
				<line x1="16" y1="13" x2="8" y2="13" />
				<line x1="16" y1="17" x2="8" y2="17" />
				<polyline points="10 9 9 9 8 9" />
			</svg>
			<span>Show Logs</span>
			<svg class="w-4 h-4 ml-auto transition-transform {showLogs ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<polyline points="6 9 12 15 18 9" />
			</svg>
		{/if}
	</button>

	{#if showLogs}
		{#if logsError}
			<div class="p-4 bg-danger/10 border border-danger/30 rounded-xl text-danger text-sm">
				{logsError}
			</div>
		{:else if logs}
			<div class="mt-3 space-y-2">
				{#if logs.filename}
					<div class="flex items-center justify-between text-xs text-text-dim">
						<span>{logs.filename}</span>
						<span>
							{logs.truncated ? `Last ${logs.total_lines > 300 ? 300 : logs.total_lines} of ${logs.total_lines}` : `${logs.total_lines}`} lines
						</span>
					</div>
				{/if}
				<div class="bg-background rounded-xl border border-border overflow-hidden">
					<pre bind:this={logsContainer} class="p-4 text-xs font-mono text-text-muted overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap break-all">{@html colorizedLogs()}</pre>
				</div>
			</div>
		{/if}
	{/if}
	</section>

	<!-- AI Output Configuration Section -->
	<section class="card space-y-4">
		<div class="flex items-center justify-between">
			<h2 class="text-lg font-semibold text-text flex items-center gap-2">
				<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4" />
				</svg>
				Configure AI Output
			</h2>
			{#if showFieldPrefs && fieldPrefsSaved}
				<span class="text-sm text-success flex items-center gap-1">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
					</svg>
					Saved
				</span>
			{/if}
		</div>

	<p class="text-sm text-text-muted">
		Customize how the AI generates item data. Leave fields empty to use default behavior.
	</p>

	<button
		type="button"
		class="w-full py-3 px-4 bg-surface-elevated/50 hover:bg-surface-hover border border-border rounded-xl text-text-muted hover:text-text transition-all flex items-center gap-2"
		onclick={loadFieldPrefs}
		disabled={isLoadingFieldPrefs}
	>
		{#if isLoadingFieldPrefs}
			<div class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
			<span>Loading...</span>
		{:else}
			<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M12 6V4m0 2a2 2 0 1 0 0 4m0-4a2 2 0 1 1 0 4m-6 8a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 1 0 0-4m0 4a2 2 0 1 1 0-4m0 4v2m0-6V4" />
			</svg>
			<span>Configure Fields</span>
			<svg class="w-4 h-4 ml-auto transition-transform {showFieldPrefs ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<polyline points="6 9 12 15 18 9" />
			</svg>
		{/if}
	</button>

	{#if showFieldPrefs}
		{#if fieldPrefsError}
			<div class="p-4 bg-danger/10 border border-danger/30 rounded-xl text-danger text-sm">
				{fieldPrefsError}
			</div>
		{/if}

		<!-- Output Language Setting -->
		<div class="p-4 bg-primary/5 rounded-xl border border-primary/20 space-y-3">
			<div class="flex items-center gap-2">
				<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
				</svg>
				<label for="output_language" class="font-semibold text-text">Output Language</label>
			</div>
			<p class="text-xs text-text-muted">
				Choose what language the AI should use for item names, descriptions, and notes.
			</p>
			<input
				type="text"
				id="output_language"
				value={prefs.output_language || ''}
				oninput={(e) => handleFieldInput('output_language', e.currentTarget.value)}
				placeholder={effectiveDefaults ? effectiveDefaults.output_language : 'Loading...'}
				class="w-full px-3 py-2 bg-background border border-border rounded-lg text-text placeholder-text-dim text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
			/>
			<div class="p-2 bg-amber-500/10 border border-amber-500/30 rounded-lg">
				<p class="text-xs text-amber-200 flex items-start gap-2">
					<svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
						<path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
					<span><strong>Note:</strong> Field customization instructions below should still be written in English. Only the AI output will be in the configured language.</span>
				</p>
			</div>
		</div>

		<!-- Default Label Setting -->
		<div class="p-4 bg-primary/5 rounded-xl border border-primary/20 space-y-3">
			<div class="flex items-center gap-2">
				<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
				</svg>
				<label for="default_label" class="font-semibold text-text">Default Label</label>
			</div>
			<p class="text-xs text-text-muted">
				Automatically tag all items created via Homebox Companion with this label.
			</p>
			<select
				id="default_label"
				value={prefs.default_label_id || ''}
				onchange={(e) => { prefs.default_label_id = e.currentTarget.value || null; }}
				class="w-full px-3 py-2 bg-background border border-border rounded-lg text-text text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
			>
				<option value="">No default label</option>
				{#each availableLabels as label}
					<option value={label.id}>{label.name}{effectiveDefaults?.default_label_id === label.id ? ' (env default)' : ''}</option>
				{/each}
			</select>
			<p class="text-xs text-text-dim">
				Useful for identifying items added through this app in your Homebox inventory.
			</p>
		</div>

		<!-- Field Customizations -->
		<div class="space-y-4">
			{#each fieldMeta as field}
					<div class="p-3 bg-surface-elevated/50 rounded-lg border border-border/50 space-y-2">
						<label for={field.key} class="block text-sm font-semibold text-text">
							{field.label}
						</label>
						<div class="text-xs text-text-muted bg-background/50 px-2 py-1.5 rounded border border-border/30">
							<span class="text-text-dim">Default:</span> {effectiveDefaults?.[field.key] ?? 'Loading...'}
						</div>
						<input
							type="text"
							id={field.key}
							value={prefs[field.key] || ''}
							oninput={(e) => handleFieldInput(field.key, e.currentTarget.value)}
							placeholder="Leave empty to use default, or type custom instruction..."
							class="w-full px-3 py-2 bg-background border border-border rounded-lg text-text placeholder-text-dim text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
						/>
						<p class="text-xs text-text-dim">Example: {field.example}</p>
					</div>
				{/each}
			</div>

			<div class="flex gap-3 pt-2">
				<Button
					variant="primary"
					onclick={saveFieldPrefs}
					disabled={isSavingFieldPrefs}
				>
					{#if isSavingFieldPrefs}
						<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
					{:else}
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
						</svg>
					{/if}
					<span>Save</span>
				</Button>
				<Button
					variant="secondary"
					onclick={resetFieldPrefs}
					disabled={isSavingFieldPrefs}
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
					</svg>
					<span>Reset to Defaults</span>
				</Button>
			</div>
		{/if}

		<!-- Prompt Preview Section - Always visible at section level -->
		<div class="pt-4 border-t border-border/20">
			<button
				type="button"
				class="w-full py-3 px-4 bg-surface-elevated/50 hover:bg-surface-hover border border-border rounded-xl text-text-muted hover:text-text transition-all flex items-center gap-2"
				onclick={loadPromptPreview}
				disabled={isLoadingPreview}
			>
				{#if isLoadingPreview}
					<div class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
					<span>Generating preview...</span>
				{:else}
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
						<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
						<path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z" />
					</svg>
					<span>Preview AI Prompt</span>
					<svg class="w-4 h-4 ml-auto transition-transform {showPromptPreview ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<polyline points="6 9 12 15 18 9" />
					</svg>
				{/if}
			</button>

		{#if showPromptPreview && promptPreview}
			<div class="mt-3 space-y-2">
				<div class="flex items-center justify-between">
					<span class="text-xs text-text-muted font-medium">System Prompt Preview</span>
					<button
						type="button"
						class="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-all"
						onclick={() => (promptFullscreen = true)}
						title="Expand fullscreen"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
							<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
						</svg>
					</button>
				</div>
				<div class="bg-background rounded-xl border border-border overflow-hidden">
					<pre class="p-4 text-xs font-mono text-text-muted overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap break-words">{promptPreview}</pre>
				</div>
				<p class="text-xs text-text-dim">
					This is what the AI will see when analyzing your images. Labels shown are examples; actual labels from your Homebox instance will be used.
				</p>
			</div>
		{/if}
	</div>

	<!-- Docker Persistence Warning & Export -->
	<div class="pt-4 border-t border-border/20 space-y-3">
		<!-- Export Button -->
		<button
			type="button"
			class="w-full py-3 px-4 bg-surface-elevated/50 hover:bg-surface-hover border border-border rounded-xl text-text-muted hover:text-text transition-all flex items-center justify-center gap-2"
			onclick={toggleEnvExport}
			disabled={isLoadingExport}
		>
			{#if isLoadingExport}
				<div class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
				<span>Loading...</span>
			{:else}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
				</svg>
				<span>Export as Environment Variables</span>
				<svg class="w-4 h-4 ml-auto transition-transform {showEnvExport ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="6 9 12 15 18 9" />
				</svg>
			{/if}
		</button>

		{#if showEnvExport && exportPrefs}
			<div class="space-y-2">
				<div class="flex items-center justify-between">
					<span class="text-xs text-text-muted font-medium">Add these to your docker-compose.yml or .env file</span>
					<button
						type="button"
						class="flex items-center gap-1 text-xs px-2 py-1 bg-primary/20 hover:bg-primary/30 text-primary rounded transition-colors"
						onclick={copyEnvVars}
					>
						{#if envCopied}
							<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<polyline points="20 6 9 17 4 12" />
							</svg>
							<span>Copied!</span>
						{:else}
							<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
								<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
							</svg>
							<span>Copy</span>
						{/if}
					</button>
				</div>
				<div class="bg-background rounded-xl border border-border overflow-hidden">
					<pre class="p-4 text-xs font-mono text-text-muted overflow-x-auto whitespace-pre-wrap break-words">{generateEnvVars(exportPrefs)}</pre>
				</div>
			</div>
		{/if}

		<!-- Warning -->
		<div class="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl">
			<p class="text-xs text-amber-200 flex items-start gap-2">
				<svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
				</svg>
				<span><strong>Docker users:</strong> Customizations are stored in a config file that may be lost when updating your container. Use the export above to persist settings via environment variables.</span>
			</p>
		</div>
	</div>
</section>

	<!-- Account Section -->
	<section class="card space-y-4">
		<h2 class="text-lg font-semibold text-text flex items-center gap-2">
			<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
				<circle cx="12" cy="7" r="4" />
			</svg>
			Account
		</h2>

		<Button variant="danger" full onclick={handleLogout}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
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
	<div class="fixed inset-0 z-[60] flex flex-col bg-background">
		<!-- Header -->
		<div class="flex items-center justify-between p-4 border-b border-border bg-surface">
			<div class="flex items-center gap-3">
				<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
					<polyline points="14 2 14 8 20 8" />
					<line x1="16" y1="13" x2="8" y2="13" />
					<line x1="16" y1="17" x2="8" y2="17" />
					<polyline points="10 9 9 9 8 9" />
				</svg>
				<div>
					<h2 class="text-lg font-semibold text-text">Application Logs</h2>
					{#if logs.filename}
						<p class="text-xs text-text-dim">
							{logs.filename} • {logs.truncated ? `Last ${logs.total_lines > 300 ? 300 : logs.total_lines} of ${logs.total_lines}` : logs.total_lines} lines
						</p>
					{/if}
				</div>
			</div>
			<div class="flex items-center gap-2">
				<button
					type="button"
					class="p-2 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-colors"
					onclick={refreshLogs}
					disabled={isLoadingLogs}
					title="Refresh logs"
				>
					<svg
						class="w-5 h-5 {isLoadingLogs ? 'animate-spin' : ''}"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path d="M23 4v6h-6M1 20v-6h6" />
						<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
					</svg>
				</button>
				<button
					type="button"
					class="p-2 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-colors"
					onclick={handleDownloadLogs}
					disabled={!logs.filename}
					title="Download full log file"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
						<polyline points="7 10 12 15 17 10" />
						<line x1="12" y1="15" x2="12" y2="3" />
					</svg>
				</button>
				<button
					type="button"
					class="p-2 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-colors"
					onclick={() => (logsFullscreen = false)}
					title="Close fullscreen"
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
						<path d="M18 6L6 18M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>
		<!-- Content -->
		<div bind:this={logsFullscreenContainer} class="flex-1 overflow-auto p-4 pb-24">
			<pre class="text-xs font-mono text-text-muted whitespace-pre-wrap break-all leading-relaxed">{@html colorizedLogs()}</pre>
		</div>
	</div>
{/if}

<!-- Fullscreen Prompt Preview Modal -->
{#if promptFullscreen && promptPreview}
	<div class="fixed inset-0 z-[60] flex flex-col bg-background">
		<!-- Header -->
		<div class="flex items-center justify-between p-4 border-b border-border bg-surface">
			<div class="flex items-center gap-3">
				<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
					<path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z" />
				</svg>
				<div>
					<h2 class="text-lg font-semibold text-text">AI System Prompt</h2>
					<p class="text-xs text-text-dim">
						This is what the AI sees when analyzing your images
					</p>
				</div>
			</div>
			<button
				type="button"
				class="p-2 text-text-muted hover:text-text hover:bg-surface-hover rounded-lg transition-colors"
				onclick={() => (promptFullscreen = false)}
				title="Close fullscreen"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<path d="M18 6L6 18M6 6l12 12" />
				</svg>
			</button>
		</div>
		<!-- Content -->
		<div class="flex-1 overflow-auto p-4 pb-24">
			<pre class="text-sm font-mono text-text-muted whitespace-pre-wrap break-words leading-relaxed">{promptPreview}</pre>
		</div>
	</div>
{/if}

