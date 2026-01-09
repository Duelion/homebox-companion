<script lang="ts">
	/**
	 * ConnectionSection - Connection and quality settings.
	 *
	 * Allows users to override:
	 * - Homebox URL (useful for switching instances)
	 * - Image quality (for bandwidth/performance tuning)
	 */
	import { settingsService } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';
	import CollapsibleSection from './CollapsibleSection.svelte';
	import type { AppPreferencesInput } from '$lib/api/appPreferences';

	const service = settingsService;

	// Local form state for editing
	let editingPrefs = $state<AppPreferencesInput | null>(null);
	let prefsInitialized = $state(false);

	// Initialize form state when preferences load (only once)
	$effect(() => {
		if (!prefsInitialized && service.appPreferences) {
			editingPrefs = {
				homebox_url_override: service.appPreferences.homebox_url_override,
				image_quality_override: service.appPreferences.image_quality_override,
				duplicate_detection_enabled: service.appPreferences.duplicate_detection_enabled,
				enrichment_enabled: service.appPreferences.enrichment_enabled,
				enrichment_auto_enrich: service.appPreferences.enrichment_auto_enrich,
				enrichment_cache_ttl_hours: service.appPreferences.enrichment_cache_ttl_hours,
				search_provider: service.appPreferences.search_provider,
				search_tavily_api_key: service.appPreferences.search_tavily_api_key,
				search_google_api_key: service.appPreferences.search_google_api_key,
				search_google_engine_id: service.appPreferences.search_google_engine_id,
				search_searxng_url: service.appPreferences.search_searxng_url,
				enrichment_retailer_domains: service.appPreferences.enrichment_retailer_domains
			};
			prefsInitialized = true;
		}
	});

	async function handleSave() {
		if (!editingPrefs) return;
		await service.saveAppPreferences(editingPrefs);
	}

	function clearOverride(field: 'homebox_url_override' | 'image_quality_override') {
		if (!editingPrefs) return;
		editingPrefs[field] = null;
	}
</script>

{#snippet icon()}
	<svg
		class="h-5 w-5 text-primary"
		fill="none"
		stroke="currentColor"
		viewBox="0 0 24 24"
		stroke-width="1.5"
	>
		<path
			d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"
		/>
	</svg>
{/snippet}

<CollapsibleSection title="Connection Settings" {icon} defaultCollapsed={true}>
	<!-- Toggle Button -->
	<button
		type="button"
		class="flex w-full items-center gap-2 rounded-xl border border-base-content/20 bg-base-300/50 px-4 py-3 text-base-content/60 transition-all hover:bg-base-300 hover:text-base-content"
		onclick={() => service.toggleConnectionSettings()}
	>
		<svg
			class="h-5 w-5 text-primary"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<path
				d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
			/>
			<path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
		</svg>
		<span>Configure Connection</span>
		{#if service.isLoading.appPreferences}
			<div
				class="ml-auto h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
			></div>
		{:else}
			<svg
				class="ml-auto h-4 w-4 transition-transform {service.showConnectionSettings
					? 'rotate-180'
					: ''}"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<polyline points="6 9 12 15 18 9" />
			</svg>
		{/if}
	</button>

	{#if service.errors.appPreferences}
		<div class="rounded-xl border border-error/30 bg-error/10 p-3">
			<p class="text-sm text-error">{service.errors.appPreferences}</p>
		</div>
	{/if}

	{#if service.showConnectionSettings && editingPrefs && service.appPreferences}
		<div class="space-y-4 border-t border-base-content/10 pt-4">
			<!-- Homebox URL -->
			<div class="space-y-2">
				<div class="flex items-center justify-between">
					<label for="homebox-url" class="text-sm font-medium text-base-content/75"
						>Homebox URL</label
					>
					{#if editingPrefs.homebox_url_override}
						<button
							type="button"
							class="text-xs text-base-content/40 hover:text-base-content/75"
							onclick={() => clearOverride('homebox_url_override')}
						>
							Use default
						</button>
					{/if}
				</div>
				<input
					id="homebox-url"
					type="url"
					bind:value={editingPrefs.homebox_url_override}
					class="input w-full"
					placeholder={service.appPreferences.effective_homebox_url}
				/>
				<p class="text-xs text-base-content/40">
					{#if editingPrefs.homebox_url_override}
						Override active. Clear to use default.
					{:else}
						Using environment default: {service.appPreferences.effective_homebox_url}
					{/if}
				</p>
			</div>

			<!-- Image Quality -->
			<div class="space-y-2">
				<div class="flex items-center justify-between">
					<label for="image-quality" class="text-sm font-medium text-base-content/75"
						>Image Quality</label
					>
					{#if editingPrefs.image_quality_override}
						<button
							type="button"
							class="text-xs text-base-content/40 hover:text-base-content/75"
							onclick={() => clearOverride('image_quality_override')}
						>
							Use default
						</button>
					{/if}
				</div>
				<select id="image-quality" bind:value={editingPrefs.image_quality_override} class="input w-full">
					<option value={null}>Default ({service.appPreferences.effective_image_quality})</option>
					{#each service.appPreferences.image_quality_options as quality}
						<option value={quality}>{quality.charAt(0).toUpperCase() + quality.slice(1)}</option>
					{/each}
				</select>
				<p class="text-xs text-base-content/40">
					{#if editingPrefs.image_quality_override}
						Using override: {editingPrefs.image_quality_override}
					{:else}
						Higher quality = larger files, slower uploads
					{/if}
				</p>
			</div>

			<!-- Save Button -->
			<div class="flex items-center gap-3 border-t border-base-content/10 pt-4">
				<Button
					variant="primary"
					onclick={handleSave}
					disabled={service.connectionSettingsSaveState === 'saving'}
				>
					{#if service.connectionSettingsSaveState === 'saving'}
						<div
							class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
						></div>
						Saving...
					{:else if service.connectionSettingsSaveState === 'success'}
						<svg
							class="h-4 w-4"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="2"
						>
							<polyline points="20 6 9 17 4 12" />
						</svg>
						Saved!
					{:else}
						Save Settings
					{/if}
				</Button>
			</div>
		</div>
	{/if}
</CollapsibleSection>
