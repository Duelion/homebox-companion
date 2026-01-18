<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
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

	onMount(async () => {
		log.debug('Loading items for location:', locationId);
		await loadItems();
	});

	// Clean up blob URLs when component is destroyed
	onDestroy(() => {
		for (const result of thumbnailResults.values()) {
			result.revoke();
		}
	});

	async function loadItems() {
		isLoading = true;
		try {
			items = await itemsApi.list(locationId);
			log.debug(`Loaded ${items.length} items`);
			// Fetch thumbnails for items that have them
			await loadThumbnails(items);
		} catch (error) {
			log.error('Failed to load items', error);
			showToast('Failed to load items', 'error');
			items = [];
		} finally {
			isLoading = false;
		}
	}

	async function loadThumbnails(itemsList: ItemSummary[]) {
		const itemsWithThumbnails = itemsList.filter((item) => item.thumbnailId);
		if (itemsWithThumbnails.length === 0) return;

		log.debug(`Fetching ${itemsWithThumbnails.length} thumbnails`);

		// Fetch all thumbnails in parallel, catching errors individually
		const results = await Promise.all(
			itemsWithThumbnails.map(async (item) => {
				try {
					const result = await itemsApi.getThumbnail(item.id, item.thumbnailId!);
					return { itemId: item.id, result };
				} catch (error) {
					// Ignore aborted requests silently
					if (error instanceof Error && error.name === 'AbortError') {
						return { itemId: item.id, result: null };
					}
					// Log other errors but continue - missing thumbnails are not critical
					log.debug(`Failed to load thumbnail for item ${item.id}:`, error);
					return { itemId: item.id, result: null };
				}
			})
		);

		// Store successful results (with their revoke functions for cleanup)
		const newResults = new SvelteMap(thumbnailResults);
		for (const { itemId, result } of results) {
			if (result) {
				// Revoke any existing URL for this item before replacing
				const existing = newResults.get(itemId);
				if (existing) {
					existing.revoke();
				}
				newResults.set(itemId, result);
			}
		}
		thumbnailResults = newResults;
		log.debug(`Loaded ${newResults.size} thumbnails`);
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
				<svg
					class="h-5 w-5 text-neutral-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<circle cx="11" cy="11" r="8" />
					<path d="m21 21-4.35-4.35" />
				</svg>
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
					<p class="text-body-sm mt-2">Add some items first</p>
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
					<div class="h-14 w-14 flex-shrink-0 overflow-hidden rounded-lg bg-neutral-700">
						{#if thumbnailUrl}
							<img src={thumbnailUrl} alt="" class="h-full w-full object-cover" />
						{:else}
							<div class="flex h-full w-full items-center justify-center">
								<svg
									class="h-7 w-7 text-neutral-500"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									stroke-width="1"
								>
									<path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
								</svg>
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
						<div class="text-primary-400 flex h-6 w-6 items-center justify-center">
							<svg
								class="h-5 w-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2.5"
							>
								<polyline points="20 6 9 17 4 12" />
							</svg>
						</div>
					{/if}
				</button>
			{/each}
		{/if}
	</div>

	{#snippet footer()}
		{#if currentItemId}
			<Button variant="secondary" onclick={clearSelection}>
				<svg
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
				<span>Clear Selection</span>
			</Button>
		{/if}
		<Button variant="ghost" onclick={onClose}>
			<span>Cancel</span>
		</Button>
	{/snippet}
</Modal>
