<script lang="ts">
	/**
	 * Settings Page - Thin orchestrator for settings sections.
	 *
	 * This page delegates all state management and business logic to:
	 * - settingsService: Centralized state and API calls
	 * - Section components: UI rendering for each settings area
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, onDestroy } from 'svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import { settingsService } from '$lib/workflows/settings.svelte';

	import AccountSection from '$lib/components/settings/AccountSection.svelte';
	import AboutSection from '$lib/components/settings/AboutSection.svelte';
	import AIProviderSection from '$lib/components/settings/AIProviderSection.svelte';
	import BehaviorSection from '$lib/components/settings/BehaviorSection.svelte';
	import ConnectionSection from '$lib/components/settings/ConnectionSection.svelte';
	import EnrichmentSection from '$lib/components/settings/EnrichmentSection.svelte';
	import FieldPrefsSection from '$lib/components/settings/FieldPrefsSection.svelte';
	import LogsSection from '$lib/components/settings/LogsSection.svelte';
	import ThemeSection from '$lib/components/settings/ThemeSection.svelte';

	onMount(async () => {
		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		if (!authStore.isAuthenticated) {
			goto(resolve('/'));
			return;
		}

		await settingsService.initialize();
	});

	onDestroy(() => {
		// Clean up any pending timeouts
		settingsService.cleanup();
	});
</script>

<svelte:head>
	<title>Settings - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	<div class="mb-6">
		<h1 class="text-h1 font-bold text-neutral-100">Settings</h1>
		<p class="mt-1 text-body-sm text-neutral-400">App configuration and information</p>
	</div>

	{#if settingsService.errors.init}
		<div class="card mb-6 border-error-500/30 bg-error-500/10">
			<div class="flex items-start gap-3">
				<svg
					class="mt-0.5 h-5 w-5 flex-shrink-0 text-error-500"
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
					<p class="font-medium text-error-500">Failed to load settings</p>
					<p class="mt-1 text-sm text-neutral-400">{settingsService.errors.init}</p>
					<button
						type="button"
						class="mt-2 text-sm text-primary-400 underline hover:text-primary-300"
						onclick={() => settingsService.initialize()}
					>
						Try again
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Settings sections - single column on mobile, two columns on desktop -->
	<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
		<!-- Left column on desktop -->
		<div class="space-y-6">
			<AccountSection />
			<ThemeSection />
			<AIProviderSection />
			<ConnectionSection />
		</div>

		<!-- Right column on desktop -->
		<div class="space-y-6">
			<BehaviorSection />
			<EnrichmentSection />
			<FieldPrefsSection />
			<AboutSection />
			<LogsSection />
		</div>
	</div>

	<!-- Bottom spacing for nav -->
	<div class="h-4"></div>
</div>
