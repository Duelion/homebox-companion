<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { resetLocationState } from '$lib/stores/locations';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { routeGuards } from '$lib/utils/routeGuard';
	import Button from '$lib/components/Button.svelte';

	const workflow = scanWorkflow;

	// Get submission result
	const result = $derived(workflow.submissionResult);

	// Animation state - stop ping after a few cycles
	let showPing = $state(true);

	// Apply route guard: requires authentication only
	onMount(async () => {
		if (!routeGuards.success()) return;

		// Stop the ping animation after 3 seconds
		setTimeout(() => {
			showPing = false;
		}, 3000);
	});

	function scanMore() {
		// Keep location, start new scan
		workflow.startNew();
		goto('/capture');
	}

	function startOver() {
		// Reset everything including location selection UI
		workflow.reset();
		resetLocationState();
		goto('/location');
	}
</script>

<svelte:head>
	<title>Success - Homebox Companion</title>
</svelte:head>

<div class="flex flex-col items-center justify-center min-h-[60vh] animate-in text-center px-4">
	<!-- Success animation with animated checkmark -->
	<div class="relative w-28 h-28 mb-8">
		<!-- Ping animation (stops after 3 seconds) -->
		{#if showPing}
			<div class="absolute inset-0 bg-success-500/20 rounded-full animate-ping"></div>
		{/if}
		<!-- Outer glow ring - scales in -->
		<div class="absolute inset-0 bg-success-500/10 rounded-full success-scale"></div>
		<!-- Inner circle - scales in with slight delay -->
		<div class="absolute inset-2 bg-success-500/20 rounded-full success-scale" style="animation-delay: 0.1s;"></div>
		<!-- Checkmark icon with draw animation -->
		<div class="absolute inset-0 flex items-center justify-center success-scale" style="animation-delay: 0.15s;">
			<svg class="w-14 h-14 text-success-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
				<path class="checkmark-draw" stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
			</svg>
		</div>
	</div>

	<!-- Heading -->
	<h2 class="text-h1 text-neutral-100 mb-3">Success!</h2>

	<!-- Specific feedback with count and location -->
	{#if result}
		<p class="text-body text-neutral-300 mb-6">
			{result.itemCount} item{result.itemCount !== 1 ? 's' : ''} added to {result.locationName}
		</p>

		<!-- Statistics card -->
		<div class="w-full max-w-sm bg-neutral-900 border border-neutral-700 rounded-2xl p-4 mb-8">
			<div class="grid grid-cols-2 gap-4 text-center">
				<div>
					<div class="text-2xl font-bold text-primary-400">{result.itemCount}</div>
					<div class="text-caption text-neutral-500">Item{result.itemCount !== 1 ? 's' : ''}</div>
				</div>
				<div>
					<div class="text-2xl font-bold text-primary-400">{result.photoCount}</div>
					<div class="text-caption text-neutral-500">Photo{result.photoCount !== 1 ? 's' : ''}</div>
				</div>
			</div>
		</div>
	{:else}
		<p class="text-body text-neutral-400 mb-8">Items have been added to your inventory</p>
	{/if}

	<!-- Action buttons -->
	<div class="w-full max-w-sm space-y-3">
		<!-- Scan more (with location context) -->
		<Button variant="primary" full onclick={scanMore}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
				<circle cx="12" cy="13" r="4" />
			</svg>
			<span>
				{#if result?.locationName}
					Scan More in {result.locationName}
				{:else}
					Scan More Items
				{/if}
			</span>
		</Button>

		<!-- Change location -->
		<Button variant="secondary" full onclick={startOver}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
				<circle cx="12" cy="10" r="3" />
			</svg>
			<span>Choose New Location</span>
		</Button>
	</div>
</div>
