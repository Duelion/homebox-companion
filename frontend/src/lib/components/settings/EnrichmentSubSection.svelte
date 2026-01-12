<script lang="ts">
	/**
	 * EnrichmentSubSection - Enrichment settings as a sub-section.
	 *
	 * Simplified version for use within AIConfigurationSection.
	 */
	import { onMount } from 'svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';

	const service = settingsService;

	let isExpanded = $state(false);
	let isSaving = $state(false);

	// Local state for settings
	let localCacheTTL = $state(24);
	let ttlInitialized = $state(false);
	let localSearchProvider = $state('none');
	let localTavilyKey = $state('');
	let localGoogleKey = $state('');
	let localGoogleEngineId = $state('');
	let localSearxngUrl = $state('');
	let searchProviderInitialized = $state(false);
	let localRetailerDomains = $state<string[]>([]);
	let newDomainInput = $state('');
	let retailerDomainsInitialized = $state(false);

	onMount(async () => {
		if (!service.appPreferences) {
			await service.toggleConnectionSettings();
			service.showConnectionSettings = false;
		}
		initializeLocalState();
	});

	function initializeLocalState() {
		if (!service.appPreferences) return;
		if (!ttlInitialized) {
			localCacheTTL = service.appPreferences.enrichment_cache_ttl_hours;
			ttlInitialized = true;
		}
		if (!searchProviderInitialized) {
			localSearchProvider = service.appPreferences.search_provider || 'none';
			localTavilyKey = service.appPreferences.search_tavily_api_key || '';
			localGoogleKey = service.appPreferences.search_google_api_key || '';
			localGoogleEngineId = service.appPreferences.search_google_engine_id || '';
			localSearxngUrl = service.appPreferences.search_searxng_url || '';
			searchProviderInitialized = true;
		}
		if (!retailerDomainsInitialized) {
			localRetailerDomains = [...(service.appPreferences.enrichment_retailer_domains || [])];
			retailerDomainsInitialized = true;
		}
	}

	$effect(() => {
		const needsTTL = !ttlInitialized;
		const needsSearch = !searchProviderInitialized;
		const hasPrefs = !!service.appPreferences;
		if (hasPrefs && (needsTTL || needsSearch)) {
			initializeLocalState();
		}
	});

	function buildPrefsForSave(overrides: Partial<Record<string, unknown>>) {
		if (!service.appPreferences) return null;
		return {
			homebox_url_override: service.appPreferences.homebox_url_override,
			image_quality_override: service.appPreferences.image_quality_override,
			duplicate_detection_enabled: service.appPreferences.duplicate_detection_enabled,
			enrichment_enabled: overrides.enrichment_enabled ?? service.appPreferences.enrichment_enabled,
			enrichment_auto_enrich: overrides.enrichment_auto_enrich ?? service.appPreferences.enrichment_auto_enrich,
			enrichment_cache_ttl_hours: overrides.enrichment_cache_ttl_hours ?? service.appPreferences.enrichment_cache_ttl_hours,
			search_provider: overrides.search_provider ?? service.appPreferences.search_provider,
			search_tavily_api_key: overrides.search_tavily_api_key !== undefined ? overrides.search_tavily_api_key : service.appPreferences.search_tavily_api_key,
			search_google_api_key: overrides.search_google_api_key !== undefined ? overrides.search_google_api_key : service.appPreferences.search_google_api_key,
			search_google_engine_id: overrides.search_google_engine_id !== undefined ? overrides.search_google_engine_id : service.appPreferences.search_google_engine_id,
			search_searxng_url: overrides.search_searxng_url !== undefined ? overrides.search_searxng_url : service.appPreferences.search_searxng_url,
			enrichment_retailer_domains: overrides.enrichment_retailer_domains ?? service.appPreferences.enrichment_retailer_domains ?? [],
		};
	}

	async function handleToggleEnabled() {
		if (isSaving || !service.appPreferences) return;
		const prefs = buildPrefsForSave({ enrichment_enabled: !service.appPreferences.enrichment_enabled });
		if (!prefs) return;
		isSaving = true;
		try {
			await service.saveAppPreferences(prefs);
		} finally {
			isSaving = false;
		}
	}

	async function handleToggleAutoEnrich() {
		if (isSaving || !service.appPreferences) return;
		const prefs = buildPrefsForSave({ enrichment_auto_enrich: !service.appPreferences.enrichment_auto_enrich });
		if (!prefs) return;
		isSaving = true;
		try {
			await service.saveAppPreferences(prefs);
		} finally {
			isSaving = false;
		}
	}

	async function handleSearchProviderChange(e: Event) {
		const newProvider = (e.target as HTMLSelectElement).value;
		localSearchProvider = newProvider;
		if (isSaving || !service.appPreferences) return;
		const prefs = buildPrefsForSave({ search_provider: newProvider });
		if (!prefs) return;
		isSaving = true;
		try {
			await service.saveAppPreferences(prefs);
		} finally {
			isSaving = false;
		}
	}

	async function handleSaveSearchCredentials() {
		if (isSaving || !service.appPreferences) return;
		const prefs = buildPrefsForSave({
			search_tavily_api_key: localTavilyKey || null,
			search_google_api_key: localGoogleKey || null,
			search_google_engine_id: localGoogleEngineId || null,
			search_searxng_url: localSearxngUrl || null,
		});
		if (!prefs) return;
		isSaving = true;
		try {
			await service.saveAppPreferences(prefs);
		} finally {
			isSaving = false;
		}
	}

	const isEnabled = $derived(service.appPreferences?.enrichment_enabled ?? false);
	const isAutoEnrich = $derived(service.appPreferences?.enrichment_auto_enrich ?? false);
