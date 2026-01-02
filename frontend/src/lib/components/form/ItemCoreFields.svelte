<script lang="ts">
	/**
	 * ItemCoreFields - Shared form fields for name, quantity, and description
	 *
	 * Used by both the review page and approval panel for consistent item editing.
	 * Supports compact (sm) and regular (md) sizing.
	 */
	import { expandable } from '$lib/actions/expandable';
	import type { FormSize } from './types';
	import { getInputClass, getLabelClass } from './types';

	interface Props {
		name: string;
		quantity: number;
		description: string | null | undefined;
		size?: FormSize;
		disabled?: boolean;
		idPrefix?: string;
	}

	let {
		name = $bindable(),
		quantity = $bindable(),
		description = $bindable(),
		size = 'md',
		disabled = false,
		idPrefix = 'item',
	}: Props = $props();

	// Dynamic classes based on size
	const inputClass = $derived(getInputClass(size));
	const labelClass = $derived(getLabelClass(size));
	const quantityWidth = $derived(size === 'sm' ? 'w-20' : 'w-24');
	const spacing = $derived(size === 'sm' ? 'space-y-2.5' : 'space-y-5');
</script>

<div class={spacing}>
	<!-- Name field -->
	<div>
		<label for="{idPrefix}-name" class={labelClass}>Name</label>
		{#if size === 'sm'}
			<input
				type="text"
				id="{idPrefix}-name"
				bind:value={name}
				placeholder="Item name"
				class={inputClass}
				{disabled}
			/>
		{:else}
			<textarea
				id="{idPrefix}-name"
				bind:value={name}
				rows="1"
				placeholder="Item name"
				class="input-expandable"
				use:expandable
				{disabled}
			></textarea>
		{/if}
	</div>

	<!-- Quantity field -->
	<div>
		<label for="{idPrefix}-quantity" class={labelClass}>Quantity</label>
		<input
			type="number"
			id="{idPrefix}-quantity"
			min="1"
			bind:value={quantity}
			class="{inputClass} {quantityWidth}"
			{disabled}
		/>
	</div>

	<!-- Description field -->
	<div>
		<label for="{idPrefix}-description" class={labelClass}>Description</label>
		{#if size === 'sm'}
			<textarea
				id="{idPrefix}-description"
				bind:value={description}
				placeholder="Optional description"
				rows="2"
				class="{inputClass} resize-none"
				{disabled}
			></textarea>
		{:else}
			<textarea
				id="{idPrefix}-description"
				bind:value={description}
				rows="1"
				placeholder="Optional description"
				class="input-expandable"
				use:expandable
				{disabled}
			></textarea>
		{/if}
	</div>
</div>
