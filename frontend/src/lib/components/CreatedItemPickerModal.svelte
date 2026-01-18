<script lang="ts">
	import Modal from './Modal.svelte';
	import Button from './Button.svelte';

	interface CreatedItem {
		id: string;
		name: string;
		thumbnail?: string;
	}

	interface Props {
		items: CreatedItem[];
		onSelect: (id: string, name: string) => void;
		onClose: () => void;
	}

	let { items, onSelect, onClose }: Props = $props();

	let selectedItem = $state<CreatedItem | null>(null);

	/** Track IDs of items whose thumbnails failed to load */
	let failedThumbnails = $state(new Set<string>());

	function handleSelect(item: CreatedItem) {
		selectedItem = item;
	}

	function handleConfirm() {
		if (selectedItem) {
			onSelect(selectedItem.id, selectedItem.name);
		}
	}

	/** Handle image load error by marking it as failed so fallback icon is shown */
	function handleImageError(itemId: string) {
		failedThumbnails = new Set(failedThumbnails).add(itemId);
	}

	/** Check if an item should show its thumbnail */
	function shouldShowThumbnail(item: CreatedItem): boolean {
		return !!item.thumbnail && !failedThumbnails.has(item.id);
	}
</script>

<Modal open={true} title="Select Parent Item" onclose={onClose}>
	<div class="space-y-2">
		<p class="text-body-sm mb-4 text-neutral-400">
			Choose which item should be the parent for your next scan. New items will be added as
			sub-items.
		</p>

		{#if items.length === 0}
			<p class="py-8 text-center text-neutral-500">No items available</p>
		{:else}
			<div class="max-h-64 space-y-2 overflow-y-auto">
				{#each items as item (item.id)}
					<button
						type="button"
						class="flex w-full items-center gap-3 rounded-xl border p-4 text-left transition-all {selectedItem?.id ===
						item.id
							? 'border-primary-500/50 bg-primary-500/10'
							: 'border-neutral-700 bg-neutral-800 hover:border-neutral-600'}"
						onclick={() => handleSelect(item)}
					>
						<!-- Thumbnail or fallback icon -->
						{#if shouldShowThumbnail(item)}
							<img
								src={item.thumbnail}
								alt={item.name}
								class="h-10 w-10 shrink-0 rounded-lg object-cover"
								onerror={() => handleImageError(item.id)}
							/>
						{:else}
							<div
								class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-neutral-700"
							>
								<svg
									class="h-5 w-5 text-neutral-400"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									stroke-width="1.5"
								>
									<path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
								</svg>
							</div>
						{/if}

						<span class="flex-1 truncate font-medium text-neutral-100">{item.name}</span>

						{#if selectedItem?.id === item.id}
							<svg
								class="text-primary-400 h-5 w-5 shrink-0"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2.5"
							>
								<polyline points="20 6 9 17 4 12" />
							</svg>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
	</div>

	{#snippet footer()}
		<Button variant="ghost" onclick={onClose}>Cancel</Button>
		<Button variant="primary" disabled={!selectedItem} onclick={handleConfirm}>
			Use as Parent
		</Button>
	{/snippet}
</Modal>
