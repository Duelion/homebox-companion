<script lang="ts">
	/**
	 * ItemCoreFields - Shared form fields for name, quantity, and description
	 *
	 * Used by both the review page and approval panel for consistent item editing.
	 * Supports compact (sm) and regular (md) sizing.
	 */
	import { expandable } from '$lib/actions/expandable';
	import { itemNameError, itemQuantityError } from '$lib/utils/itemValidation';
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

	const nameError = $derived(itemNameError(name));
	const quantityError = $derived(itemQuantityError(quantity));

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
				aria-invalid={!!nameError}
				aria-describedby={nameError ? `${idPrefix}-name-error` : undefined}
				placeholder="Item name"
				class={inputClass}
				{disabled}
			/>
		{:else}
			<textarea
				id="{idPrefix}-name"
				bind:value={name}
				aria-invalid={!!nameError}
				aria-describedby={nameError ? `${idPrefix}-name-error` : undefined}
				rows="1"
				placeholder="Item name"
				class="input-expandable"
				use:expandable
				{disabled}></textarea>
		{/if}
		{#if nameError}<p
				id="{idPrefix}-name-error"
				class="mt-1 text-body-sm text-error-400"
				aria-live="polite"
			>
				{nameError}
			</p>{/if}
	</div>

	<!-- Quantity field -->
	<div>
		<label for="{idPrefix}-quantity" class={labelClass}>Quantity</label>
		<input
			type="number"
			id="{idPrefix}-quantity"
			min="1"
			bind:value={quantity}
			aria-invalid={!!quantityError}
			aria-describedby={quantityError ? `${idPrefix}-quantity-error` : undefined}
			class="{inputClass} {quantityWidth}"
			{disabled}
		/>
		{#if quantityError}<p
				id="{idPrefix}-quantity-error"
				class="mt-1 text-body-sm text-error-400"
				aria-live="polite"
			>
				{quantityError}
			</p>{/if}
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
				{disabled}></textarea>
		{:else}
			<textarea
				id="{idPrefix}-description"
				bind:value={description}
				rows="1"
				placeholder="Optional description"
				class="input-expandable"
				use:expandable
				{disabled}></textarea>
		{/if}
	</div>
</div>
