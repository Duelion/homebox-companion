<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { isAuthenticated, logout } from '$lib/stores/auth';
	import { appVersion } from '$lib/stores/ui';
	import { getConfig, getLogs, getVersion, labels as labelsApi, fieldPreferences, type ConfigResponse, type LogsResponse, type FieldPreferences, type LabelData } from '$lib/api';
	import Button from '$lib/components/Button.svelte';

	let config = $state<ConfigResponse | null>(null);
	let logs = $state<LogsResponse | null>(null);
	let isLoadingConfig = $state(true);
	let isLoadingLogs = $state(false);
	let showLogs = $state(false);
	let logsError = $state<string | null>(null);

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
	});

	// Prompt preview state
	let showPromptPreview = $state(false);
	let isLoadingPreview = $state(false);
	let promptPreview = $state<string | null>(null);

	// Field metadata for display - defaults shown as visible text, not hidden in placeholder
	const fieldMeta: Array<{ key: keyof FieldPreferences; label: string; defaultText: string; example: string }> = [
		{
			key: 'name',
			label: 'Name',
			defaultText: '[Type] [Brand] [Model] [Specs], Title Case, item type first for searchability',
			example: '"Ball Bearing 6900-2RS 10x22x6mm", "LED Strip COB Green 5V 1M"'
		},
		{
			key: 'description',
			label: 'Description',
			defaultText: 'Condition/attributes only, max 1000 chars, NEVER mention quantity',
			example: '"Minor scratches on casing", "New in packaging"'
		},
		{
			key: 'quantity',
			label: 'Quantity',
			defaultText: 'Count identical items together, separate different variants',
			example: '5 identical screws = qty 5, but 2 sizes = 2 separate items'
		},
		{
			key: 'manufacturer',
			label: 'Manufacturer',
			defaultText: 'Only when brand/logo is VISIBLE. Include recognizable brands only.',
			example: 'DeWalt, Vallejo (NOT "Shenzhen XYZ Technology Co.")'
		},
		{
			key: 'model_number',
			label: 'Model Number',
			defaultText: 'Only when model/part number TEXT is clearly visible on label',
			example: '"DCD771C2", "72.034"'
		},
		{
			key: 'serial_number',
			label: 'Serial Number',
			defaultText: 'Only when S/N text is visible on sticker/label/engraving',
			example: 'Look for "S/N:", "Serial:" markings'
		},
		{
			key: 'purchase_price',
			label: 'Purchase Price',
			defaultText: 'Only from visible price tag/receipt. Just the number.',
			example: '29.99 (not "$29.99")'
		},
		{
			key: 'purchase_from',
			label: 'Purchase From',
			defaultText: 'Only from visible packaging/receipt or user-specified',
			example: '"Amazon", "Home Depot"'
		},
		{
			key: 'notes',
			label: 'Notes',
			defaultText: 'ONLY for defects/damage/warnings. Most items = no notes.',
			example: 'GOOD: "Cracked lens" | BAD: "Appears new"'
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

	function handleLogout() {
		logout();
		goto('/');
	}

	async function loadFieldPrefs() {
		if (prefs.name !== null || isLoadingFieldPrefs) {
			showFieldPrefs = !showFieldPrefs;
			return;
		}

		isLoadingFieldPrefs = true;
		fieldPrefsError = null;

		try {
			// Load preferences (labels already loaded in onMount)
			const prefsResult = await fieldPreferences.get();
			prefs = prefsResult;
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
		if (showPromptPreview && promptPreview) {
			showPromptPreview = !showPromptPreview;
			return;
		}

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
				<div class="flex items-center justify-between py-2 border-t border-border/50">
					<span class="text-text-muted">AI Model</span>
					<span class="text-text font-mono text-sm">{config.openai_model}</span>
				</div>
			{:else if isLoadingConfig}
				<div class="flex items-center justify-center py-4">
					<div class="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
				</div>
			{/if}

			<!-- GitHub Link -->
			<div class="pt-2 border-t border-border/50">
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
				<button
					type="button"
					class="text-sm text-primary hover:text-primary-hover transition-colors flex items-center gap-1"
					onclick={refreshLogs}
					disabled={isLoadingLogs}
				>
					<svg
						class="w-4 h-4 {isLoadingLogs ? 'animate-spin' : ''}"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path d="M23 4v6h-6M1 20v-6h6" />
						<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
					</svg>
					Refresh
				</button>
			{/if}
		</div>

		<p class="text-sm text-text-muted">
			View recent application logs for debugging and reference.
		</p>

		{#if !showLogs}
			<button
				type="button"
				class="w-full py-3 px-4 bg-surface-elevated hover:bg-surface-hover border border-border rounded-xl text-text-muted hover:text-text transition-all flex items-center justify-center gap-2"
				onclick={loadLogs}
				disabled={isLoadingLogs}
			>
				{#if isLoadingLogs}
					<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
					<span>Loading logs...</span>
				{:else}
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<polyline points="6 9 12 15 18 9" />
					</svg>
					<span>Show Logs</span>
				{/if}
			</button>
		{:else}
			{#if logsError}
				<div class="p-4 bg-danger/10 border border-danger/30 rounded-xl text-danger text-sm">
					{logsError}
				</div>
			{:else if logs}
				<div class="space-y-2">
					{#if logs.filename}
						<div class="flex items-center justify-between text-xs text-text-dim">
							<span>{logs.filename}</span>
							<span>
								{logs.truncated ? `Last ${logs.total_lines > 300 ? 300 : logs.total_lines} of ${logs.total_lines}` : `${logs.total_lines}`} lines
							</span>
						</div>
					{/if}
					<div class="bg-background rounded-xl border border-border overflow-hidden">
						<pre class="p-4 text-xs font-mono text-text-muted overflow-x-auto max-h-80 overflow-y-auto whitespace-pre-wrap break-all">{logs.logs}</pre>
					</div>
				</div>

				<button
					type="button"
					class="w-full py-2 text-sm text-text-muted hover:text-text transition-colors flex items-center justify-center gap-1"
					onclick={() => (showLogs = false)}
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<polyline points="18 15 12 9 6 15" />
					</svg>
					Hide Logs
				</button>
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

		{#if !showFieldPrefs}
			<button
				type="button"
				class="w-full py-3 px-4 bg-surface-elevated hover:bg-surface-hover border border-border rounded-xl text-text-muted hover:text-text transition-all flex items-center justify-center gap-2"
				onclick={loadFieldPrefs}
				disabled={isLoadingFieldPrefs}
			>
				{#if isLoadingFieldPrefs}
					<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
					<span>Loading...</span>
				{:else}
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<polyline points="6 9 12 15 18 9" />
					</svg>
					<span>Configure Fields</span>
				{/if}
			</button>
		{:else}
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
				placeholder="English (default)"
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
					<option value={label.id}>{label.name}</option>
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
							<span class="text-text-dim">Default:</span> {field.defaultText}
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

			<button
				type="button"
				class="w-full py-2 text-sm text-text-muted hover:text-text transition-colors flex items-center justify-center gap-1"
				onclick={() => (showFieldPrefs = false)}
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="18 15 12 9 6 15" />
				</svg>
				Hide Configuration
			</button>
		{/if}

		<!-- Prompt Preview Section - Always visible at section level -->
		<div class="pt-4 border-t border-border/50">
			<button
				type="button"
				class="w-full py-3 px-4 bg-surface-elevated/50 hover:bg-surface-hover border border-border rounded-xl text-text-muted hover:text-text transition-all flex items-center justify-center gap-2"
				onclick={loadPromptPreview}
				disabled={isLoadingPreview}
			>
				{#if isLoadingPreview}
					<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
					<span>Generating preview...</span>
				{:else}
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
						<path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
						<path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7Z" />
					</svg>
					<span>{showPromptPreview ? 'Refresh' : 'Preview'} AI Prompt</span>
				{/if}
			</button>

			{#if showPromptPreview && promptPreview}
				<div class="mt-3 space-y-2">
					<div class="flex items-center justify-between">
						<span class="text-xs text-text-muted font-medium">System Prompt Preview</span>
						<button
							type="button"
							class="text-xs text-text-dim hover:text-text-muted transition-colors"
							onclick={() => (showPromptPreview = false)}
						>
							Hide
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

