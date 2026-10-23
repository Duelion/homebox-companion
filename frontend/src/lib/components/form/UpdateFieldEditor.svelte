<script lang="ts">
	/**
	 * UpdateFieldEditor - Conditional field editor for update approval actions
	 *
	 * Renders form fields based on which fields are being changed in an update action.
	 * Reduces duplication in ApprovalItemPanel.svelte by centralizing update field rendering.
	 */
	import { untrack } from 'svelte';
	import { locations } from '$lib/api/locations';
	import type { FormSize } from './types';
	import { getInputClass, getLabelClass } from './types';
	import LocationSelector from './LocationSelector.svelte';
	import { locationStore } from '$lib/stores/locations.svelte';
	import TagSelector from './TagSelector.svelte';

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

		// Location/Tags
		locationId: string;
		locationOverrideId?: string;
		clearLocationOverride?: boolean;
		tagIds: string[];

		// Extended item fields
		manufacturer: string | null;
		modelNumber: string | null;
		serialNumber: string | null;
		purchasePrice: number | null;
		purchaseFrom: string | null;

		// Tag fields
		color: string | null;

		// Location fields
		parentId: string | null;

		// Callbacks
		onToggleTag: (tagId: string) => void;
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
		locationOverrideId = $bindable(''),
		clearLocationOverride = $bindable(false),
		tagIds = $bindable(),
		// Extended fields (bindable)
		manufacturer = $bindable(),
		modelNumber = $bindable(),
		serialNumber = $bindable(),
		purchasePrice = $bindable(),
		purchaseFrom = $bindable(),
		// Tag/Location fields (bindable)
		color = $bindable(),
		parentId = $bindable(),
		// Callbacks
		onToggleTag,
	}: Props = $props();

	let loadingOverrideLocations = $state(false);
	let overrideLocationsError = $state(false);
	let overrideLocationsAttempt = $state(0);
	const overrideProposalMissing = $derived(
		locationOverrideId &&
			!locationStore.flatList.some((loc) => loc.location.id === locationOverrideId)
	);

	$effect(() => {
		const needsOverrideLocations = fieldsBeingChanged.includes('location_override_id');
		void overrideLocationsAttempt;
		if (!needsOverrideLocations || untrack(() => locationStore.flatList.length > 0)) return;
		const controller = new AbortController();
		loadingOverrideLocations = true;
		overrideLocationsError = false;
		void locations
			.tree(controller.signal)
			.then((tree) => {
				if (controller.signal.aborted) return;
				locationStore.setTree(tree);
				locationStore.setFlatList(tree);
			})
			.catch(() => {
				if (!controller.signal.aborted) overrideLocationsError = true;
			})
			.finally(() => {
				if (!controller.signal.aborted) loadingOverrideLocations = false;
			});
		return () => controller.abort();
	});

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
			<span class="text-caption text-neutral-500">Updating:</span>
			<span class="ml-1 text-body-sm text-neutral-300"
				>{displayInfo.target_name ?? displayInfo.item_name}</span
			>
			{#if displayInfo.asset_id}
				<span class="text-caption text-neutral-500">({displayInfo.asset_id})</span>
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
				{disabled}></textarea>
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
			<label for="{idPrefix}-parent" class={labelClass}>New Parent</label>
			<input
				type="text"
				id="{idPrefix}-parent"
				bind:value={parentId}
				placeholder="Parent ID (leave blank to keep the current one)"
				class={inputClass}
				{disabled}
			/>
		</div>
	{/if}

	{#if fieldsBeingChanged.includes('location')}
		<p class="text-caption text-neutral-400">
			Move directly into a location, removing the parent item.
		</p>
		<LocationSelector
			bind:value={locationId}
			{size}
			{disabled}
			{idPrefix}
			fallbackDisplay={displayInfo?.location ?? fallbackLocationId}
		/>
	{/if}

	{#if fieldsBeingChanged.includes('location_override_id')}
		<div>
			<label for="{idPrefix}-location-override" class={labelClass}>Physical location override</label
			>
			<select
				id="{idPrefix}-location-override"
				bind:value={locationOverrideId}
				class={inputClass}
				{disabled}
			>
				<option value="">Cancel this override change</option>
				{#if overrideProposalMissing}
					<option value={locationOverrideId}>Proposed location ({locationOverrideId})</option>
				{/if}
				{#each locationStore.flatList as loc (loc.location.id)}
					<option value={loc.location.id}>{loc.path}</option>
				{/each}
			</select>
			<p class="text-caption text-neutral-400">
				Keeps the parent item; changes this item’s physical location.
			</p>
			{#if loadingOverrideLocations}
				<p role="status" class="text-caption text-neutral-400">Loading locations…</p>
			{:else if overrideLocationsError}
				<p role="alert" class="text-caption text-error-400">Could not load locations.</p>
				<button
					type="button"
					class="min-h-touch text-body-sm text-accent"
					onclick={() => overrideLocationsAttempt++}
					{disabled}>Retry loading locations</button
				>
			{/if}
		</div>
	{/if}
	{#if fieldsBeingChanged.includes('clear_location_override')}
		<label class="flex min-h-touch items-center gap-2 text-body-sm text-neutral-300">
			<input type="checkbox" bind:checked={clearLocationOverride} {disabled} />
			Use parent-chain location
		</label>
	{/if}

	{#if fieldsBeingChanged.includes('tags')}
		<TagSelector selectedIds={tagIds} {size} {disabled} onToggle={onToggleTag} />
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
				{disabled}></textarea>
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
				{disabled}></textarea>
		</div>
	{/if}

	{#if fieldsBeingChanged.length === 0}
		<p class="text-body-sm text-neutral-500">No specific fields to edit.</p>
	{/if}
</div>
