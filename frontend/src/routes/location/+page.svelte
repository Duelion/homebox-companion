<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { locations as locationsApi } from '$lib/api';
	import { sessionExpired } from '$lib/stores/auth';
	import {
		locationTree,
		locationPath,
		currentLevelLocations,
		selectedLocation,
		selectedLocationPath,
	} from '$lib/stores/locations';
	import { fetchLabels } from '$lib/stores/labels';
	import { showToast } from '$lib/stores/ui';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { routeGuards } from '$lib/utils/routeGuard';
	import { createLogger } from '$lib/utils/logger';
	import type { Location } from '$lib/types';
	import Button from '$lib/components/Button.svelte';
	import Loader from '$lib/components/Loader.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import LocationModal from '$lib/components/LocationModal.svelte';
	import ItemPickerModal from '$lib/components/ItemPickerModal.svelte';
	import BackLink from '$lib/components/BackLink.svelte';
	import QrScanner from '$lib/components/QrScanner.svelte';

	const log = createLogger({ prefix: 'LocationPage' });

	// Local UI state
	let isLoadingLocations = $state(true);
	let searchQuery = $state('');
	let allLocationsFlat = $state<{ location: Location; path: string }[]>([]);
	let wasSessionExpired = $state(false);
	// Store the current location we're viewing (from navigateInto) for accurate selection
	let currentNavigatedLocation = $state<Location | null>(null);

	// Modal state
	let showLocationModal = $state(false);
	let locationModalMode = $state<'create' | 'edit'>('create');
	let createParentLocation = $state<{ id: string; name: string } | null>(null);

	// Item picker modal state
	let showItemPicker = $state(false);

	// QR Scanner state
	let showQrScanner = $state(false);
	let isProcessingQr = $state(false);

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

	let isSearching = $derived(searchQuery.trim().length > 0);

	// Reload locations when session is restored after expiry
	$effect(() => {
		const currentExpired = $sessionExpired;
		if (wasSessionExpired && !currentExpired) {
			loadLocations();
			fetchLabels();
		}
		wasSessionExpired = currentExpired;
	});

	// Apply route guard: requires auth, redirects to capture if already in workflow
	onMount(async () => {
		if (!routeGuards.location()) return;

		await loadLocations();
		await fetchLabels();
	});

	async function loadLocations() {
		log.debug('Loading location tree');
		isLoadingLocations = true;
		currentNavigatedLocation = null;
		try {
			const tree = await locationsApi.tree();
			log.debug('Loaded location tree, top-level count:', tree.length);
			locationTree.set(tree);
			currentLevelLocations.set(tree);
			
			// Also load flat list for search (without tree structure)
			const flatList = await locationsApi.list();
			allLocationsFlat = flattenLocations(flatList, '');
		} catch (error) {
			log.error('Failed to load locations', error);
			showToast('Failed to load locations', 'error');
		} finally {
			isLoadingLocations = false;
		}
	}

	async function refreshCurrentLevel(parentId: string | null) {
		log.debug('Refreshing current level, parentId:', parentId);
		isLoadingLocations = true;
		try {
			if (parentId) {
				// Refresh children of the parent location
				const details = await locationsApi.get(parentId);
				currentLevelLocations.set(details.children || []);
				// Update the current navigated location with fresh data
				currentNavigatedLocation = {
					id: details.id,
					name: details.name,
					description: details.description || '',
					itemCount: details.itemCount ?? 0,
					children: details.children || [],
				};
			} else {
				// Refresh top-level locations
				const tree = await locationsApi.tree();
				locationTree.set(tree);
				currentLevelLocations.set(tree);
				currentNavigatedLocation = null;
			}
			
			// Also refresh flat list for search
			const flatList = await locationsApi.list();
			allLocationsFlat = flattenLocations(flatList, '');
		} catch (error) {
			log.error('Failed to refresh current level', error);
			showToast('Failed to refresh locations', 'error');
		} finally {
			isLoadingLocations = false;
		}
	}

	function flattenLocations(locations: Location[], parentPath: string): { location: Location; path: string }[] {
		const result: { location: Location; path: string }[] = [];
		for (const loc of locations) {
			const currentPath = parentPath ? `${parentPath} › ${loc.name}` : loc.name;
			result.push({ location: loc, path: currentPath });
			if (loc.children && loc.children.length > 0) {
				result.push(...flattenLocations(loc.children, currentPath));
			}
		}
		return result;
	}

	async function navigateInto(location: Location) {
		// Always navigate into the location's context, regardless of children
		log.debug('Navigating into location:', location.name, location.id);
		isLoadingLocations = true;
		try {
			const details = await locationsApi.get(location.id);
			log.debug('Loaded location details, children:', details.children?.length ?? 0);
			locationPath.update((path) => [...path, { id: location.id, name: location.name }]);
			currentLevelLocations.set(details.children || []);
			// Store the current location with all its data including itemCount
			currentNavigatedLocation = {
				id: details.id,
				name: details.name,
				description: details.description || '',
				itemCount: details.itemCount ?? 0,
				children: details.children || [],
			};
		} catch (error) {
			log.error('Failed to load location details', error);
			showToast('Failed to load location details', 'error');
			// Fallback to using existing children data
			locationPath.update((path) => [...path, { id: location.id, name: location.name }]);
			currentLevelLocations.set(location.children || []);
			currentNavigatedLocation = location;
		} finally {
			isLoadingLocations = false;
		}
	}

	function selectLocation(location: Location, path: string) {
		log.debug('Selected location:', location.name, 'itemCount:', location.itemCount ?? 'unknown');
		// Update both the location store (for UI) and the workflow (for scan flow)
		selectedLocation.set(location);
		scanWorkflow.setLocation(location.id, location.name, path);
		searchQuery = '';
	}

	function selectFromSearch(item: { location: Location; path: string }) {
		selectLocation(item.location, item.path);
	}

	async function navigateToPath(index: number) {
		if (index === -1) {
			// Navigate back to root - refresh tree to ensure it's current
			isLoadingLocations = true;
			currentNavigatedLocation = null; // Clear current location
			try {
				const tree = await locationsApi.tree();
				locationTree.set(tree);
				locationPath.set([]);
				currentLevelLocations.set(tree);
			} catch (error) {
				log.error('Failed to refresh root locations', error);
				showToast('Failed to load locations', 'error');
				// Fallback to cached tree
				locationPath.set([]);
				currentLevelLocations.set($locationTree);
			} finally {
				isLoadingLocations = false;
			}
		} else {
			const newPath = $locationPath.slice(0, index + 1);
			locationPath.set(newPath);
			
			// Fetch fresh details for the target location to ensure children are up-to-date
			const targetId = newPath[newPath.length - 1].id;
			isLoadingLocations = true;
			try {
				const details = await locationsApi.get(targetId);
				currentLevelLocations.set(details.children || []);
				// Store the navigated location
				currentNavigatedLocation = {
					id: details.id,
					name: details.name,
					description: details.description || '',
					itemCount: details.itemCount ?? 0,
					children: details.children || [],
				};
		} catch (error) {
			log.error('Failed to load location details', error);
			showToast('Failed to navigate back', 'error');
			} finally {
				isLoadingLocations = false;
			}
		}
	}

	async function changeSelection() {
		const previousPath = [...$locationPath];
		selectedLocation.set(null);
		scanWorkflow.clearLocation();
		
		// If we had a path (user was inside a location), restore it
		if (previousPath.length > 0) {
			// Restore the path - user will be brought back to where they were browsing
			locationPath.set(previousPath);
			
			// Fetch the location details to get current children
			const lastPathItem = previousPath[previousPath.length - 1];
			isLoadingLocations = true;
			try {
				const details = await locationsApi.get(lastPathItem.id);
				currentLevelLocations.set(details.children || []);
				// Restore the current navigated location
				currentNavigatedLocation = {
					id: details.id,
					name: details.name,
					description: details.description || '',
					itemCount: details.itemCount ?? 0,
					children: details.children || [],
				};
			} catch (error) {
				log.error('Failed to load location details', error);
				showToast('Failed to restore navigation', 'error');
			} finally {
				isLoadingLocations = false;
			}
		} else {
			// Was at root level - refresh to show any new locations
			isLoadingLocations = true;
			currentNavigatedLocation = null;
			try {
				const tree = await locationsApi.tree();
				locationTree.set(tree);
				locationPath.set([]);
				currentLevelLocations.set(tree);
			} catch (error) {
				log.error('Failed to refresh locations', error);
				// Fallback to cached tree
				locationPath.set([]);
				currentLevelLocations.set($locationTree);
			} finally {
				isLoadingLocations = false;
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

	function openEditModal() {
		locationModalMode = 'edit';
		showLocationModal = true;
	}

	async function handleSaveLocation(data: { name: string; description: string; parentId: string | null }) {
		try {
			if (locationModalMode === 'create') {
				const newLocation = await locationsApi.create({
					name: data.name,
					description: data.description,
					parent_id: data.parentId,
				});

				log.debug('Created location:', newLocation.name, 'under parent:', data.parentId);
				
				// Refresh current level by fetching parent's children directly
				// This avoids tree traversal and works at any depth
				await refreshCurrentLevel(data.parentId);
				
				showToast(`Location "${newLocation.name}" created`, 'success');
			} else if (locationModalMode === 'edit' && $selectedLocation) {
				const updatedLocation = await locationsApi.update($selectedLocation.id, {
					name: data.name,
					description: data.description,
				});

				log.debug('Updated location:', updatedLocation.name);
				
				// Update selected location with new data
				const locationData: Location = {
					id: updatedLocation.id,
					name: updatedLocation.name,
					description: updatedLocation.description,
					children: $selectedLocation.children || [],
				};
				selectedLocation.set(locationData);
				
				// Update workflow with new name
				scanWorkflow.setLocation(locationData.id, locationData.name, $selectedLocationPath);
				
				// Refresh flat list for search to show updated name
				try {
					const flatList = await locationsApi.list();
					allLocationsFlat = flattenLocations(flatList, '');
				} catch (error) {
					log.warn('Failed to refresh search list after edit', error);
				}
				
				showToast(`Location "${updatedLocation.name}" updated`, 'success');
			}
		} catch (error) {
			log.error('Failed to save location', error);
			// Re-throw to let LocationModal handle the error display
			throw error;
		}
	}

	// QR Scanner handlers
	function openQrScanner() {
		showQrScanner = true;
	}

	function closeQrScanner() {
		showQrScanner = false;
	}

	async function handleQrScan(decodedText: string) {
		showQrScanner = false;
		isProcessingQr = true;

		try {
			// Parse the QR code URL to extract location ID
			// Expected format: https://homebox.example.com/location/{uuid}
			const locationIdMatch = decodedText.match(/\/location\/([a-f0-9-]+)(?:\/|$)/i);
			
			if (!locationIdMatch) {
				showToast('Invalid QR code. Not a Homebox location.', 'error');
				isProcessingQr = false;
				return;
			}

			const locationId = locationIdMatch[1];

			// Fetch location details from API
			const location = await locationsApi.get(locationId);

			if (!location) {
				showToast('Location not found in your Homebox.', 'error');
				isProcessingQr = false;
				return;
			}

			// Build location path - for QR scans, we just use the location name
			// since we don't have the parent hierarchy from a single API call
			const locationPath = location.name;

		// Set the location
		const locationData: Location = {
			id: location.id,
			name: location.name,
			description: location.description || '',
			itemCount: location.itemCount ?? 0,
			children: location.children || [],
		};

	selectedLocation.set(locationData);
		scanWorkflow.setLocation(locationData.id, locationData.name, locationPath);
	} catch (error) {
			log.error('QR scan error', error);
			if (error instanceof Error && error.message.includes('401')) {
				showToast('Session expired. Please log in again.', 'error');
			} else if (error instanceof Error && error.message.includes('404')) {
				showToast('Location not found in your Homebox.', 'error');
			} else {
				showToast('Failed to load location. Please try again.', 'error');
			}
		} finally {
			isProcessingQr = false;
		}
	}

	function handleQrError(error: string) {
		log.warn('QR Scanner error:', error);
	}

	// Item picker handlers
	function openItemPicker() {
		showItemPicker = true;
	}

	function handleParentItemSelect(id: string, name: string) {
		if (id && name) {
			scanWorkflow.setParentItem(id, name);
		} else {
			scanWorkflow.clearParentItem();
		}
	}
</script>

<svelte:head>
	<title>Select Location - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	<StepIndicator currentStep={1} />

	<h2 class="text-h2 text-neutral-100 mb-1">Select Location</h2>
	<p class="text-body-sm text-neutral-400 mb-6">Choose where your items will be stored</p>

	{#if $selectedLocation}
		<BackLink href="/location" label="Choose a different location" onclick={changeSelection} />
	{/if}

	{#if isLoadingLocations}
		<!-- Skeleton loading state -->
		<div class="space-y-3">
			<!-- Search skeleton -->
			<div class="flex gap-2 mb-4">
				<Skeleton width="100%" height="48px" rounded="xl" />
				<Skeleton width="48px" height="48px" rounded="xl" />
			</div>
			
			<!-- Location card skeletons -->
			{#each Array(6) as _, i}
				<div class="bg-neutral-900/50 border border-neutral-800 rounded-xl p-4 flex items-center gap-3" style="animation-delay: {i * 50}ms;">
					<Skeleton width="44px" height="44px" rounded="lg" />
					<div class="flex-1 space-y-2">
						<Skeleton width="60%" height="16px" rounded="md" />
						<Skeleton width="40%" height="12px" rounded="md" />
					</div>
					<Skeleton width="20px" height="20px" rounded="full" />
				</div>
			{/each}
			
			<!-- Create button skeleton -->
			<Skeleton width="100%" height="44px" rounded="xl" class="mt-4" />
		</div>
	{:else if $selectedLocation}
		<!-- SELECTED STATE -->
		<div class="space-y-4">
			<!-- Selected location card with ring highlight -->
			<div class="bg-neutral-900 rounded-xl border border-primary-500 ring-2 ring-primary-500/30 p-4 shadow-md">
				<div class="flex items-center gap-3">
					<div class="p-3 bg-primary-500/20 rounded-lg">
						<svg class="w-6 h-6 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
							<circle cx="12" cy="10" r="3" />
						</svg>
					</div>
					<div class="flex-1 min-w-0">
						<p class="text-body-sm text-neutral-400">Selected location:</p>
						<p class="text-body font-semibold text-neutral-100">{$selectedLocation.name}</p>
						{#if $selectedLocationPath !== $selectedLocation.name}
							<p class="text-body-sm text-neutral-500">{$selectedLocationPath}</p>
						{/if}
						{#if $selectedLocation.description}
							<p class="text-body-sm text-neutral-400 mt-1">{$selectedLocation.description}</p>
						{/if}
					</div>
					<button
						type="button"
						class="p-2 rounded-lg text-neutral-400 hover:text-primary-400 hover:bg-primary-500/10 transition-colors"
						onclick={openEditModal}
						title="Edit location"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
							<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
						</svg>
					</button>
				</div>
			</div>

			<!-- Assign to Container Item -->
			<Button 
				variant="secondary" 
				full 
				onclick={openItemPicker}
				disabled={($selectedLocation?.itemCount ?? 0) === 0}
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
					<path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
				</svg>
				<span>
					{#if scanWorkflow.state.parentItemName}
						Inside: {scanWorkflow.state.parentItemName} (change)
					{:else}
						Place Inside an Item ({$selectedLocation?.itemCount ?? 0})
					{/if}
				</span>
			</Button>

			<Button variant="primary" full onclick={continueToCapture}>
				<span>Continue to Capture</span>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
					<line x1="5" y1="12" x2="19" y2="12" />
					<polyline points="12 5 19 12 12 19" />
				</svg>
			</Button>
		</div>
	{:else}
		<!-- SELECTION STATE -->
		
		<!-- Search box with elevated style and QR scan button -->
		<div class="flex gap-2 mb-4">
			<div class="relative flex-1">
				<div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
					<svg class="w-5 h-5 text-neutral-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<circle cx="11" cy="11" r="8" />
						<path d="m21 21-4.35-4.35" />
					</svg>
				</div>
				<input
					type="text"
					placeholder="Search all locations..."
					bind:value={searchQuery}
					class="w-full h-12 pl-11 pr-10 bg-neutral-800 border border-neutral-600 rounded-xl text-neutral-100 placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-all"
				/>
				{#if searchQuery}
					<button
						type="button"
						class="absolute inset-y-0 right-0 pr-4 flex items-center text-neutral-400 hover:text-neutral-200 transition-colors"
						aria-label="Clear search"
						onclick={() => searchQuery = ''}
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<line x1="18" y1="6" x2="6" y2="18" />
							<line x1="6" y1="6" x2="18" y2="18" />
						</svg>
					</button>
				{/if}
			</div>
			
			<!-- QR Scan Button -->
			<button
				type="button"
				onclick={openQrScanner}
				disabled={isProcessingQr}
				class="w-12 h-12 flex items-center justify-center bg-neutral-800 border border-neutral-600 rounded-xl text-neutral-400 hover:text-primary-400 hover:border-primary-500/50 hover:bg-primary-500/5 transition-all disabled:opacity-50"
				title="Scan QR Code"
			>
				{#if isProcessingQr}
					<div class="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
				{:else}
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<!-- QR Code icon -->
						<rect x="3" y="3" width="7" height="7" rx="1" />
						<rect x="14" y="3" width="7" height="7" rx="1" />
						<rect x="3" y="14" width="7" height="7" rx="1" />
						<rect x="14" y="14" width="3" height="3" />
						<rect x="18" y="14" width="3" height="3" />
						<rect x="14" y="18" width="3" height="3" />
						<rect x="18" y="18" width="3" height="3" />
					</svg>
				{/if}
			</button>
		</div>

		{#if isSearching}
			<!-- SEARCH RESULTS -->
			<div class="space-y-2">
				{#if filteredLocations.length === 0}
					<div class="py-8 text-center text-neutral-500">
						<svg class="w-10 h-10 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<circle cx="11" cy="11" r="8" />
							<path d="m21 21-4.35-4.35" />
						</svg>
						<p>No locations found for "{searchQuery}"</p>
					</div>
				{:else}
					<p class="text-body-sm text-neutral-400 mb-2">{filteredLocations.length} location{filteredLocations.length !== 1 ? 's' : ''} found</p>
					{#each filteredLocations as item}
						<button
							type="button"
							class="w-full flex items-center gap-3 p-4 rounded-xl border bg-neutral-900 border-neutral-700 shadow-sm hover:shadow-md hover:border-neutral-600 transition-all text-left group"
							onclick={() => selectFromSearch(item)}
						>
							<div class="p-2.5 bg-neutral-800 rounded-lg group-hover:bg-primary-500/20 transition-colors">
								<svg class="w-5 h-5 text-neutral-400 group-hover:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
									<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
									<circle cx="12" cy="10" r="3" />
								</svg>
							</div>
							<div class="flex-1 min-w-0">
								<p class="font-medium text-neutral-100">{item.location.name}</p>
								<p class="text-body-sm text-neutral-500 truncate">{item.path}</p>
							</div>
							{#if item.location.itemCount !== undefined}
								<span class="text-body-sm text-neutral-500">{item.location.itemCount} items</span>
							{/if}
						</button>
					{/each}
				{/if}
			</div>
		{:else}
			<!-- BROWSE MODE -->
			
			{#if $locationPath.length > 0}
				<div class="flex items-center gap-1 overflow-x-auto pb-2 mb-4 text-sm">
					<button
						type="button"
						class="flex items-center gap-1 px-2 py-1 rounded-lg text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition-colors whitespace-nowrap"
						onclick={() => navigateToPath(-1)}
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
							<polyline points="9 22 9 12 15 12 15 22" />
						</svg>
						<span>All</span>
					</button>

					{#each $locationPath as pathItem, index}
						<svg class="w-4 h-4 text-neutral-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
							<polyline points="9 18 15 12 9 6" />
						</svg>
						<button
							type="button"
							class="px-2 py-1 rounded-lg text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition-colors whitespace-nowrap"
							onclick={() => navigateToPath(index)}
						>
							{pathItem.name}
						</button>
					{/each}
				</div>

		<!-- Select current folder button -->
		<button
			type="button"
			class="w-full flex items-center gap-3 p-4 mb-4 rounded-xl border bg-neutral-900 border-neutral-700 shadow-sm hover:shadow-md hover:border-primary-500 hover:bg-primary-500/5 transition-all text-left group"
			aria-label="Select current location"
			onclick={() => {
				// Use the stored current location from navigateInto instead of traversing stale tree
				if (currentNavigatedLocation) {
					const path = $locationPath.map(p => p.name).join(' / ');
					selectLocation(currentNavigatedLocation, path);
				}
			}}
		>
				<div class="p-2.5 bg-neutral-800 rounded-lg group-hover:bg-primary-500/20 transition-colors">
					<svg class="w-5 h-5 text-neutral-400 group-hover:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
						<circle cx="12" cy="10" r="3" />
					</svg>
				</div>
				<div class="flex-1 min-w-0">
					<p class="font-medium text-neutral-100 group-hover:text-primary-400 transition-colors">Use "{$locationPath[$locationPath.length - 1].name}"</p>
					<p class="text-body-sm text-neutral-500">Select as item location</p>
				</div>
				<div class="flex items-center gap-1 text-neutral-500 group-hover:text-primary-400 transition-colors">
					<span class="text-body-sm font-medium">Select</span>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<line x1="5" y1="12" x2="19" y2="12" />
						<polyline points="12 5 19 12 12 19" />
					</svg>
				</div>
		</button>
		{/if}

		<!-- Sublocations section -->
		{#if $currentLevelLocations.length > 0 && $locationPath.length > 0}
			<div class="flex items-center gap-2 mb-2 mt-2">
				<div class="flex items-center gap-1.5 text-neutral-500">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z" />
					</svg>
					<span class="text-body-sm font-medium">Inside {$locationPath[$locationPath.length - 1].name}</span>
				</div>
				<div class="flex-1 h-px bg-neutral-800"></div>
			</div>
		{/if}

		<!-- Location list with improved cards -->
		<div class="space-y-2">
			{#each $currentLevelLocations as location}
					<button
						type="button"
						class="w-full flex items-center gap-3 p-4 rounded-xl border bg-neutral-900/60 border-neutral-700/70 shadow-sm hover:shadow-md hover:border-neutral-600 hover:bg-neutral-900 transition-all text-left group {$locationPath.length > 0 ? 'ml-2' : ''}"
						onclick={() => navigateInto(location)}
					>
						<div class="p-2.5 bg-neutral-800 rounded-lg group-hover:bg-primary-500/20 transition-colors">
							<svg class="w-5 h-5 text-neutral-400 group-hover:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
								<path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z" />
							</svg>
						</div>
						<div class="flex-1 min-w-0">
							<p class="font-medium text-neutral-100 truncate">{location.name}</p>
							{#if location.description}
								<p class="text-body-sm text-neutral-500 truncate">{location.description}</p>
							{/if}
						</div>
						{#if location.children && location.children.length > 0}
							<div class="flex items-center gap-1 text-neutral-500 text-body-sm">
								<span>{location.children.length}</span>
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
									<polyline points="9 18 15 12 9 6" />
								</svg>
							</div>
						{:else if location.itemCount !== undefined}
							<span class="text-body-sm text-neutral-500">{location.itemCount} items</span>
						{/if}
					</button>
				{/each}

			<!-- Create new location button (secondary style) -->
				<Button variant="secondary" full onclick={() => openCreateModal(getCurrentParent())}>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<line x1="12" y1="5" x2="12" y2="19" />
						<line x1="5" y1="12" x2="19" y2="12" />
					</svg>
					<span>
						{#if $locationPath.length > 0}
							Create Location in {$locationPath[$locationPath.length - 1].name}
						{:else}
							Create New Location
						{/if}
					</span>
				</Button>
			</div>
		{/if}
	{/if}
</div>

<!-- Location Modal -->
<LocationModal
	bind:open={showLocationModal}
	mode={locationModalMode}
	location={locationModalMode === 'edit' ? $selectedLocation : null}
	parentLocation={locationModalMode === 'create' ? createParentLocation : null}
	onsave={handleSaveLocation}
/>

<!-- Item Picker Modal -->
{#if showItemPicker && $selectedLocation}
	<ItemPickerModal
		locationId={$selectedLocation.id}
		currentItemId={scanWorkflow.state.parentItemId}
		onSelect={handleParentItemSelect}
		onClose={() => (showItemPicker = false)}
	/>
{/if}

<!-- QR Scanner Modal -->
{#if showQrScanner}
	<QrScanner
		onScan={handleQrScan}
		onClose={closeQrScanner}
		onError={handleQrError}
	/>
{/if}
