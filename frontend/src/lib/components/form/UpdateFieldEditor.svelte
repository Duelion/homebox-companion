<script lang="ts">
	/**
	 * UpdateFieldEditor - Conditional field editor for update approval actions
	 *
	 * Renders form fields based on which fields are being changed in an update action.
	 * Reduces duplication in ApprovalItemPanel.svelte by centralizing update field rendering.
	 */
	import type { FormSize } from './types';
	import { getInputClass, getLabelClass } from './types';
	import LocationSelector from './LocationSelector.svelte';
	import LabelSelector from './LabelSelector.svelte';

	interface DisplayInfo {
		target_name?: string;
		item_name?: string;
		asset_id?: string;
		location?: string;
	}

	interface Props {
		fieldsBeingChanged: string[];
		idPrefix: string;
		disabled?: boolean;
		size?: FormSize;
		displayInfo?: DisplayInfo;
		fallbackLocationId?: string;

		// Core fields
		name: string;
		quantity: number;
		description: string | null;
		notes: string | null;

		// Location/Label
		locationId: string;
		labelIds: string[];

		// Extended item fields
		manufacturer: string | null;
		modelNumber: string | null;
		serialNumber: string | null;
		purchasePrice: number | null;
		purchaseFrom: string | null;

		// Label fields
		color: string | null;

		// Location fields
		parentId: string | null;

		// Callbacks
		onToggleLabel: (labelId: string) => void;
	}

	let {
		fieldsBeingChanged,
		idPrefix,
		disabled = false,
		size = 'sm',
		displayInfo,
		fallbackLocationId,
		// Core fields (bindable)
		name = $bindable(),
		quantity = $bindable(),
		description = $bindable(),
		notes = $bindable(),
		locationId = $bindable(),
		labelIds = $bindable(),
		// Extended fields (bindable)
		manufacturer = $bindable(),
		modelNumber = $bindable(),
		serialNumber = $bindable(),
		purchasePrice = $bindable(),
		purchaseFrom = $bindable(),
		// Label/Location fields (bindable)
		color = $bindable(),
		parentId = $bindable(),
		// Callbacks
		onToggleLabel,
	}: Props = $props();

	// Check if extended fields are being updated
	const EXTENDED_FIELDS = [
		'manufacturer',
		'model_number',
		'serial_number',
		'purchase_price',
		'purchase_from',
	] as const;
	const hasExtendedFieldsBeingChanged = $derived(
		fieldsBeingChanged.some((f) => (EXTENDED_FIELDS as readonly string[]).includes(f))
	);

	// Dynamic classes based on size
	const inputClass = $derived(getInputClass(size));
	const labelClass = $derived(getLabelClass(size));
</script>

<div class="space-y-2.5">
	{#if displayInfo?.target_name || displayInfo?.item_name}
		<div class="rounded-lg bg-neutral-800/50 px-2.5 py-1.5">
			<span class="text-xs text-neutral-500">Updating:</span>
			<span class="ml-1 text-sm text-neutral-300"
				>{displayInfo.target_name ?? displayInfo.item_name}</span
			>
			{#if displayInfo.asset_id}
				<span class="text-xs text-neutral-500">({displayInfo.asset_id})</span>
			{/if}
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('name')}
		<div>
			<label for="{idPrefix}-name" class={labelClass}>New Name</label>
			<input
				type="text"
				id="{idPrefix}-name"
				bind:value={name}
				placeholder="Item name"
				class={inputClass}
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('quantity')}
		<div>
			<label for="{idPrefix}-qty" class={labelClass}>New Quantity</label>
			<input
				type="number"
				id="{idPrefix}-qty"
				min="1"
				bind:value={quantity}
				class="{inputClass} w-20"
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('description')}
		<div>
			<label for="{idPrefix}-desc" class={labelClass}>New Description</label>
			<textarea
				id="{idPrefix}-desc"
				bind:value={description}
				placeholder="Description"
				rows="2"
				class="{inputClass} resize-none"
				{disabled}
			></textarea>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('color')}
		<div>
			<label for="{idPrefix}-color" class={labelClass}>New Color</label>
			<input
				type="text"
				id="{idPrefix}-color"
				bind:value={color}
				placeholder="Color (e.g., #FF5733)"
				class={inputClass}
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('parent_id')}
		<div>
			<label for="{idPrefix}-parent" class={labelClass}>New Parent Location</label>
			<input
				type="text"
				id="{idPrefix}-parent"
				bind:value={parentId}
				placeholder="Parent Location ID (optional)"
				class={inputClass}
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('location')}
		<LocationSelector
			bind:value={locationId}
			{size}
			{disabled}
			{idPrefix}
			fallbackDisplay={displayInfo?.location ?? fallbackLocationId}
		/>
	{/if}

	{#if fieldsBeingChanged.includes('labels')}
		<LabelSelector selectedIds={labelIds} {size} {disabled} onToggle={onToggleLabel} />
	{/if}

	{#if fieldsBeingChanged.includes('notes') && !hasExtendedFieldsBeingChanged}
		<!-- Only show standalone notes when NOT also showing extended fields -->
		<div>
			<label for="{idPrefix}-notes" class={labelClass}>New Notes</label>
			<textarea
				id="{idPrefix}-notes"
				bind:value={notes}
				placeholder="Notes"
				rows="2"
				class="{inputClass} resize-none"
				{disabled}
			></textarea>
		</div>
	{/if}

	<!-- Extended fields being changed -->
	{#if fieldsBeingChanged.includes('manufacturer')}
		<div>
			<label for="{idPrefix}-manufacturer" class={labelClass}>New Manufacturer</label>
			<input
				type="text"
				id="{idPrefix}-manufacturer"
				bind:value={manufacturer}
				placeholder="Manufacturer"
				class={inputClass}
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('model_number')}
		<div>
			<label for="{idPrefix}-model" class={labelClass}>New Model Number</label>
			<input
				type="text"
				id="{idPrefix}-model"
				bind:value={modelNumber}
				placeholder="Model Number"
				class={inputClass}
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('serial_number')}
		<div>
			<label for="{idPrefix}-serial" class={labelClass}>New Serial Number</label>
			<input
				type="text"
				id="{idPrefix}-serial"
				bind:value={serialNumber}
				placeholder="Serial Number"
				class={inputClass}
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('purchase_price')}
		<div>
			<label for="{idPrefix}-price" class={labelClass}>New Purchase Price</label>
			<input
				type="number"
				id="{idPrefix}-price"
				step="0.01"
				min="0"
				bind:value={purchasePrice}
				placeholder="0.00"
				class="{inputClass} w-32"
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('purchase_from')}
		<div>
			<label for="{idPrefix}-vendor" class={labelClass}>New Purchased From</label>
			<input
				type="text"
				id="{idPrefix}-vendor"
				bind:value={purchaseFrom}
				placeholder="Vendor"
				class={inputClass}
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('notes') && hasExtendedFieldsBeingChanged}
		<!-- Notes shown here when part of extended fields update -->
		<div>
			<label for="{idPrefix}-notes-ext" class={labelClass}>New Notes</label>
			<textarea
				id="{idPrefix}-notes-ext"
				bind:value={notes}
				placeholder="Notes"
				rows="2"
				class="{inputClass} resize-none"
				{disabled}
			></textarea>
		</div>
	{/if}

	{#if fieldsBeingChanged.length === 0}
		<p class="text-sm text-neutral-500">No specific fields to edit.</p>
	{/if}
</div>
