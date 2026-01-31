<script lang="ts">
	/**
	 * TagSelector - Tag chip selector for items
	 *
	 * Displays available tags as clickable chips, highlighting selected ones.
	 * Uses the global tagStore for available tags.
	 */
	import { onMount } from 'svelte';
	import { tagStore } from '$lib/stores/tags.svelte';
	import type { FormSize } from './types';
	import { getLabelClass } from './types';

	interface Props {
		selectedIds: string[];
		size?: FormSize;
		disabled?: boolean;
		onToggle: (tagId: string) => void;
	}

	let { selectedIds, size = 'md', disabled = false, onToggle }: Props = $props();

	// Dynamic label class based on size
	const labelClass = $derived(getLabelClass(size));

	// Ensure tags are loaded when component mounts
	onMount(() => {
		if (!tagStore.fetched) {
			tagStore.fetchTags();
		}
	});
</script>

{#if tagStore.loading}
	<div>
		<span class={labelClass}>Tags</span>
		<p class="text-sm text-neutral-500">Loading tags...</p>
	</div>
{:else if tagStore.tags.length > 0}
	<div>
		<span class={labelClass}>Tags</span>
		<div class="flex flex-wrap gap-2" role="group" aria-label="Select tags">
			{#each tagStore.tags as tag (tag.id)}
				{@const isSelected = selectedIds.includes(tag.id)}
				<button
					type="button"
					class={isSelected ? 'label-chip-selected' : 'label-chip'}
					onclick={() => onToggle(tag.id)}
					aria-pressed={isSelected}
					{disabled}
				>
					{tag.name}
				</button>
			{/each}
		</div>
	</div>
{/if}
