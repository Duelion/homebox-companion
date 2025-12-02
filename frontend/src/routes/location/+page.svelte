<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { locations as locationsApi, labels as labelsApi, type LocationData, type LocationTreeNode } from '$lib/api';
	import { isAuthenticated } from '$lib/stores/auth';
	import {
		locationTree,
		locationPath,
		currentLevelLocations,
		selectedLocation,
		selectedLocationPath,
		resetLocationState,
		type PathItem,
	} from '$lib/stores/locations';
	import { labels } from '$lib/stores/items';
	import { showToast, setLoading } from '$lib/stores/ui';
	import Button from '$lib/components/Button.svelte';
	import Loader from '$lib/components/Loader.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';

	let isLoadingLocations = $state(true);

	// Redirect if not authenticated
	onMount(async () => {
		if (!$isAuthenticated) {
			goto('/');
			return;
		}

		await loadLocations();
		await loadLabels();
	});

	async function loadLocations() {
		isLoadingLocations = true;
		try {
			const tree = await locationsApi.tree();
			locationTree.set(tree);
			currentLevelLocations.set(tree);
		} catch (error) {
			console.error('Failed to load locations:', error);
			showToast('Failed to load locations', 'error');
		} finally {
			isLoadingLocations = false;
		}
	}

	async function loadLabels() {
		try {
			const labelList = await labelsApi.list();
			labels.set(labelList);
		} catch (error) {
			console.error('Failed to load labels:', error);
		}
	}

	async function navigateInto(location: LocationData) {
		// If this location has children, navigate into it
		if (location.children && location.children.length > 0) {
			locationPath.update((path) => [...path, { id: location.id, name: location.name }]);
			currentLevelLocations.set(location.children);
		} else {
			// No children, select this location
			selectLocation(location);
		}
	}

	function selectLocation(location: LocationData) {
		selectedLocation.set(location);
	}

	function navigateToPath(index: number) {
		if (index === -1) {
			// Go to root
			locationPath.set([]);
			currentLevelLocations.set($locationTree);
		} else {
			// Navigate to specific path item
			const newPath = $locationPath.slice(0, index + 1);
			locationPath.set(newPath);
			
			// Find the location at this path
			let current: LocationData[] = $locationTree;
			for (const pathItem of newPath) {
				const loc = current.find((l) => l.id === pathItem.id);
				if (loc?.children) {
					current = loc.children;
				}
			}
			currentLevelLocations.set(current);
		}
	}

	function clearSelection() {
		selectedLocation.set(null);
	}

	function useCurrentLocation() {
		// Select the current navigated location (last in path)
		if ($locationPath.length > 0) {
			const lastPath = $locationPath[$locationPath.length - 1];
			// Find full location data
			let current: LocationData[] = $locationTree;
			let found: LocationData | null = null;
			for (const pathItem of $locationPath) {
				const loc = current.find((l) => l.id === pathItem.id);
				if (loc) {
					found = loc;
					if (loc.children) {
						current = loc.children;
					}
				}
			}
			if (found) {
				selectedLocation.set(found);
			}
		}
	}

	function continueToCapture() {
		if (!$selectedLocation) {
			showToast('Please select a location', 'warning');
			return;
		}
		goto('/capture');
	}
</script>

<svelte:head>
	<title>Select Location - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	<StepIndicator currentStep={1} />

	<h2 class="text-2xl font-bold text-text mb-2">Select Location</h2>
	<p class="text-text-muted mb-6">Navigate to choose where your items will be stored</p>

	<!-- Breadcrumb -->
	<div class="flex items-center gap-1 overflow-x-auto pb-2 mb-4 text-sm">
		<button
			type="button"
			class="flex items-center gap-1 px-2 py-1 rounded-lg text-text-muted hover:text-text hover:bg-surface-elevated transition-colors whitespace-nowrap"
			onclick={() => navigateToPath(-1)}
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
				<polyline points="9 22 9 12 15 12 15 22" />
			</svg>
			<span>All</span>
		</button>

		{#each $locationPath as pathItem, index}
			<svg class="w-4 h-4 text-text-dim shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<polyline points="9 18 15 12 9 6" />
			</svg>
			<button
				type="button"
				class="px-2 py-1 rounded-lg text-text-muted hover:text-text hover:bg-surface-elevated transition-colors whitespace-nowrap"
				onclick={() => navigateToPath(index)}
			>
				{pathItem.name}
			</button>
		{/each}
	</div>

	<!-- Selected location display -->
	{#if $selectedLocation}
		<div class="flex items-center gap-3 p-3 mb-4 bg-primary/10 border border-primary/20 rounded-xl">
			<div class="p-2 bg-primary/20 rounded-lg">
				<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
					<circle cx="12" cy="10" r="3" />
				</svg>
			</div>
			<div class="flex-1 min-w-0">
				<p class="text-xs text-primary-light">Selected:</p>
				<p class="text-text font-medium truncate">{$selectedLocationPath}</p>
			</div>
		<button
			type="button"
			class="p-2 text-text-muted hover:text-text hover:bg-surface-elevated rounded-lg transition-colors"
			aria-label="Clear selection"
			onclick={clearSelection}
		>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
			</button>
		</div>
	{/if}

	<!-- Location list -->
	<div class="space-y-2 mb-6">
		{#if isLoadingLocations}
			<div class="py-12">
				<Loader message="Loading locations..." />
			</div>
		{:else if $currentLevelLocations.length === 0}
			<div class="py-12 text-center text-text-muted">
				<svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
					<circle cx="12" cy="10" r="3" />
				</svg>
				<p>No locations found</p>
			</div>
		{:else}
			{#each $currentLevelLocations as location}
			<button
				type="button"
				class="w-full flex items-center gap-3 p-4 rounded-xl border transition-all text-left group {$selectedLocation?.id === location.id ? 'bg-primary/5 border-primary' : 'bg-surface border-border hover:border-primary/30 hover:bg-surface-elevated'}"
				onclick={() => navigateInto(location)}
				>
					<div class="p-2 bg-surface-elevated rounded-lg group-hover:bg-primary/20 transition-colors">
						<svg class="w-5 h-5 text-text-muted group-hover:text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
							<circle cx="12" cy="10" r="3" />
						</svg>
					</div>
					<div class="flex-1 min-w-0">
						<p class="font-medium text-text truncate">{location.name}</p>
						{#if location.description}
							<p class="text-sm text-text-muted truncate">{location.description}</p>
						{/if}
					</div>
					{#if location.children && location.children.length > 0}
						<div class="flex items-center gap-1 text-text-dim text-sm">
							<span>{location.children.length}</span>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<polyline points="9 18 15 12 9 6" />
							</svg>
						</div>
					{:else if location.itemCount !== undefined}
						<span class="text-sm text-text-dim">{location.itemCount} items</span>
					{/if}
				</button>
			{/each}
		{/if}
	</div>

	<!-- Use current location button (when navigated into a location with children) -->
	{#if $locationPath.length > 0 && !$selectedLocation}
		<Button variant="secondary" full onclick={useCurrentLocation}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
				<circle cx="12" cy="10" r="3" />
			</svg>
			<span>Use This Location</span>
		</Button>
		<div class="h-3"></div>
	{/if}

	<Button variant="primary" full disabled={!$selectedLocation} onclick={continueToCapture}>
		<span>Continue to Capture</span>
		<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<line x1="5" y1="12" x2="19" y2="12" />
			<polyline points="12 5 19 12 12 19" />
		</svg>
	</Button>
</div>

