<script lang="ts">
	/**
	 * EnrichmentSection - AI-powered product enrichment settings.
	 *
	 * Includes:
	 * - Enable/disable enrichment toggle
	 * - Auto-enrich after detection toggle
	 * - Cache TTL configuration
	 * - Clear cache button
	 */
	import { onMount } from 'svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';

	const service = settingsService;

	// Load app preferences on mount if not already loaded
	onMount(async () => {
		if (!service.appPreferences) {
			await service.toggleConnectionSettings();
			// Close it since we just wanted to load the data
			service.showConnectionSettings = false;
		}
	});

	// Derived values from appPreferences
	const enabled = $derived(service.appPreferences?.enrichment_enabled ?? false);
	const autoEnrich = $derived(service.appPreferences?.enrichment_auto_enrich ?? false);
	const cacheTTL = $derived(service.appPreferences?.enrichment_cache_ttl_hours ?? 24);

	// Local state for TTL input (allows editing without immediate save)
	let localCacheTTL = $state(24);

	// Sync local TTL with server value when it changes
	$effect(() => {
		localCacheTTL = cacheTTL;
	});

	async function setEnabled(value: boolean) {
		if (!service.appPreferences) return;

		await service.saveAppPreferences({
			homebox_url_override: service.appPreferences.homebox_url_override,
			image_quality_override: service.appPreferences.image_quality_override,
			duplicate_detection_enabled: service.appPreferences.duplicate_detection_enabled,
			enrichment_enabled: value,
			enrichment_auto_enrich: autoEnrich,
			enrichment_cache_ttl_hours: cacheTTL,
		});
	}

	async function setAutoEnrich(value: boolean) {
		if (!service.appPreferences) return;

		await service.saveAppPreferences({
			homebox_url_override: service.appPreferences.homebox_url_override,
			image_quality_override: service.appPreferences.image_quality_override,
			duplicate_detection_enabled: service.appPreferences.duplicate_detection_enabled,
			enrichment_enabled: enabled,
			enrichment_auto_enrich: value,
			enrichment_cache_ttl_hours: cacheTTL,
		});
	}

	function handleCacheTTLInput(value: number) {
		localCacheTTL = Math.max(1, Math.min(168, value || 24));
	}

	async function handleCacheTTLBlur() {
		if (!service.appPreferences) return;
		if (localCacheTTL === cacheTTL) return;

		await service.saveAppPreferences({
			homebox_url_override: service.appPreferences.homebox_url_override,
			image_quality_override: service.appPreferences.image_quality_override,
			duplicate_detection_enabled: service.appPreferences.duplicate_detection_enabled,
			enrichment_enabled: enabled,
			enrichment_auto_enrich: autoEnrich,
			enrichment_cache_ttl_hours: localCacheTTL,
		});
	}
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
		Enrichment uses your configured AI provider to look up detailed product specifications from its
		training knowledge. No external APIs or services required.
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
				class="relative h-6 w-11 rounded-full transition-colors {enabled
					? 'bg-primary-500'
					: 'bg-neutral-600'}"
				onclick={() => setEnabled(!enabled)}
				role="switch"
				aria-checked={enabled}
				aria-label="Toggle enrichment"
			>
				<span
					class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {enabled
						? 'translate-x-5'
						: 'translate-x-0'}"
				></span>
			</button>
		</div>

		<!-- Auto-Enrich Toggle (only shown when enrichment is enabled) -->
		{#if enabled}
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
					class="relative h-6 w-11 rounded-full transition-colors {autoEnrich
						? 'bg-primary-500'
						: 'bg-neutral-600'}"
					onclick={() => setAutoEnrich(!autoEnrich)}
					role="switch"
					aria-checked={autoEnrich}
					aria-label="Toggle auto-enrich"
				>
					<span
						class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {autoEnrich
							? 'translate-x-5'
							: 'translate-x-0'}"
					></span>
				</button>
			</div>

			<!-- Cache Settings -->
			<div class="space-y-3 rounded-xl border border-neutral-700 bg-neutral-800/30 p-4">
				<h3 class="text-sm font-medium text-neutral-200">Cache Settings</h3>
				<p class="text-xs text-neutral-400">
					Enrichment results are cached locally to avoid repeated AI calls for the same product.
				</p>

				<div class="flex items-center gap-4">
					<label for="cache-ttl" class="text-xs text-neutral-400">Cache Duration:</label>
					<div class="flex items-center gap-2">
						<input
							id="cache-ttl"
							type="number"
							min="1"
							max="168"
							bind:value={localCacheTTL}
							oninput={(e) => handleCacheTTLInput(parseInt(e.currentTarget.value))}
							onblur={handleCacheTTLBlur}
							class="w-20 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-1.5 text-sm text-neutral-100 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
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
					Enrichment sends manufacturer name and model number to your configured AI provider. Serial
					numbers are never sent. All results are cached locally on your server.
				</p>
			</div>
		</div>
	</div>
</section>
