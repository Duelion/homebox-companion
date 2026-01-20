<script lang="ts">
	/**
	 * Settings Page - Thin orchestrator for settings sections.
	 *
	 * This page delegates all state management and business logic to:
	 * - settingsService: Centralized state and API calls
	 * - Section components: UI rendering for each settings area
	 */
	import { AlertTriangle } from 'lucide-svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, onDestroy } from 'svelte';
	import { authStore } from '$lib/stores/auth.svelte';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import { settingsService } from '$lib/workflows/settings.svelte';

	import AccountSection from '$lib/components/settings/AccountSection.svelte';
	import AboutSection from '$lib/components/settings/AboutSection.svelte';
	import FieldPrefsSection from '$lib/components/settings/FieldPrefsSection.svelte';
	import LLMProfilesSection from '$lib/components/settings/LLMProfilesSection.svelte';
	import LogsSection from '$lib/components/settings/LogsSection.svelte';

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

<div class="animate-in space-y-6">
	<div>
		<h1 class="text-h1 font-bold text-neutral-100">Settings</h1>
		<p class="mt-1 text-body-sm text-neutral-400">App configuration and information</p>
	</div>

	{#if settingsService.errors.init}
		<div class="card border-error-500/30 bg-error-500/10">
			<div class="flex items-start gap-3">
				<AlertTriangle class="mt-0.5 flex-shrink-0 text-error-500" size={20} strokeWidth={1.5} />
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

	<AccountSection />
	<AboutSection />
	<LLMProfilesSection />
	<FieldPrefsSection />
	<LogsSection />

	<!-- Bottom spacing for nav -->
	<div class="h-4"></div>
</div>
