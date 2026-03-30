<script lang="ts">
	import { Package, ExternalLink, ScanLine } from 'lucide-svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { onMount } from 'svelte';
	import Modal from './Modal.svelte';
	import { tagStore } from '$lib/stores/tags.svelte';
	import { settingsService } from '$lib/workflows/settings.svelte';
	import { getConfig } from '$lib/api/settings';

	interface CreatedItem {
		id: string;
		name: string;
		thumbnail?: string;
		tag_ids?: string[];
	}

	interface Props {
		items: CreatedItem[];
		open: boolean;
		onclose: () => void;
		/** Called when user wants to scan sub-items for a specific parent */
		onScanSubItems?: (id: string, name: string) => void;
	}

	let { items, open = $bindable(), onclose, onScanSubItems }: Props = $props();

	/** Track IDs of items whose thumbnails failed to load */
	let failedThumbnails = new SvelteSet<string>();

	/** Homebox base URL for constructing item links */
	let homeboxUrl = $state<string | null>(null);

	onMount(async () => {
		// Use cached config if available, otherwise fetch
		if (settingsService.config?.homebox_url) {
			homeboxUrl = settingsService.config.homebox_url;
		} else {
			try {
				const config = await getConfig();
				homeboxUrl = config.homebox_url;
			} catch {
				// Non-critical: links just won't work
			}
		}
		// Ensure tags are loaded for label resolution
		await tagStore.fetchTags();
	});

	/** Handle image load error by marking it as failed so fallback icon is shown */
	function handleImageError(itemId: string) {
		failedThumbnails.add(itemId);
	}

	/** Check if an item should show its thumbnail */
	function shouldShowThumbnail(item: CreatedItem): boolean {
		return !!item.thumbnail && !failedThumbnails.has(item.id);
	}

	/** Get the Homebox URL for an item */
	function getItemUrl(itemId: string): string | null {
		if (!homeboxUrl) return null;
		// Remove trailing slash if present
		const base = homeboxUrl.replace(/\/$/, '');
		return `${base}/item/${itemId}`;
	}

	/** Resolve a tag ID to its name */
	function getTagName(tagId: string): string | undefined {
		return tagStore.getTagName(tagId);
	}
</script>

<Modal bind:open title="Created Items" {onclose}>
	<div class="space-y-2">
		{#if items.length === 0}
			<p class="py-8 text-center text-neutral-500">No items created</p>
		{:else}
			<div class="max-h-80 space-y-2 overflow-y-auto">
				{#each items as item (item.id)}
					{@const itemUrl = getItemUrl(item.id)}
					<div class="rounded-xl border border-neutral-700 bg-neutral-800 p-3 transition-all">
						<div class="flex items-center gap-3">
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

							<!-- Name -->
							<div class="min-w-0 flex-1">
								<span class="block truncate font-medium text-neutral-100">{item.name}</span>
							</div>

							<!-- Actions -->
							<div class="flex shrink-0 items-center gap-1">
								{#if itemUrl}
									<!-- eslint-disable svelte/no-navigation-without-resolve -- External URL, not an app route -->
									<a
										href={itemUrl}
										target="_blank"
										rel="noopener noreferrer"
										class="flex min-h-touch min-w-touch items-center justify-center rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-primary-400"
										title="Open in Homebox"
									>
										<!-- eslint-enable svelte/no-navigation-without-resolve -->
										<ExternalLink size={18} strokeWidth={1.5} />
									</a>
								{/if}
							</div>
						</div>

						<!-- Bottom row: tags + scan action -->
						<!-- pl-[52px] = 40px thumbnail + 12px gap, aligns with item name -->
						{#if (item.tag_ids && item.tag_ids.length > 0) || onScanSubItems}
							<div class="mt-2 flex flex-wrap items-center gap-1.5 pl-[52px]">
								{#if item.tag_ids}
									{#each item.tag_ids as tagId (tagId)}
										{@const tagName = getTagName(tagId)}
										{#if tagName}
											<span
												class="rounded-lg border border-neutral-700 bg-neutral-900 px-2 py-0.5 text-xs text-neutral-300"
											>
												{tagName}
											</span>
										{/if}
									{/each}
								{/if}
								{#if onScanSubItems}
									<button
										type="button"
										class="ml-auto flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs text-primary-400 transition-colors hover:bg-primary-500/10 hover:text-primary-300"
										onclick={() => onScanSubItems(item.id, item.name)}
									>
										<ScanLine size={12} strokeWidth={2} />
										<span>Scan Sub-Items</span>
									</button>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</Modal>