</script>

<!-- Sub-section header -->
<button
	type="button"
	class="flex w-full items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-800/50 px-4 py-3 text-neutral-400 transition-all hover:bg-neutral-700 hover:text-neutral-100"
	onclick={() => (isExpanded = !isExpanded)}
>
	<svg class="h-5 w-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
		<path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
	</svg>
	<span>Enrichment</span>
	{#if isEnabled}
		<span class="rounded-full bg-success-500/20 px-2 py-0.5 text-xs text-success-500">Enabled</span>
	{/if}
	<svg class="ml-auto h-4 w-4 transition-transform {isExpanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
		<polyline points="6 9 12 15 18 9" />
	</svg>
</button>

{#if isExpanded}
	<div class="space-y-4 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
		<p class="text-xs text-neutral-400">
			Enrichment looks up detailed product specifications using web search and/or AI knowledge.
		</p>

		<!-- Enable Toggle -->
		<div class="flex items-center justify-between">
			<div class="flex-1">
				<h3 class="text-sm font-medium text-neutral-200">Enable Enrichment</h3>
				<p class="mt-1 text-xs text-neutral-400">Look up product specs when you click enrich.</p>
			</div>
			<button
				type="button"
				class="relative h-6 w-11 rounded-full transition-colors {isEnabled ? 'bg-primary-500' : 'bg-neutral-600'} {isSaving ? 'opacity-50' : ''}"
				onclick={handleToggleEnabled}
				disabled={isSaving}
				role="switch"
				aria-checked={isEnabled}
			>
				<span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {isEnabled ? 'translate-x-5' : 'translate-x-0'}"></span>
			</button>
		</div>

		{#if isEnabled}
			<!-- Auto-Enrich Toggle -->
			<div class="flex items-center justify-between border-t border-neutral-700 pt-3">
				<div class="flex-1">
					<h3 class="text-sm font-medium text-neutral-200">Auto-Enrich After Detection</h3>
					<p class="mt-1 text-xs text-neutral-400">Automatically enrich after AI detection.</p>
				</div>
				<button
					type="button"
					class="relative h-6 w-11 rounded-full transition-colors {isAutoEnrich ? 'bg-primary-500' : 'bg-neutral-600'} {isSaving ? 'opacity-50' : ''}"
					onclick={handleToggleAutoEnrich}
					disabled={isSaving}
					role="switch"
					aria-checked={isAutoEnrich}
				>
					<span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {isAutoEnrich ? 'translate-x-5' : 'translate-x-0'}"></span>
				</button>
			</div>

			<!-- Search Provider -->
			<div class="space-y-2 border-t border-neutral-700 pt-3">
				<label for="search-provider" class="block text-sm font-medium text-neutral-200">Web Search Provider</label>
				<select
					id="search-provider"
					value={localSearchProvider}
					onchange={handleSearchProviderChange}
					disabled={isSaving}
					class="input w-full"
				>
					<option value="none">AI Knowledge Only</option>
					<option value="tavily">Tavily (Recommended)</option>
					<option value="google_cse">Google Custom Search</option>
					<option value="searxng">SearXNG (Self-Hosted)</option>
				</select>

				{#if localSearchProvider === 'tavily'}
					<div class="space-y-2 pt-2">
						<input type="password" bind:value={localTavilyKey} placeholder="Tavily API Key" disabled={isSaving} class="input w-full" />
						<Button variant="secondary" size="sm" onclick={handleSaveSearchCredentials} disabled={isSaving}>
							{isSaving ? 'Saving...' : 'Save API Key'}
						</Button>
					</div>
				{:else if localSearchProvider === 'google_cse'}
					<div class="space-y-2 pt-2">
						<input type="password" bind:value={localGoogleKey} placeholder="Google API Key" disabled={isSaving} class="input w-full" />
						<input type="text" bind:value={localGoogleEngineId} placeholder="Search Engine ID" disabled={isSaving} class="input w-full" />
						<Button variant="secondary" size="sm" onclick={handleSaveSearchCredentials} disabled={isSaving}>
							{isSaving ? 'Saving...' : 'Save Credentials'}
						</Button>
					</div>
				{:else if localSearchProvider === 'searxng'}
					<div class="space-y-2 pt-2">
						<input type="url" bind:value={localSearxngUrl} placeholder="https://searx.example.com" disabled={isSaving} class="input w-full" />
						<Button variant="secondary" size="sm" onclick={handleSaveSearchCredentials} disabled={isSaving}>
							{isSaving ? 'Saving...' : 'Save URL'}
						</Button>
					</div>
				{/if}
			</div>

			<!-- Clear Cache -->
			<div class="border-t border-neutral-700 pt-3">
				<Button variant="secondary" size="sm" onclick={() => service.clearEnrichmentCache()} disabled={service.enrichmentCacheClearing}>
					{#if service.enrichmentCacheClearing}
						Clearing...
					{:else}
						Clear Cache
					{/if}
				</Button>
				{#if service.enrichmentCacheMessage}
					<p class="mt-2 text-xs {service.enrichmentCacheMessageType === 'success' ? 'text-success-500' : 'text-error-500'}">
						{service.enrichmentCacheMessage}
					</p>
				{/if}
			</div>
		{/if}

		<!-- Privacy Notice -->
		<div class="rounded-lg border border-neutral-700/50 bg-neutral-800/20 p-3">
			<p class="text-xs text-neutral-400">
				<strong class="text-neutral-300">Privacy:</strong> Only manufacturer and model are sent. Serial numbers are never sent externally.
			</p>
		</div>
	</div>
{/if}
