<script lang="ts">
	/**
	 * ItemExtendedFields - Collapsible panel for extended item fields
	 *
	 * Displays manufacturer, model, serial number, purchase info, and notes.
	 * Works with any object that implements the ItemExtended interface.
	 */
	import { slide } from 'svelte/transition';
	import type { FormSize } from './types';
	import { getInputClass, getLabelClass } from './types';

	interface Props {
		manufacturer: string | null | undefined;
		modelNumber: string | null | undefined;
		serialNumber: string | null | undefined;
		purchasePrice: number | null | undefined;
		purchaseFrom: string | null | undefined;
		notes: string | null | undefined;
		expanded: boolean;
		size?: FormSize;
		disabled?: boolean;
		idPrefix?: string;
		onToggle: () => void;
	}

	let {
		manufacturer = $bindable(),
		modelNumber = $bindable(),
		serialNumber = $bindable(),
		purchasePrice = $bindable(),
		purchaseFrom = $bindable(),
		notes = $bindable(),
		expanded,
		size = 'md',
		disabled = false,
		idPrefix = 'extended',
		onToggle,
	}: Props = $props();

	// Check if any extended field has data
	const hasData = $derived(
		!!(manufacturer || modelNumber || serialNumber || purchasePrice || purchaseFrom || notes)
	);

	// Dynamic classes based on size
	const inputClass = $derived(getInputClass(size));
	const labelClass = $derived(getLabelClass(size));
	const spacing = $derived(size === 'sm' ? 'space-y-2.5' : 'space-y-4');
	const gridGap = $derived(size === 'sm' ? 'gap-2.5' : 'gap-3');
</script>

<div class="border-t border-neutral-700 pt-4">
	<button
		type="button"
		class="flex w-full items-center gap-2 text-sm text-neutral-400 hover:text-neutral-200"
		onclick={onToggle}
		aria-expanded={expanded}
	>
		<svg
			class="h-4 w-4 transition-transform {expanded ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
		<span>Extended Fields</span>
		{#if hasData}
			<span class="rounded bg-primary/20 px-1.5 py-0.5 text-xs text-primary-light">Has data</span>
		{/if}
	</button>

	{#if expanded}
		<div class="mt-4 {spacing}" transition:slide={{ duration: 200 }}>
			<div class="grid grid-cols-2 {gridGap}">
				<div>
					<label for="{idPrefix}-manufacturer" class={labelClass}>Manufacturer</label>
					<input
						type="text"
						id="{idPrefix}-manufacturer"
						bind:value={manufacturer}
						placeholder="e.g. DeWalt"
						class={inputClass}
						{disabled}
					/>
				</div>
				<div>
					<label for="{idPrefix}-model" class={labelClass}>Model Number</label>
					<input
						type="text"
						id="{idPrefix}-model"
						bind:value={modelNumber}
						placeholder="e.g. DCD771C2"
						class={inputClass}
						{disabled}
					/>
				</div>
			</div>

			<div>
				<label for="{idPrefix}-serial" class={labelClass}>Serial Number</label>
				<input
					type="text"
					id="{idPrefix}-serial"
					bind:value={serialNumber}
					placeholder="e.g. SN123456789"
					class={inputClass}
					{disabled}
				/>
			</div>

			<div class="grid grid-cols-2 {gridGap}">
				<div>
					<label for="{idPrefix}-price" class={labelClass}>Purchase Price</label>
					<input
						type="number"
						id="{idPrefix}-price"
						step="0.01"
						min="0"
						bind:value={purchasePrice}
						placeholder="0.00"
						class={inputClass}
						{disabled}
					/>
				</div>
				<div>
					<label for="{idPrefix}-vendor" class={labelClass}>Purchased From</label>
					<input
						type="text"
						id="{idPrefix}-vendor"
						bind:value={purchaseFrom}
						placeholder="e.g. Amazon"
						class={inputClass}
						{disabled}
					/>
				</div>
			</div>

			<div>
				<label for="{idPrefix}-notes" class={labelClass}>Notes</label>
				<textarea
					id="{idPrefix}-notes"
					bind:value={notes}
					rows="2"
					placeholder="e.g., Good condition, minor scratches on left side"
					class="{inputClass} resize-none"
					{disabled}
				></textarea>
			</div>
		</div>
	{/if}
</div>
