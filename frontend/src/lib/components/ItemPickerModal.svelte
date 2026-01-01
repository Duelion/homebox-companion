<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import { items as itemsApi, type BlobUrlResult } from '$lib/api';
	import { showToast } from '$lib/stores/ui.svelte';
	import { createLogger } from '$lib/utils/logger';
	import type { ItemSummary } from '$lib/types';
	import Button from './Button.svelte';
	import Loader from './Loader.svelte';

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

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Modal overlay -->
<div
	class="animate-in fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
	onclick={onClose}
	role="presentation"
>
	<!-- Modal content -->
	<div
		class="animate-in zoom-in-95 flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl border border-neutral-700 bg-neutral-900 shadow-xl"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
		tabindex="-1"
		role="dialog"
		aria-modal="true"
		aria-labelledby="item-picker-title"
	>
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-neutral-800 p-6">
			<h2 id="item-picker-title" class="text-h3 text-neutral-100">Select Container Item</h2>
			<button
				type="button"
				class="rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-800 hover:text-neutral-200"
				onclick={onClose}
				aria-label="Close"
			>
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
			</button>
		</div>

		<!-- Search -->
		<div class="border-b border-neutral-800 p-4">
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
					class="h-12 w-full rounded-xl border border-neutral-600 bg-neutral-800 pl-10 pr-4 text-neutral-100 transition-all placeholder:text-neutral-500 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
				/>
			</div>
		</div>

		<!-- Items list -->
		<div class="flex-1 space-y-2 overflow-y-auto p-4">
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
						class="flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-all {selectedItemId ===
						item.id
							? 'border-primary-500/50 bg-primary-500/10'
							: 'border-neutral-700 bg-neutral-800 hover:border-neutral-600'}"
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
							<div class="flex h-6 w-6 items-center justify-center text-primary-400">
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

		<!-- Footer actions -->
		<div class="space-y-2 border-t border-neutral-800 p-4">
			{#if currentItemId}
				<Button variant="secondary" full onclick={clearSelection}>
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
			<Button variant="ghost" full onclick={onClose}>
				<span>Cancel</span>
			</Button>
		</div>
	</div>
</div>
