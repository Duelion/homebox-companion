<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { locations as locationsApi } from '$lib/api';
	import { ApiError } from '$lib/api/client';
	import { authStore } from '$lib/stores/auth.svelte';
	import { locationStore } from '$lib/stores/locations.svelte';
	import { locationNavigator } from '$lib/services/locationNavigator.svelte';
	import { fetchTags } from '$lib/stores/tags.svelte';
	import { showToast } from '$lib/stores/ui.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { routeGuards } from '$lib/utils/routeGuard';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import { createLogger } from '$lib/utils/logger';
	import { resolveQrUrl } from '$lib/utils/qrUrl';
	import type { Location } from '$lib/types';
	import Button from '$lib/components/Button.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import LocationModal from '$lib/components/LocationModal.svelte';
	import ItemPickerModal from '$lib/components/ItemPickerModal.svelte';
	import BackLink from '$lib/components/BackLink.svelte';
	import QrScanner from '$lib/components/QrScanner.svelte';
	import PullToRefresh from '$lib/components/PullToRefresh.svelte';
	import RecoveryBanner from '$lib/components/RecoveryBanner.svelte';
	import type { SessionSummary } from '$lib/services/sessionPersistence';
	import {
		MapPin,
		SquarePen,
		ArrowRight,
		Package,
		Search,
		X,
		QrCode,
		Home,
		ChevronRight,
		FolderOpen,
		Plus,
	} from 'lucide-svelte';

	const log = createLogger({ prefix: 'LocationPage' });

	// Local UI state
	let searchQuery = $state('');

	// Modal state
	let showLocationModal = $state(false);
	let locationModalMode = $state<'create' | 'edit'>('create');
	let createParentLocation = $state<{ id: string; name: string } | null>(null);

	// Item picker modal state
	let showItemPicker = $state(false);

	// QR Scanner state
	let showQrScanner = $state(false);

	// Session recovery state
	let hasRecovery = $state(false);
	let recoverySummary = $state<SessionSummary | null>(null);
	let isRecovering = $state(false);
	let isProcessingQr = $state(false);

	// Derived: filtered locations based on search (uses store's flatList)
	let filteredLocations = $derived(
		searchQuery.trim() === ''
			? []
			: locationStore.flatList.filter(
					(item) =>
						item.location.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
						item.path.toLowerCase().includes(searchQuery.toLowerCase())
				)
	);

	let isSearching = $derived(searchQuery.trim().length > 0);

	// Reload locations when session is restored after expiry
	// Use a simple variable to track previous state (not reactive, just storage)
	let prevSessionExpired = false;

	$effect(() => {
		const currentExpired = authStore.sessionExpired;
		// Detect transition from expired -> restored
		if (prevSessionExpired && !currentExpired) {
			locationNavigator.loadTree();
			fetchTags();
		}
		// Update previous state (plain variable, not tracked by Svelte)
		prevSessionExpired = currentExpired;
	});

	// Apply route guard: requires auth, redirects to capture if already in workflow
	onMount(async () => {
		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		if (!routeGuards.location()) return;

		// Check for recoverable session
		try {
			hasRecovery = await scanWorkflow.hasRecoverableSession();
			if (hasRecovery) {
				recoverySummary = await scanWorkflow.getRecoverySummary();
			}
		} catch (err) {
			log.warn('Failed to check for recoverable session:', err);
		}

		await locationNavigator.loadTree();
		await fetchTags();
	});

	// Handler for pull-to-refresh: refreshes current view without resetting navigation
	async function handlePullRefresh() {
		const path = locationStore.path;

		if (locationStore.selected) {
			// Refresh selected location's details
			await locationNavigator.refreshSelected();
		} else if (path.length > 0) {
			// Drilled into a location - refresh current level
			const parentId = path[path.length - 1].id;
			await locationNavigator.refreshCurrentLevel(parentId);
			await locationNavigator.updateBreadcrumbNames();
		} else {
			// At root level - refresh everything
			await locationNavigator.loadTree();
		}

		// Always refresh tags to pick up new tags created by other users
		try {
			await fetchTags(true); // force refresh
		} catch (error) {
			log.warn('Failed to refresh tags during pull-to-refresh', error);
		}
	}

	function selectFromSearch(item: { location: Location; path: string }) {
		locationNavigator.selectLocation(item.location, item.path);
		searchQuery = '';
	}

	function selectCurrentLocation() {
		// Use the stored current location from navigateInto instead of traversing stale tree
		if (locationNavigator.currentLocation) {
			const pathStr = locationStore.path.map((p) => p.name).join(' / ');
			locationNavigator.selectLocation(locationNavigator.currentLocation, pathStr);
		}
	}

	async function changeSelection() {
		await locationNavigator.clearSelection();
	}

	function continueToCapture() {
		if (!locationStore.selected) {
			showToast('Please select a location', 'warning');
			return;
		}
		goto(resolve('/capture'));
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

	async function handleSaveLocation(data: {
		name: string;
		description: string;
		parentId: string | null;
	}) {
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
				await locationNavigator.refreshCurrentLevel(data.parentId);

				showToast(`Location "${newLocation.name}" created`, 'success');
			} else if (locationModalMode === 'edit' && locationStore.selected) {
				const updatedLocation = await locationsApi.update(locationStore.selected.id, {
					name: data.name,
					description: data.description,
				});

				log.debug('Updated location:', updatedLocation.name);

				// Update selected location with new data
				const locationData: Location = {
					id: updatedLocation.id,
					name: updatedLocation.name,
					description: updatedLocation.description,
					children: locationStore.selected.children || [],
				};
				locationStore.setSelected(locationData);

				// Update workflow with new name
				scanWorkflow.setLocation(locationData.id, locationData.name, locationStore.selectedPath);

				// Refresh flat list for search - fetch tree to preserve hierarchy for disambiguation
				try {
					const tree = await locationsApi.tree();
					locationStore.setTree(tree);
					locationStore.setFlatList(tree);
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
			// Resolve shortened URLs (bit.ly, etc.) to their final destination
			const resolvedUrl = await resolveQrUrl(decodedText);

			// Parse the QR code URL to extract location ID
			// Expected format: https://homebox.example.com/location/{uuid}
			const locationIdMatch = resolvedUrl.match(/\/location\/([a-f0-9-]+)(?:\/|$)/i);

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

			locationNavigator.selectLocation(locationData, locationPath);
		} catch (error) {
			log.error('QR scan error', error);
			if (error instanceof ApiError) {
				if (error.status === 401) {
					showToast('Session expired. Please log in again.', 'error');
				} else if (error.status === 404) {
					showToast('Location not found in your Homebox.', 'error');
				} else {
					showToast('Failed to load location. Please try again.', 'error');
				}
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

	// Session recovery handlers
	async function handleResumeSession() {
		isRecovering = true;
		try {
			const success = await scanWorkflow.recover();
			if (success) {
				hasRecovery = false;
				recoverySummary = null;
				showToast('Session recovered!', 'success');
				// Navigate based on recovered status
				const status = scanWorkflow.state.status;
				if (status === 'reviewing' || status === 'confirming') {
					goto(resolve('/review'));
				} else if (status === 'capturing' || status === 'partial_analysis') {
					goto(resolve('/capture'));
				}
			} else {
				showToast('Failed to recover session', 'error');
				hasRecovery = false;
			}
		} catch (err) {
			log.error('Recovery failed:', err);
			showToast('Failed to recover session', 'error');
			hasRecovery = false;
		} finally {
			isRecovering = false;
		}
	}

	async function handleDismissRecovery() {
		await scanWorkflow.clearPersistedSession();
		hasRecovery = false;
		recoverySummary = null;
		showToast('Previous session cleared', 'info');
	}
</script>

<svelte:head>
	<title>Select Location - Homebox Companion</title>
</svelte:head>

<PullToRefresh
	onRefresh={handlePullRefresh}
	enabled={!locationNavigator.isLoading && !showLocationModal && !showItemPicker && !showQrScanner}
>
	<div class="animate-in">
		<StepIndicator currentStep={1} />

		<h2 class="mb-1 text-h2 text-neutral-100">Select Location</h2>
		<p class="mb-6 text-body-sm text-neutral-400">Choose where your items will be stored</p>

		{#if hasRecovery && recoverySummary && !locationStore.selected}
			<RecoveryBanner
				summary={recoverySummary}
				onResume={handleResumeSession}
				onDismiss={handleDismissRecovery}
				loading={isRecovering}
			/>
		{/if}

		{#if locationStore.selected}
			<BackLink href="/location" label="Choose a different location" onclick={changeSelection} />
		{/if}

		{#if locationNavigator.isLoading}
			<!-- Skeleton loading state -->
			<div class="space-y-3">
				<!-- Search skeleton -->
				<div class="mb-4 flex gap-2">
					<Skeleton width="100%" height="48px" rounded="xl" />
					<Skeleton width="48px" height="48px" rounded="xl" />
				</div>

				<!-- Location card skeletons -->
				{#each Array(6) as _, i (i)}
					<div
						class="flex items-center gap-3 rounded-xl border border-neutral-800 bg-neutral-900/50 p-4"
						style="animation-delay: {i * 50}ms;"
					>
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
		{:else if locationStore.selected}
			<!-- SELECTED STATE -->
			<div class="space-y-4">
				<!-- Selected location card with ring highlight -->
				<div
					class="rounded-xl border border-primary-500 bg-neutral-900 p-4 shadow-md ring-2 ring-primary-500/30"
				>
					<div class="flex items-center gap-3">
						<div class="rounded-lg bg-primary-500/20 p-3">
							<MapPin class="text-primary-400" size={24} strokeWidth={1.5} />
						</div>
						<div class="min-w-0 flex-1">
							<p class="text-body-sm text-neutral-400">Selected location:</p>
							<p class="text-body font-semibold text-neutral-100">
								{locationStore.selected.name}
							</p>
							{#if locationStore.selectedPath !== locationStore.selected.name}
								<p class="text-body-sm text-neutral-500">
									{locationStore.selectedPath}
								</p>
							{/if}
							{#if locationStore.selected.description}
								<p class="mt-1 text-body-sm text-neutral-400">
									{locationStore.selected.description}
								</p>
							{/if}
						</div>
						<button
							type="button"
							class="rounded-lg p-2 text-neutral-400 transition-colors hover:bg-primary-500/10 hover:text-primary-400"
							onclick={openEditModal}
							title="Edit location"
						>
							<SquarePen size={20} strokeWidth={1.5} />
						</button>
					</div>
				</div>

				<!-- Continue to Capture -->
				<Button variant="primary" full onclick={continueToCapture}>
					<span>Continue to Capture</span>
					<ArrowRight size={20} strokeWidth={1.5} />
				</Button>

				<!-- Assign to Container Item -->
				<Button
					variant="secondary"
					full
					onclick={openItemPicker}
					disabled={(locationStore.selected?.itemCount ?? 0) === 0}
				>
					<Package size={20} strokeWidth={1.5} />
					<span>
						{#if scanWorkflow.state.parentItemName}
							Inside: {scanWorkflow.state.parentItemName}
						{:else}
							Place Inside an Item ({locationStore.selected?.itemCount ?? 0})
						{/if}
					</span>
				</Button>
			</div>
		{:else}
			<!-- SELECTION STATE -->

			<!-- Search box with elevated style and QR scan button -->
			<div class="mb-4 flex gap-2">
				<div class="relative flex-1">
					<div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
						<Search class="text-neutral-500" size={20} strokeWidth={1.5} />
					</div>
					<input
						type="text"
						placeholder="Search all locations..."
						bind:value={searchQuery}
						class="h-12 w-full rounded-xl border border-neutral-600 bg-neutral-800 pl-11 pr-10 text-neutral-100 transition-all placeholder:text-neutral-500 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
					/>
					{#if searchQuery}
						<button
							type="button"
							class="absolute inset-y-0 right-0 flex items-center pr-4 text-neutral-400 transition-colors hover:text-neutral-200"
							aria-label="Clear search"
							onclick={() => (searchQuery = '')}
						>
							<X size={16} strokeWidth={1.5} />
						</button>
					{/if}
				</div>

				<!-- QR Scan Button -->
				<button
					type="button"
					onclick={openQrScanner}
					disabled={isProcessingQr}
					class="flex h-12 w-12 items-center justify-center rounded-xl border border-neutral-600 bg-neutral-800 text-neutral-400 transition-all hover:border-primary-500/50 hover:bg-primary-500/5 hover:text-primary-400 disabled:opacity-50"
					title="Scan QR Code"
				>
					{#if isProcessingQr}
						<div
							class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
						></div>
					{:else}
						<QrCode size={20} strokeWidth={1.5} />
					{/if}
				</button>
			</div>

			{#if isSearching}
				<!-- SEARCH RESULTS -->
				<div class="space-y-2">
					{#if filteredLocations.length === 0}
						<div class="py-8 text-center text-neutral-500">
							<Search class="mx-auto mb-2 opacity-50" size={40} strokeWidth={1.5} />
							<p>No locations found for "{searchQuery}"</p>
						</div>
					{:else}
						<p class="mb-2 text-body-sm text-neutral-400">
							{filteredLocations.length} location{filteredLocations.length !== 1 ? 's' : ''} found
						</p>
						{#each filteredLocations as item (item.location.id)}
							<button
								type="button"
								class="group flex w-full items-center gap-3 rounded-xl border border-neutral-700 bg-neutral-900 p-4 text-left shadow-sm transition-all hover:border-neutral-600 hover:shadow-md"
								onclick={() => selectFromSearch(item)}
							>
								<div
									class="rounded-lg bg-neutral-800 p-2.5 transition-colors group-hover:bg-primary-500/20"
								>
									<MapPin
										class="text-neutral-400 group-hover:text-primary-400"
										size={20}
										strokeWidth={1.5}
									/>
								</div>
								<div class="min-w-0 flex-1">
									<p class="font-medium text-neutral-100">
										{item.displayName}
									</p>
									{#if item.displayName !== item.path}
										<p class="truncate text-body-sm text-neutral-500">
											{item.path}
										</p>
									{/if}
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

				{#if locationStore.path.length > 0}
					<div class="mb-4 flex items-center gap-1 overflow-x-auto pb-2 text-sm">
						<button
							type="button"
							class="flex items-center gap-1 whitespace-nowrap rounded-lg px-2 py-1 text-neutral-400 transition-colors hover:bg-neutral-800 hover:text-neutral-200"
							onclick={() => locationNavigator.navigateToPath(-1)}
						>
							<Home size={16} strokeWidth={1.5} />
							<span>All</span>
						</button>

						{#each locationStore.path as pathItem (pathItem.id)}
							{@const index = locationStore.path.indexOf(pathItem)}
							<ChevronRight class="shrink-0 text-neutral-600" size={16} strokeWidth={1.5} />
							<button
								type="button"
								class="whitespace-nowrap rounded-lg px-2 py-1 text-neutral-400 transition-colors hover:bg-neutral-800 hover:text-neutral-200"
								onclick={() => locationNavigator.navigateToPath(index)}
							>
								{pathItem.name}
							</button>
						{/each}
					</div>

					<!-- Select current folder button -->
					<button
						type="button"
						class="group mb-4 flex w-full items-center gap-3 rounded-xl border border-neutral-700 bg-neutral-900 p-4 text-left shadow-sm transition-all hover:border-primary-500 hover:bg-primary-500/5 hover:shadow-md"
						aria-label="Select current location"
						onclick={selectCurrentLocation}
					>
						<div
							class="rounded-lg bg-neutral-800 p-2.5 transition-colors group-hover:bg-primary-500/20"
						>
							<MapPin
								class="text-neutral-400 group-hover:text-primary-400"
								size={20}
								strokeWidth={1.5}
							/>
						</div>
						<div class="min-w-0 flex-1">
							<p
								class="font-medium text-neutral-100 transition-colors group-hover:text-primary-400"
							>
								Use "{locationStore.path[locationStore.path.length - 1].name}"
							</p>
							<p class="text-body-sm text-neutral-500">Select as item location</p>
						</div>
						<div
							class="flex items-center gap-1 text-neutral-500 transition-colors group-hover:text-primary-400"
						>
							<span class="text-body-sm font-medium">Select</span>
							<ArrowRight size={16} strokeWidth={1.5} />
						</div>
					</button>
				{/if}

				<!-- Sublocations section -->
				{#if locationStore.currentLevel.length > 0 && locationStore.path.length > 0}
					<div class="mb-2 mt-2 flex items-center gap-2">
						<div class="flex items-center gap-1.5 text-neutral-500">
							<FolderOpen size={16} strokeWidth={1.5} />
							<span class="text-body-sm font-medium"
								>Inside {locationStore.path[locationStore.path.length - 1].name}</span
							>
						</div>
						<div class="h-px flex-1 bg-neutral-800"></div>
					</div>
				{/if}

				<!-- Location list with improved cards -->
				<div class="space-y-2">
					{#each locationStore.currentLevel as location (location.id)}
						<button
							type="button"
							class="group flex w-full items-center gap-3 rounded-xl border border-neutral-700/70 bg-neutral-900/60 p-4 text-left shadow-sm transition-all hover:border-neutral-600 hover:bg-neutral-900 hover:shadow-md {locationStore
								.path.length > 0
								? 'ml-2'
								: ''}"
							onclick={() => locationNavigator.navigateInto(location)}
						>
							<div
								class="rounded-lg bg-neutral-800 p-2.5 transition-colors group-hover:bg-primary-500/20"
							>
								<FolderOpen
									class="text-neutral-400 group-hover:text-primary-400"
									size={20}
									strokeWidth={1.5}
								/>
							</div>
							<div class="min-w-0 flex-1">
								<p class="truncate font-medium text-neutral-100">
									{location.name}
								</p>
								{#if location.description}
									<p class="truncate text-body-sm text-neutral-500">
										{location.description}
									</p>
								{/if}
							</div>
							{#if location.children && location.children.length > 0}
								<div class="flex items-center gap-1 text-body-sm text-neutral-500">
									<span>{location.children.length}</span>
									<ChevronRight size={16} strokeWidth={1.5} />
								</div>
							{:else if location.itemCount !== undefined}
								<span class="text-body-sm text-neutral-500">{location.itemCount} items</span>
							{/if}
						</button>
					{/each}

					<!-- Create new location button (secondary style) -->
					<Button
						variant="secondary"
						full
						onclick={() => openCreateModal(locationNavigator.getCurrentParent())}
					>
						<Plus size={20} strokeWidth={1.5} />
						<span>
							{#if locationStore.path.length > 0}
								Create Location in {locationStore.path[locationStore.path.length - 1].name}
							{:else}
								Create New Location
							{/if}
						</span>
					</Button>
				</div>
			{/if}
		{/if}
	</div>
</PullToRefresh>

<!-- Location Modal -->
<LocationModal
	bind:open={showLocationModal}
	mode={locationModalMode}
	location={locationModalMode === 'edit' ? locationStore.selected : null}
	parentLocation={locationModalMode === 'create' ? createParentLocation : null}
	onsave={handleSaveLocation}
/>

<!-- Item Picker Modal -->
{#if showItemPicker && locationStore.selected}
	<ItemPickerModal
		locationId={locationStore.selected.id}
		currentItemId={scanWorkflow.state.parentItemId}
		onSelect={handleParentItemSelect}
		onClose={() => (showItemPicker = false)}
	/>
{/if}

<!-- QR Scanner Modal -->
{#if showQrScanner}
	<QrScanner onScan={handleQrScan} onClose={closeQrScanner} onError={handleQrError} />
{/if}
