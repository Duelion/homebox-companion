<script lang="ts">
	/**
	 * LocationSelector - Dropdown for selecting item location
	 *
	 * Displays available locations from the global store as a select dropdown.
	 * Falls back to displaying a text value when locations aren't loaded.
	 */
	import { locationStore } from '$lib/stores/locations.svelte';
	import type { FormSize } from './types';
	import { getInputClass, getLabelClass } from './types';

	interface Props {
		/**
		 * Selected location ID. MUST be initialized to empty string (''), not null/undefined,
		 * for the "Select location..." placeholder option to display correctly.
		 */
		value: string;
		size?: FormSize;
		disabled?: boolean;
		idPrefix?: string;
		/** Text to display when location store hasn't loaded yet */
		fallbackDisplay?: string;
	}

	let {
		value = $bindable(),
		size = 'md',
		disabled = false,
		idPrefix = 'location',
		fallbackDisplay = 'No location',
	}: Props = $props();

	// Dynamic classes based on size
	const inputClass = $derived(getInputClass(size));
	const labelClass = $derived(getLabelClass(size));
</script>

<div>
	<label for="{idPrefix}-location" class={labelClass}>Location</label>
	{#if locationStore.flatList.length > 0}
		<select id="{idPrefix}-location" bind:value class={inputClass} {disabled}>
			<option value="">Select location...</option>
			{#each locationStore.flatList as loc (loc.location.id)}
				<option value={loc.location.id}>{loc.path}</option>
			{/each}
		</select>
	{:else}
		<!-- Fallback when locations haven't loaded -->
		<div class="rounded-lg bg-neutral-800/50 px-2.5 py-1.5">
			<span class="text-sm text-neutral-300">{fallbackDisplay}</span>
		</div>
	{/if}
</div>
