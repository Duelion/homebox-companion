<script lang="ts">
	import { Package, Check } from 'lucide-svelte';
	import { SvelteSet } from 'svelte/reactivity';
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
	let failedThumbnails = new SvelteSet<string>();

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
		failedThumbnails.add(itemId);
	}

	/** Check if an item should show its thumbnail */
	function shouldShowThumbnail(item: CreatedItem): boolean {
		return !!item.thumbnail && !failedThumbnails.has(item.id);
	}
</script>

<Modal open={true} title="Select Parent Item" onclose={onClose}>
	<div class="space-y-2">
		<p class="mb-4 text-body-sm text-neutral-400">
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
						class="selectable-item p-4 {selectedItem?.id === item.id
							? 'selectable-item-selected'
							: ''}"
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
								<Package class="text-neutral-400" size={20} strokeWidth={1.5} />
							</div>
						{/if}

						<span class="flex-1 truncate font-medium text-neutral-100">{item.name}</span>

						{#if selectedItem?.id === item.id}
							<Check class="shrink-0 text-primary-400" size={20} strokeWidth={2.5} />
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
