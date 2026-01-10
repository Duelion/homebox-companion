<script lang="ts">
	/**
	 * AccountSection - User account info and logout button.
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { authStore } from '$lib/stores/auth.svelte';
	import { resetLocationState } from '$lib/stores/locations.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import Button from '$lib/components/Button.svelte';
	import CollapsibleSection from './CollapsibleSection.svelte';

	function handleLogout() {
		scanWorkflow.reset();
		resetLocationState();
		settingsService.reset();
		authStore.logout();
		goto(resolve('/'));
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
		<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
		<circle cx="12" cy="7" r="4" />
	</svg>
{/snippet}

<CollapsibleSection title="Account" {icon}>
	<!-- Signed in as -->
	{#if authStore.email}
		<div
			class="flex items-center gap-3 rounded-xl border border-base-content/10 bg-base-200/50 p-4"
		>
			<div
				class="flex h-10 w-10 items-center justify-center rounded-full bg-primary/20 text-primary"
			>
				<svg
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
					<circle cx="12" cy="7" r="4" />
				</svg>
			</div>
			<div class="min-w-0 flex-1">
				<p class="text-xs text-base-content/50">Signed in as</p>
				<p class="truncate font-medium text-base-content">{authStore.email}</p>
			</div>
		</div>
	{/if}

	<Button variant="danger" full onclick={handleLogout}>
		<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
			<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
			<polyline points="16 17 21 12 16 7" />
			<line x1="21" y1="12" x2="9" y2="12" />
		</svg>
		<span>Sign Out</span>
	</Button>
</CollapsibleSection>
