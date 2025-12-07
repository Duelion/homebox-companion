<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { locations as locationsApi, labels as labelsApi, type LocationData, type LocationTreeNode } from '$lib/api';
	import { isAuthenticated, sessionExpired } from '$lib/stores/auth';
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
	import LocationModal from '$lib/components/LocationModal.svelte';
	import BackLink from '$lib/components/BackLink.svelte';

	let isLoadingLocations = $state(true);
	let searchQuery = $state('');
	let allLocationsFlat = $state<{ location: LocationData; path: string }[]>([]);

	// Track previous session expired state to detect re-authentication
	let wasSessionExpired = $state(false);

	// Modal state
	let showLocationModal = $state(false);
	let locationModalMode = $state<'create' | 'edit'>('create');
	let createParentLocation = $state<{ id: string; name: string } | null>(null);

	// Derived: filtered locations based on search
	let filteredLocations = $derived(
		searchQuery.trim() === ''
			? []
			: allLocationsFlat.filter(
					(item) =>
						item.location.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
						item.path.toLowerCase().includes(searchQuery.toLowerCase())
				)
	);

	// Are we in search mode?
	let isSearching = $derived(searchQuery.trim().length > 0);

	// Reload locations when session is restored after expiry
	$effect(() => {
		const currentExpired = $sessionExpired;
		if (wasSessionExpired && !currentExpired) {
			// Session was restored after expiry - reload data
			loadLocations();
			loadLabels();
		}
		wasSessionExpired = currentExpired;
	});

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
			// Build flat list with paths for search
			allLocationsFlat = flattenLocations(tree, '');
		} catch (error) {
			console.error('Failed to load locations:', error);
			showToast('Failed to load locations', 'error');
		} finally {
			isLoadingLocations = false;
		}
	}

	// Recursively flatten all locations with their full paths
	function flattenLocations(locations: LocationData[], parentPath: string): { location: LocationData; path: string }[] {
		const result: { location: LocationData; path: string }[] = [];
		for (const loc of locations) {
			const currentPath = parentPath ? `${parentPath} › ${loc.name}` : loc.name;
			result.push({ location: loc, path: currentPath });
			if (loc.children && loc.children.length > 0) {
				result.push(...flattenLocations(loc.children, currentPath));
			}
		}
		return result;
	}

	// Find a location by ID in the tree
	function findLocationById(locations: LocationData[], id: string): LocationData | null {
		for (const loc of locations) {
			if (loc.id === id) return loc;
			if (loc.children && loc.children.length > 0) {
				const found = findLocationById(loc.children, id);
				if (found) return found;
			}
		}
		return null;
	}

	async function loadLabels() {
		try {
			const labelList = await labelsApi.list();
			labels.set(labelList);
		} catch (error) {
			console.error('Failed to load labels:', error);
		}
	}

	function navigateInto(location: LocationData) {
		// If this location has children, navigate into it
		if (location.children && location.children.length > 0) {
			locationPath.update((path) => [...path, { id: location.id, name: location.name }]);
			currentLevelLocations.set(location.children);
		} else {
			// No children, select this location directly
			selectLocation(location);
		}
	}

	function selectLocation(location: LocationData) {
		selectedLocation.set(location);
		searchQuery = ''; // Clear search when selecting
	}

	function selectFromSearch(item: { location: LocationData; path: string }) {
		selectedLocation.set(item.location);
		searchQuery = ''; // Clear search
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

	function changeSelection() {
		selectedLocation.set(null);
		// Reset to root for fresh selection
		locationPath.set([]);
		currentLevelLocations.set($locationTree);
	}

	function continueToCapture() {
		if (!$selectedLocation) {
			showToast('Please select a location', 'warning');
			return;
		}
		goto('/capture');
	}

	// Get the current parent for new locations (based on navigation path)
	function getCurrentParent(): { id: string; name: string } | null {
		if ($locationPath.length === 0) return null;
		const last = $locationPath[$locationPath.length - 1];
		return { id: last.id, name: last.name };
	}

	function openCreateModal(parent: { id: string; name: string } | null = null) {
		locationModalMode = 'create';
		createParentLocation = parent;
		showLocationModal = true;
	}

	function openCreateSubLocationModal() {
		if ($selectedLocation) {
			openCreateModal({ id: $selectedLocation.id, name: $selectedLocation.name });
		}
	}

	function openEditModal() {
		locationModalMode = 'edit';
		showLocationModal = true;
	}

	async function handleSaveLocation(data: { name: string; description: string; parentId: string | null }) {
		if (locationModalMode === 'create') {
			// Create new location
			const newLocation = await locationsApi.create({
				name: data.name,
				description: data.description,
				parent_id: data.parentId,
			});

			showToast(`Created "${newLocation.name}"`, 'success');

			// Remember the current navigation path before refreshing
			const savedPath = [...$locationPath];
			
			// Refresh the location tree to show the new location
			await loadLocations();

			// If we created from a selected location (Add sub-location button)
			if ($selectedLocation) {
				// Clear selection and navigate to show the parent's children
				selectedLocation.set(null);
				
				// Set the path to the selected location so we can see the new sub-location
				const parentId = data.parentId;
				if (parentId) {
					// Navigate into the parent to show the new location
					const parentLoc = findLocationById($locationTree, parentId);
					if (parentLoc) {
						locationPath.set([{ id: parentLoc.id, name: parentLoc.name }]);
						currentLevelLocations.set(parentLoc.children || []);
					}
				} else {
					locationPath.set([]);
					currentLevelLocations.set($locationTree);
				}
			} else if (savedPath.length > 0) {
				// We were in browse mode inside a folder - restore that navigation
				locationPath.set(savedPath);
				
				// Navigate to that path in the refreshed tree
				let current: LocationData[] = $locationTree;
				for (const pathItem of savedPath) {
					const loc = current.find((l) => l.id === pathItem.id);
					if (loc?.children) {
						current = loc.children;
					}
				}
				currentLevelLocations.set(current);
			}
		} else if (locationModalMode === 'edit' && $selectedLocation) {
			// Update existing location
			const updatedLocation = await locationsApi.update($selectedLocation.id, {
				name: data.name,
				description: data.description,
			});

			showToast(`Updated "${updatedLocation.name}"`, 'success');

			// Refresh the location tree
			await loadLocations();

			// Update the selected location with new data
			const locationData: LocationData = {
				id: updatedLocation.id,
				name: updatedLocation.name,
				description: updatedLocation.description,
				children: $selectedLocation.children || [],
			};
			selectedLocation.set(locationData);
		}
	}
</script>

<svelte:head>
	<title>Select Location - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	{#if $selectedLocation}
		<BackLink href="/location" label="Choose a different location" onclick={changeSelection} />
	{/if}

	<StepIndicator currentStep={1} />

	<h2 class="text-2xl font-bold text-text mb-2">Select Location</h2>
	<p class="text-text-muted mb-6">Choose where your items will be stored</p>

	{#if isLoadingLocations}
		<div class="py-12">
			<Loader message="Loading locations..." />
		</div>
	{:else if $selectedLocation}
		<!-- SELECTED STATE: Show only the selected location with confirm -->
		<div class="space-y-4">
			<div class="bg-surface rounded-xl border border-primary p-4">
				<div class="flex items-center gap-3">
					<div class="p-3 bg-primary/20 rounded-lg">
						<svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
							<circle cx="12" cy="10" r="3" />
						</svg>
					</div>
					<div class="flex-1 min-w-0">
						<p class="text-sm text-text-muted">Selected location:</p>
						<p class="text-lg font-semibold text-text">{$selectedLocation.name}</p>
						{#if $selectedLocationPath !== $selectedLocation.name}
							<p class="text-sm text-text-dim">{$selectedLocationPath}</p>
						{/if}
						{#if $selectedLocation.description}
							<p class="text-sm text-text-muted mt-1">{$selectedLocation.description}</p>
						{/if}
					</div>
					<!-- Edit button -->
					<button
						type="button"
						class="p-2 rounded-lg text-text-muted hover:text-primary hover:bg-primary/10 transition-colors"
						onclick={openEditModal}
						title="Edit location"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
							<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
						</svg>
					</button>
				</div>
			</div>

			<!-- Add sub-location button -->
			<button
				type="button"
				class="w-full p-3 text-center text-primary hover:bg-primary/10 rounded-xl border border-dashed border-primary/40 transition-colors"
				onclick={openCreateSubLocationModal}
			>
				<span class="flex items-center justify-center gap-2 whitespace-nowrap">
					<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<line x1="12" y1="5" x2="12" y2="19" />
						<line x1="5" y1="12" x2="19" y2="12" />
					</svg>
					Add sub-location
				</span>
			</button>

			<Button variant="primary" full onclick={continueToCapture}>
				<span>Continue to Capture</span>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<line x1="5" y1="12" x2="19" y2="12" />
					<polyline points="12 5 19 12 12 19" />
				</svg>
			</Button>
		</div>
	{:else}
		<!-- SELECTION STATE: Show search and location list -->
		
		<!-- Search box -->
		<div class="relative mb-4">
			<div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
				<svg class="w-5 h-5 text-text-dim" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<circle cx="11" cy="11" r="8" />
					<path d="m21 21-4.35-4.35" />
				</svg>
			</div>
			<input
				type="text"
				placeholder="Search all locations..."
				bind:value={searchQuery}
				class="w-full pl-10 pr-4 py-3 bg-surface border border-border rounded-xl text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
			/>
			{#if searchQuery}
				<button
					type="button"
					class="absolute inset-y-0 right-0 pr-3 flex items-center text-text-muted hover:text-text"
					aria-label="Clear search"
					onclick={() => searchQuery = ''}
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<line x1="18" y1="6" x2="6" y2="18" />
						<line x1="6" y1="6" x2="18" y2="18" />
					</svg>
				</button>
			{/if}
		</div>

		{#if isSearching}
			<!-- SEARCH RESULTS: Flat list with full paths -->
			<div class="space-y-2">
				{#if filteredLocations.length === 0}
					<div class="py-8 text-center text-text-muted">
						<svg class="w-10 h-10 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<circle cx="11" cy="11" r="8" />
							<path d="m21 21-4.35-4.35" />
						</svg>
						<p>No locations found for "{searchQuery}"</p>
					</div>
				{:else}
					<p class="text-sm text-text-muted mb-2">{filteredLocations.length} location{filteredLocations.length !== 1 ? 's' : ''} found</p>
					{#each filteredLocations as item}
						<button
							type="button"
							class="w-full flex items-center gap-3 p-4 rounded-xl border bg-surface border-border hover:border-primary/30 hover:bg-surface-elevated transition-all text-left group"
							onclick={() => selectFromSearch(item)}
						>
							<div class="p-2 bg-surface-elevated rounded-lg group-hover:bg-primary/20 transition-colors">
								<svg class="w-5 h-5 text-text-muted group-hover:text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
									<circle cx="12" cy="10" r="3" />
								</svg>
							</div>
							<div class="flex-1 min-w-0">
								<p class="font-medium text-text">{item.location.name}</p>
								<p class="text-sm text-text-dim truncate">{item.path}</p>
							</div>
							{#if item.location.itemCount !== undefined}
								<span class="text-sm text-text-dim">{item.location.itemCount} items</span>
							{/if}
						</button>
					{/each}
				{/if}
			</div>
		{:else}
			<!-- BROWSE MODE: Hierarchical navigation -->
			
			<!-- Breadcrumb -->
			{#if $locationPath.length > 0}
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

				<!-- Select current folder button -->
				<button
					type="button"
					class="w-full flex items-center gap-3 p-3 mb-4 rounded-xl border border-dashed border-primary/30 bg-primary/5 hover:bg-primary/10 transition-colors text-left"
					aria-label="Select current location"
					onclick={() => {
						const lastPath = $locationPath[$locationPath.length - 1];
						// Find the location in the tree
						let current: LocationData[] = $locationTree;
						let found: LocationData | null = null;
						for (const pathItem of $locationPath) {
							const loc = current.find((l) => l.id === pathItem.id);
							if (loc) {
								found = loc;
								if (loc.children) current = loc.children;
							}
						}
						if (found) selectLocation(found);
					}}
				>
					<div class="p-2 bg-primary/20 rounded-lg">
						<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<polyline points="20 6 9 17 4 12" />
						</svg>
					</div>
					<div class="flex-1">
						<p class="font-medium text-primary">Select "{$locationPath[$locationPath.length - 1].name}"</p>
						<p class="text-sm text-text-dim">Use this folder as item location</p>
					</div>
				</button>
			{/if}

			<!-- Location list -->
			<div class="space-y-2">
				{#if $currentLevelLocations.length === 0}
					<div class="py-8 text-center text-text-muted">
						<p>No sub-locations here</p>
					</div>
				{:else}
					{#each $currentLevelLocations as location}
						<button
							type="button"
							class="w-full flex items-center gap-3 p-4 rounded-xl border bg-surface border-border hover:border-primary/30 hover:bg-surface-elevated transition-all text-left group"
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

				<!-- Create new location button -->
				<button
					type="button"
					class="w-full flex items-center gap-3 p-4 rounded-xl border border-dashed border-primary/40 bg-primary/5 hover:bg-primary/10 hover:border-primary/60 transition-all text-left group"
					onclick={() => openCreateModal(getCurrentParent())}
				>
					<div class="p-2 bg-primary/20 rounded-lg">
						<svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<line x1="12" y1="5" x2="12" y2="19" />
							<line x1="5" y1="12" x2="19" y2="12" />
						</svg>
					</div>
					<div class="flex-1">
						<p class="font-medium text-primary">Create new location</p>
						<p class="text-sm text-text-dim">
							{#if $locationPath.length > 0}
								Add inside {$locationPath[$locationPath.length - 1].name}
							{:else}
								Add at root level
							{/if}
						</p>
					</div>
				</button>
			</div>
		{/if}
	{/if}
</div>

<!-- Location Modal for create/edit -->
<LocationModal
	bind:open={showLocationModal}
	mode={locationModalMode}
	location={locationModalMode === 'edit' ? $selectedLocation : null}
	parentLocation={locationModalMode === 'create' ? createParentLocation : null}
	onsave={handleSaveLocation}
/>
