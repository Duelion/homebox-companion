<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { isAuthenticated, logout } from '$lib/stores/auth';
	import { appVersion } from '$lib/stores/ui';
	import { getConfig, getLogs, getVersion, type ConfigResponse, type LogsResponse } from '$lib/api';
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

	// Redirect if not authenticated
	onMount(async () => {
		if (!$isAuthenticated) {
			goto('/');
			return;
		}

		// Fetch config and version info in parallel
		try {
			const [configResult, versionResult] = await Promise.all([
				getConfig(),
				getVersion(true), // Force check for updates regardless of env setting
			]);

			config = configResult;

			// Set update info
			if (versionResult.update_available && versionResult.latest_version) {
				updateAvailable = true;
				latestVersionNumber = versionResult.latest_version;
			}
		} catch (error) {
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

