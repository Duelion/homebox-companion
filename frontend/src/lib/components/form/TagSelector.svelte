<script lang="ts">
	/**
	 * LabelSelector - Tag chip selector for item labels
	 *
	 * Displays available labels as clickable chips, highlighting selected ones.
	 * Uses the global labelStore for available labels.
	 */
	import { onMount } from 'svelte';
	import { labelStore } from '$lib/stores/tags.svelte';
	import type { FormSize } from './types';
	import { getLabelClass } from './types';

	interface Props {
		selectedIds: string[];
		size?: FormSize;
		disabled?: boolean;
		onToggle: (labelId: string) => void;
	}

	let { selectedIds, size = 'md', disabled = false, onToggle }: Props = $props();

	// Dynamic label class based on size
	const labelClass = $derived(getLabelClass(size));

	// Ensure labels are loaded when component mounts
	onMount(() => {
		if (!labelStore.fetched) {
			labelStore.fetchLabels();
		}
	});
</script>

{#if labelStore.loading}
	<div>
		<span class={labelClass}>Labels</span>
		<p class="text-sm text-neutral-500">Loading labels...</p>
	</div>
{:else if labelStore.labels.length > 0}
	<div>
		<span class={labelClass}>Labels</span>
		<div class="flex flex-wrap gap-2" role="group" aria-label="Select labels">
			{#each labelStore.labels as label (label.id)}
				{@const isSelected = selectedIds.includes(label.id)}
				<button
					type="button"
					class={isSelected ? 'label-chip-selected' : 'label-chip'}
					onclick={() => onToggle(label.id)}
					aria-pressed={isSelected}
					{disabled}
				>
					{label.name}
				</button>
			{/each}
		</div>
	</div>
{/if}
