<script lang="ts">
	import { Search, Package, Check, X } from '@lucide/svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import { items as itemsApi, type BlobUrlResult } from '$lib/api';
	import { showToast } from '$lib/stores/ui.svelte';
	import { createLogger } from '$lib/utils/logger';
	import type { ItemSummary } from '$lib/types';
	import Button from './Button.svelte';
	import Loader from './Loader.svelte';
	import Modal from './Modal.svelte';

	const log = createLogger({ prefix: 'ItemPicker' });

	interface Props {
		locationId: string;
		currentItemId?: string | null;
		onSelect: (id: string, name: string) => void;
		onClose: () => void;
	}

	let { locationId, currentItemId = null, onSelect, onClose }: Props = $props();

	let isLoading = $state(true);
	let items = $state<ItemSummary[]>([]);
	// Track user's selection - starts with current parent, user can change independently
	// We intentionally capture the initial prop value here; the effect below syncs on prop changes
	// eslint-disable-next-line svelte/prefer-writable-derived -- Local state synced from prop, modifiable by user
	let selectedItemId = $state<string | null | undefined>(undefined);
	let searchQuery = $state('');
	// Store fetched thumbnail results with their revoke functions (itemId -> BlobUrlResult)
	let thumbnailResults = new SvelteMap<string, BlobUrlResult>();

	// Sync selectedItemId when currentItemId prop changes (including initial mount)
	$effect(() => {
		// This effect ensures we track prop changes while allowing local modification
		selectedItemId = currentItemId;
	});

	// Helper to get thumbnail URL for an item
	function getThumbnailUrl(item: ItemSummary): string | null {
		return thumbnailResults.get(item.id)?.url ?? null;
	}

	// Filtered items based on search
	let filteredItems = $derived(
		searchQuery.trim() === ''
			? items
			: items.filter((item) => item.name.toLowerCase().includes(searchQuery.toLowerCase()))
	);

	// Each location load owns its requests and thumbnail URLs. Effect cleanup runs
	// synchronously when the location changes and when the modal is destroyed.
	$effect(() => {
		const requestedLocationId = locationId;
		const controller = new AbortController();
		log.debug('Loading items for location:', requestedLocationId);
		void loadItems(requestedLocationId, controller);

		return () => {
			controller.abort();
			for (const result of thumbnailResults.values()) {
				result.revoke();
			}
			thumbnailResults.clear();
			items = [];
		};
	});

	function isCurrentRequest(controller: AbortController): boolean {
		return !controller.signal.aborted;
	}

	async function loadItems(requestedLocationId: string, controller: AbortController) {
		isLoading = true;
		items = [];
		try {
			const loadedItems = await itemsApi.list(requestedLocationId, controller.signal);
			if (!isCurrentRequest(controller)) return;
			items = loadedItems;
			log.debug(`Loaded ${items.length} items`);
			// Fetch thumbnails for items that have them
			await loadThumbnails(loadedItems, controller);
		} catch (error) {
			if (
				!isCurrentRequest(controller) ||
				(error instanceof Error && error.name === 'AbortError')
			) {
				return;
			}
			log.error('Failed to load items', error);
			showToast('Failed to load items', 'error');
			items = [];
		} finally {
			if (isCurrentRequest(controller)) isLoading = false;
		}
	}

	async function loadThumbnails(itemsList: ItemSummary[], controller: AbortController) {
		const itemsWithThumbnails = itemsList.filter((item) => item.thumbnailId);
		if (itemsWithThumbnails.length === 0) return;

		log.debug(`Fetching ${itemsWithThumbnails.length} thumbnails`);

		// Register each result as soon as it completes so cleanup always owns it.
		await Promise.all(
			itemsWithThumbnails.map(async (item) => {
				try {
					const result = await itemsApi.getThumbnail(item.id, item.thumbnailId!, controller.signal);
					if (!isCurrentRequest(controller)) {
						result.revoke();
						return;
					}
					const existing = thumbnailResults.get(item.id);
					if (existing) existing.revoke();
					thumbnailResults.set(item.id, result);
				} catch (error) {
					if (
						!isCurrentRequest(controller) ||
						(error instanceof Error && error.name === 'AbortError')
					) {
						return;
					}
					// Log other errors but continue - missing thumbnails are not critical
					log.debug(`Failed to load thumbnail for item ${item.id}:`, error);
				}
			})
		);
		if (isCurrentRequest(controller)) log.debug(`Loaded ${thumbnailResults.size} thumbnails`);
	}

	function selectItem(item: ItemSummary) {
		selectedItemId = item.id;
		onSelect(item.id, item.name);
		onClose();
	}

	function clearSelection() {
		onSelect('', '');
		onClose();
	}
</script>

<Modal open={true} title="Select Container Item" onclose={onClose}>
	<!-- Search -->
	<div class="mb-4">
		<div class="relative">
			<div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
				<Search class="text-neutral-500" size={20} strokeWidth={1.5} />
			</div>
			<input
				type="text"
				placeholder="Search items..."
				bind:value={searchQuery}
				class="input-with-icon"
			/>
		</div>
	</div>

	<!-- Items list -->
	<div class="max-h-64 space-y-2 overflow-y-auto">
		{#if isLoading}
			<div class="flex items-center justify-center py-12">
				<Loader size="lg" />
			</div>
		{:else if filteredItems.length === 0}
			<div class="py-12 text-center text-neutral-500">
				{#if searchQuery}
					<p>No items found for "{searchQuery}"</p>
				{:else}
					<p>No items in this location</p>
					<p class="mt-2 text-body-sm">Add some items first</p>
				{/if}
			</div>
		{:else}
			{#each filteredItems as item (item.id)}
				{@const thumbnailUrl = getThumbnailUrl(item)}
				<button
					type="button"
					class="selectable-item {selectedItemId === item.id ? 'selectable-item-selected' : ''}"
					onclick={() => selectItem(item)}
				>
					<!-- Thumbnail -->
					<div class="shrink-0 overflow-hidden rounded-lg bg-neutral-700 size-14">
						{#if thumbnailUrl}
							<img src={thumbnailUrl} alt="" class="object-cover size-full" />
						{:else}
							<div class="flex items-center justify-center size-full">
								<Package class="text-neutral-500" size={28} strokeWidth={1} />
							</div>
						{/if}
					</div>

					<div class="min-w-0 flex-1">
						<p class="truncate font-medium text-neutral-100">
							{item.name}
						</p>
						<p class="text-body-sm text-neutral-500">
							Quantity: {item.quantity}
						</p>
					</div>

					{#if selectedItemId === item.id}
						<div class="flex items-center justify-center text-primary-400 size-6">
							<Check class="text-primary-400" size={20} strokeWidth={2.5} />
						</div>
					{/if}
				</button>
			{/each}
		{/if}
	</div>

	{#snippet footer()}
		{#if currentItemId}
			<Button variant="secondary" onclick={clearSelection}>
				<X size={20} strokeWidth={1.5} />
				<span>Clear Selection</span>
			</Button>
		{/if}
		<Button variant="ghost" onclick={onClose}>
			<span>Cancel</span>
		</Button>
	{/snippet}
</Modal>
