<script lang="ts">
	/**
	 * EnrichmentSection - AI-powered product enrichment settings.
	 *
	 * Includes:
	 * - Enable/disable enrichment toggle
	 * - Auto-enrich after detection toggle
	 * - Web search provider configuration (Tavily, Google CSE, SearXNG)
	 * - Cache TTL configuration
	 * - Clear cache button
	 */
	import { onMount } from 'svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';

	const service = settingsService;

	// Local state to prevent rapid toggling during save
	let isSaving = $state(false);

	// Local state for TTL input (allows editing without immediate save)
	let localCacheTTL = $state(24);
	let ttlInitialized = $state(false);

	// Local state for search provider settings
	let localSearchProvider = $state('none');
	let localTavilyKey = $state('');
	let localGoogleKey = $state('');
	let localGoogleEngineId = $state('');
	let localSearxngUrl = $state('');
	let searchProviderInitialized = $state(false);

	// Local state for custom retailer domains
	let localRetailerDomains = $state<string[]>([]);
	let newDomainInput = $state('');
	let retailerDomainsInitialized = $state(false);

	// Load app preferences on mount if not already loaded
	onMount(async () => {
		if (!service.appPreferences) {
			await service.toggleConnectionSettings();
			// Close it since we just wanted to load the data
			service.showConnectionSettings = false;
		}
		// Initialize local values from loaded preferences
		initializeLocalState();
	});

	// Helper to initialize local state from service (only runs once per flag)
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

	// Sync local values when preferences load (but only once)
	// Guard with flags to prevent any chance of re-running after initialization
	$effect(() => {
		// Only run if not yet initialized and preferences are available
		const needsTTL = !ttlInitialized;
		const needsSearch = !searchProviderInitialized;
		const hasPrefs = !!service.appPreferences;

		if (hasPrefs && (needsTTL || needsSearch)) {
			initializeLocalState();
		}
	});

	// Helper to build full preferences object for saving
	function buildPrefsForSave(overrides: Partial<{
		enrichment_enabled: boolean;
		enrichment_auto_enrich: boolean;
		enrichment_cache_ttl_hours: number;
		search_provider: string;
		search_tavily_api_key: string | null;
		search_google_api_key: string | null;
		search_google_engine_id: string | null;
		search_searxng_url: string | null;
		enrichment_retailer_domains: string[];
	}>) {
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

	function handleCacheTTLInput(e: Event) {
		const value = parseInt((e.target as HTMLInputElement).value) || 24;
		localCacheTTL = Math.max(1, Math.min(168, value));
	}

	async function handleCacheTTLBlur() {
		if (isSaving || !service.appPreferences) return;
		if (localCacheTTL === service.appPreferences.enrichment_cache_ttl_hours) return;

		const prefs = buildPrefsForSave({ enrichment_cache_ttl_hours: localCacheTTL });
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

	async function handleAddRetailerDomain() {
		const domain = newDomainInput.trim().toLowerCase();
		if (!domain || isSaving || !service.appPreferences) return;

		// Basic validation - should look like a domain
		if (!domain.includes('.') || domain.includes(' ')) {
			return;
		}

		// Don't add duplicates
		if (localRetailerDomains.includes(domain)) {
			newDomainInput = '';
			return;
		}

		const updatedDomains = [...localRetailerDomains, domain];
		const prefs = buildPrefsForSave({ enrichment_retailer_domains: updatedDomains });
		if (!prefs) return;

		isSaving = true;
		try {
			await service.saveAppPreferences(prefs);
			localRetailerDomains = updatedDomains;
			newDomainInput = '';
		} finally {
			isSaving = false;
		}
	}

	async function handleRemoveRetailerDomain(domain: string) {
		if (isSaving || !service.appPreferences) return;

		const updatedDomains = localRetailerDomains.filter((d) => d !== domain);
		const prefs = buildPrefsForSave({ enrichment_retailer_domains: updatedDomains });
		if (!prefs) return;

		isSaving = true;
		try {
			await service.saveAppPreferences(prefs);
			localRetailerDomains = updatedDomains;
		} finally {
			isSaving = false;
		}
	}

	// Computed values for display (read directly from service)
	const isEnabled = $derived(service.appPreferences?.enrichment_enabled ?? false);
	const isAutoEnrich = $derived(service.appPreferences?.enrichment_auto_enrich ?? false);

	// Search provider display names
	const providerNames: Record<string, string> = {
		none: 'AI Knowledge Only',
		tavily: 'Tavily',
		google_cse: 'Google Custom Search',
		searxng: 'SearXNG',
	};
</script>

<section class="card space-y-4">
	<h2 class="flex items-center gap-2 text-body-lg font-semibold text-neutral-100">
		<svg
			class="h-5 w-5 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<path
				d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
			/>
		</svg>
		Enrichment Settings
	</h2>

	<p class="text-xs text-neutral-400">
		Enrichment looks up detailed product specifications using web search and/or AI knowledge.
	</p>

	{#if service.isLoading.appPreferences}
		<div class="flex items-center justify-center py-8">
			<div class="h-6 w-6 animate-spin rounded-full border-2 border-primary-500 border-t-transparent"></div>
		</div>
	{:else}
		<!-- Enable Enrichment Toggle -->
		<div
			class="flex items-center justify-between rounded-xl border border-neutral-700 bg-neutral-800/30 p-4"
		>
			<div class="flex-1">
				<h3 class="text-sm font-medium text-neutral-200">Enable Enrichment</h3>
				<p class="mt-1 text-xs text-neutral-400">
					Allow AI to look up product specs when you click the enrich button in review.
				</p>
			</div>
			<button
				type="button"
				class="relative h-6 w-11 rounded-full transition-colors {isEnabled
					? 'bg-primary-500'
					: 'bg-neutral-600'} {isSaving ? 'opacity-50' : ''}"
				onclick={handleToggleEnabled}
				disabled={isSaving}
				role="switch"
				aria-checked={isEnabled}
				aria-label="Toggle enrichment"
			>
				<span
					class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {isEnabled
						? 'translate-x-5'
						: 'translate-x-0'}"
				></span>
			</button>
		</div>

		<!-- Settings shown when enrichment is enabled -->
		{#if isEnabled}
			<!-- Auto-Enrich Toggle -->
			<div
				class="flex items-center justify-between rounded-xl border border-neutral-700 bg-neutral-800/30 p-4"
			>
				<div class="flex-1">
					<h3 class="text-sm font-medium text-neutral-200">Auto-Enrich After Detection</h3>
					<p class="mt-1 text-xs text-neutral-400">
						Automatically enrich items after AI detection completes.
					</p>
				</div>
				<button
					type="button"
					class="relative h-6 w-11 rounded-full transition-colors {isAutoEnrich
						? 'bg-primary-500'
						: 'bg-neutral-600'} {isSaving ? 'opacity-50' : ''}"
					onclick={handleToggleAutoEnrich}
					disabled={isSaving}
					role="switch"
					aria-checked={isAutoEnrich}
					aria-label="Toggle auto-enrich"
				>
					<span
						class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {isAutoEnrich
							? 'translate-x-5'
							: 'translate-x-0'}"
					></span>
				</button>
			</div>

			<!-- Web Search Provider Settings -->
			<div class="space-y-3 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
				<h3 class="text-sm font-medium text-neutral-200">Web Search Provider</h3>
				<p class="text-xs text-neutral-400">
					Choose a search provider for looking up product specifications. Web search provides more accurate
					and up-to-date information than AI knowledge alone.
				</p>

				<div class="space-y-3">
					<div class="flex items-center gap-3">
						<label for="search-provider" class="text-xs text-neutral-400 w-24">Provider:</label>
						<select
							id="search-provider"
							value={localSearchProvider}
							onchange={handleSearchProviderChange}
							disabled={isSaving}
							class="flex-1 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-1.5 text-sm text-neutral-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
						>
							<option value="none">AI Knowledge Only (No Web Search)</option>
							<option value="tavily">Tavily (Recommended)</option>
							<option value="google_cse">Google Custom Search</option>
							<option value="searxng">SearXNG (Self-Hosted)</option>
						</select>
					</div>

					<!-- Tavily Settings -->
					{#if localSearchProvider === 'tavily'}
						<div class="space-y-2 border-t border-neutral-700 pt-3">
							<p class="text-xs text-neutral-400">
								Tavily is an AI-optimized search API with clean content extraction.
								Get your API key at <a href="https://tavily.com" target="_blank" rel="noopener noreferrer" class="text-primary-400 hover:underline">tavily.com</a>
							</p>
							<div class="flex items-center gap-3">
								<label for="tavily-key" class="text-xs text-neutral-400 w-24">API Key:</label>
								<input
									id="tavily-key"
									type="password"
									bind:value={localTavilyKey}
									placeholder="tvly-..."
									disabled={isSaving}
									class="flex-1 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
								/>
							</div>
							<div class="flex justify-end">
								<Button
									variant="primary"
									size="sm"
									onclick={handleSaveSearchCredentials}
									disabled={isSaving}
								>
									{isSaving ? 'Saving...' : 'Save API Key'}
								</Button>
							</div>
						</div>
					{/if}

					<!-- Google CSE Settings -->
					{#if localSearchProvider === 'google_cse'}
						<div class="space-y-2 border-t border-neutral-700 pt-3">
							<p class="text-xs text-neutral-400">
								Google Custom Search requires an API key and Search Engine ID.
								See documentation for setup instructions.
							</p>
							<div class="flex items-center gap-3">
								<label for="google-key" class="text-xs text-neutral-400 w-24">API Key:</label>
								<input
									id="google-key"
									type="password"
									bind:value={localGoogleKey}
									placeholder="AIza..."
									disabled={isSaving}
									class="flex-1 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
								/>
							</div>
							<div class="flex items-center gap-3">
								<label for="google-cx" class="text-xs text-neutral-400 w-24">Engine ID:</label>
								<input
									id="google-cx"
									type="text"
									bind:value={localGoogleEngineId}
									placeholder="Search Engine ID (cx)"
									disabled={isSaving}
									class="flex-1 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
								/>
							</div>
							<div class="flex justify-end">
								<Button
									variant="primary"
									size="sm"
									onclick={handleSaveSearchCredentials}
									disabled={isSaving}
								>
									{isSaving ? 'Saving...' : 'Save Credentials'}
								</Button>
							</div>
						</div>
					{/if}

					<!-- SearXNG Settings -->
					{#if localSearchProvider === 'searxng'}
						<div class="space-y-2 border-t border-neutral-700 pt-3">
							<p class="text-xs text-neutral-400">
								SearXNG is a self-hosted metasearch engine. No API key required - just the URL to your instance.
								JSON API must be enabled on the instance.
							</p>
							<div class="flex items-center gap-3">
								<label for="searxng-url" class="text-xs text-neutral-400 w-24">Instance URL:</label>
								<input
									id="searxng-url"
									type="url"
									bind:value={localSearxngUrl}
									placeholder="https://searx.example.com"
									disabled={isSaving}
									class="flex-1 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
								/>
							</div>
							<div class="flex justify-end">
								<Button
									variant="primary"
									size="sm"
									onclick={handleSaveSearchCredentials}
									disabled={isSaving}
								>
									{isSaving ? 'Saving...' : 'Save URL'}
								</Button>
							</div>
						</div>
					{/if}

					<!-- Provider Status -->
					{#if localSearchProvider !== 'none'}
						<div class="flex items-center gap-2 text-xs">
							{#if (localSearchProvider === 'tavily' && localTavilyKey) ||
								(localSearchProvider === 'google_cse' && localGoogleKey && localGoogleEngineId) ||
								(localSearchProvider === 'searxng' && localSearxngUrl)}
								<span class="flex items-center gap-1 text-success-500">
									<svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
										<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
									</svg>
									{providerNames[localSearchProvider]} configured
								</span>
							{:else}
								<span class="flex items-center gap-1 text-warning-500">
									<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
										<path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
									</svg>
									Credentials required
								</span>
							{/if}
						</div>
					{/if}
				</div>
			</div>

			<!-- Cache Settings -->
			<div class="space-y-3 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
				<h3 class="text-sm font-medium text-neutral-200">Cache Settings</h3>
				<p class="text-xs text-neutral-400">
					Enrichment results are cached locally to avoid repeated lookups for the same product.
				</p>

				<div class="flex items-center gap-4">
					<label for="cache-ttl" class="text-xs text-neutral-400">Cache Duration:</label>
					<div class="flex items-center gap-2">
						<input
							id="cache-ttl"
							type="number"
							min="1"
							max="168"
							value={localCacheTTL}
							oninput={handleCacheTTLInput}
							onblur={handleCacheTTLBlur}
							disabled={isSaving}
							class="w-20 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-1.5 text-sm text-neutral-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
						/>
						<span class="text-xs text-neutral-400">hours (1-168)</span>
					</div>
				</div>

				<!-- Clear Cache Button -->
				<div class="flex items-center gap-3 border-t border-neutral-700 pt-3">
					<Button
						variant="secondary"
						size="sm"
						onclick={() => service.clearEnrichmentCache()}
						disabled={service.enrichmentCacheClearing}
					>
						{#if service.enrichmentCacheClearing}
							<div
								class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
							></div>
							Clearing...
						{:else}
							<svg
								class="h-4 w-4"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
								/>
							</svg>
							Clear Cache
						{/if}
					</Button>
					<span class="text-xs text-neutral-500">Remove all cached enrichment results</span>
				</div>

				<!-- Cache Status Message -->
				{#if service.enrichmentCacheMessage}
					<div
						class="rounded-lg p-2 text-xs {service.enrichmentCacheMessageType === 'success'
							? 'bg-success-500/10 text-success-500'
							: 'bg-error-500/10 text-error-500'}"
					>
						{service.enrichmentCacheMessage}
					</div>
				{/if}
			</div>

			<!-- Custom Retailer Domains -->
			<div class="space-y-3 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
				<h3 class="text-sm font-medium text-neutral-200">Custom Retailer Domains</h3>
				<p class="text-xs text-neutral-400">
					Add additional retailer domains to fetch price information from. Built-in domains include
					Home Depot, Lowes, Amazon, Best Buy, Digikey, and many more.
				</p>

				<!-- Add domain input -->
				<div class="flex items-center gap-2">
					<input
						type="text"
						bind:value={newDomainInput}
						placeholder="example-store.com"
						disabled={isSaving}
						onkeydown={(e) => e.key === 'Enter' && handleAddRetailerDomain()}
						class="flex-1 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50"
					/>
					<Button
						variant="secondary"
						size="sm"
						onclick={handleAddRetailerDomain}
						disabled={isSaving || !newDomainInput.trim()}
					>
						Add
					</Button>
				</div>

				<!-- Domain list -->
				{#if localRetailerDomains.length > 0}
					<div class="flex flex-wrap gap-2">
						{#each localRetailerDomains as domain}
							<span
								class="inline-flex items-center gap-1 rounded-full bg-neutral-700 px-2.5 py-1 text-xs text-neutral-200"
							>
								{domain}
								<button
									type="button"
									onclick={() => handleRemoveRetailerDomain(domain)}
									disabled={isSaving}
									class="ml-1 rounded-full p-0.5 hover:bg-neutral-600 disabled:opacity-50"
									aria-label="Remove {domain}"
								>
									<svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
										<path d="M6 18L18 6M6 6l12 12" />
									</svg>
								</button>
							</span>
						{/each}
					</div>
				{:else}
					<p class="text-xs text-neutral-500 italic">No custom domains added. Using built-in list only.</p>
				{/if}
			</div>
		{/if}
	{/if}

	<!-- Privacy Notice -->
	<div class="rounded-lg border border-neutral-700/50 bg-neutral-800/20 p-3">
		<div class="flex gap-2">
			<svg
				class="h-4 w-4 flex-shrink-0 text-neutral-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
				/>
			</svg>
			<div class="text-xs text-neutral-400">
				<p class="font-medium text-neutral-300">Privacy Notice</p>
				<p class="mt-1">
					Enrichment sends manufacturer name and model number to your configured search provider and AI.
					Serial numbers are never sent. All results are cached locally on your server.
				</p>
			</div>
		</div>
	</div>
</section>
