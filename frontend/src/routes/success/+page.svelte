<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { isAuthenticated } from '$lib/stores/auth';
	import { resetLocationState } from '$lib/stores/locations';
	import { resetItemState } from '$lib/stores/items';
	import Button from '$lib/components/Button.svelte';

	// Redirect if not authenticated
	onMount(() => {
		if (!$isAuthenticated) {
			goto('/');
		}
	});

	function scanMore() {
		// Keep location selected, just reset items
		resetItemState();
		goto('/capture');
	}

	function startOver() {
		// Reset everything
		resetLocationState();
		resetItemState();
		goto('/location');
	}
</script>

<svelte:head>
	<title>Success - Homebox Companion</title>
</svelte:head>

<div class="flex flex-col items-center justify-center min-h-[60vh] animate-in text-center">
	<!-- Success animation -->
	<div class="relative w-24 h-24 mb-8">
		<div class="absolute inset-0 bg-success/20 rounded-full animate-ping"></div>
		<div class="absolute inset-0 flex items-center justify-center">
			<svg class="w-16 h-16 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
				<polyline points="22 4 12 14.01 9 11.01" />
			</svg>
		</div>
	</div>

	<h2 class="text-3xl font-bold text-text mb-2">Success!</h2>
	<p class="text-text-muted mb-8">Items have been added to your inventory</p>

	<div class="w-full max-w-sm space-y-3">
		<Button variant="primary" full onclick={scanMore}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
				<circle cx="12" cy="13" r="4" />
			</svg>
			<span>Scan More Items</span>
		</Button>

		<Button variant="secondary" full onclick={startOver}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<polyline points="1 4 1 10 7 10" />
				<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
			</svg>
			<span>Change Location</span>
		</Button>
	</div>
</div>





