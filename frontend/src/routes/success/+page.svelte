<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { Check, Camera, Package, MapPin } from 'lucide-svelte';
	import { resetLocationState } from '$lib/stores/locations.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { routeGuards } from '$lib/utils/routeGuard';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import Button from '$lib/components/Button.svelte';
	import CreatedItemPickerModal from '$lib/components/CreatedItemPickerModal.svelte';

	const workflow = scanWorkflow;

	// Get submission result
	const result = $derived(workflow.submissionResult);

	// Animation state - stop ping after a few cycles
	let showPing = $state(true);

	// Modal state for parent item picker
	let showParentPicker = $state(false);

	// Apply route guard: requires authentication only
	onMount(async () => {
		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		if (!routeGuards.success()) return;

		// Stop the ping animation after 3 seconds
		setTimeout(() => {
			showPing = false;
		}, 3000);
	});

	function scanMore() {
		// Keep location, start new scan
		workflow.startNew();
		goto(resolve('/capture'));
	}

	function startOver() {
		// Reset everything including location selection UI
		workflow.reset();
		resetLocationState();
		goto(resolve('/location'));
	}

	function handleParentSelected(id: string, name: string) {
		// Set the selected item as parent for next scan
		workflow.setParentItem(id, name);
		// Start new scan with parent set
		workflow.startNew();
		goto(resolve('/capture'));
	}
</script>

<svelte:head>
	<title>Success - Homebox Companion</title>
</svelte:head>

<div class="animate-in flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
	<!-- Success animation with animated checkmark -->
	<div class="relative mb-8 h-28 w-28">
		<!-- Ping animation (stops after 3 seconds) -->
		{#if showPing}
			<div class="absolute inset-0 animate-ping rounded-full bg-success-500/20"></div>
		{/if}
		<!-- Outer glow ring - scales in -->
		<div class="success-scale absolute inset-0 rounded-full bg-success-500/10"></div>
		<!-- Inner circle - scales in with slight delay -->
		<div class="success-scale absolute inset-2 rounded-full bg-success-500/20 delay-100"></div>
		<!-- Checkmark icon with draw animation -->
		<div class="success-scale absolute inset-0 flex items-center justify-center delay-150">
			<Check class="checkmark-draw h-14 w-14 text-success-500" strokeWidth={2.5} />
		</div>
	</div>

	<!-- Heading -->
	<h2 class="mb-3 text-h1 text-neutral-100">Success!</h2>

	<!-- Specific feedback with count and location -->
	{#if result}
		<p class="mb-6 text-body text-neutral-300">
			{result.itemCount} item{result.itemCount !== 1 ? 's' : ''} added to {result.locationName}
		</p>

		<!-- Statistics card -->
		<div class="mb-8 w-full max-w-sm rounded-2xl border border-neutral-700 bg-neutral-900 p-4">
			<div class="grid grid-cols-2 gap-4 text-center">
				<div>
					<div class="text-2xl font-bold text-primary-400">
						{result.itemCount}
					</div>
					<div class="text-caption text-neutral-500">
						Item{result.itemCount !== 1 ? 's' : ''}
					</div>
				</div>
				<div>
					<div class="text-2xl font-bold text-primary-400">
						{result.photoCount}
					</div>
					<div class="text-caption text-neutral-500">
						Photo{result.photoCount !== 1 ? 's' : ''}
					</div>
				</div>
			</div>
		</div>
	{:else}
		<p class="mb-8 text-body text-neutral-400">Items have been added to your inventory</p>
	{/if}

	<!-- Action buttons -->
	<div class="w-full max-w-sm space-y-3">
		<!-- Scan more (with location context) -->
		<Button variant="primary" full onclick={scanMore}>
			<Camera size={20} strokeWidth={1.5} />
			<span>
				{#if result?.locationName}
					Scan More in {result.locationName}
				{:else}
					Scan More Items
				{/if}
			</span>
		</Button>

		<!-- Add sub-items to created items (only show if there are created items) -->
		{#if result?.createdItems && result.createdItems.length > 0}
			<Button variant="secondary" full onclick={() => (showParentPicker = true)}>
				<Package size={20} strokeWidth={1.5} />
				<span>Add Sub-Items to These</span>
			</Button>
		{/if}

		<!-- Change location -->
		<Button variant="secondary" full onclick={startOver}>
			<MapPin size={20} strokeWidth={1.5} />
			<span>Choose New Location</span>
		</Button>
	</div>
</div>

<!-- Parent item picker modal -->
{#if showParentPicker && result?.createdItems}
	<CreatedItemPickerModal
		items={result.createdItems}
		onSelect={handleParentSelected}
		onClose={() => (showParentPicker = false)}
	/>
{/if}
