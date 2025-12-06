<script lang="ts">
	import type { ReviewItem } from '$lib/stores/items';

	interface Props {
		item: ReviewItem;
		expanded: boolean;
		onToggle: () => void;
	}

	let { item = $bindable(), expanded, onToggle }: Props = $props();

	// Check if item has any extended field data
	function hasData(): boolean {
		return !!(
			item.manufacturer ||
			item.model_number ||
			item.serial_number ||
			item.purchase_price ||
			item.purchase_from ||
			item.notes
		);
	}
</script>

<div class="border-t border-border pt-4">
	<button
		type="button"
		class="flex items-center gap-2 text-sm text-text-muted hover:text-text w-full"
		onclick={onToggle}
	>
		<svg
			class="w-4 h-4 transition-transform {expanded ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
		<span>Extended Fields</span>
		{#if hasData()}
			<span class="px-1.5 py-0.5 bg-primary/20 text-primary-light rounded text-xs">Has data</span>
		{/if}
	</button>

	{#if expanded}
		<div class="mt-4 space-y-4">
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label for="manufacturer" class="label">Manufacturer</label>
					<input
						type="text"
						id="manufacturer"
						bind:value={item.manufacturer}
						placeholder="e.g. DeWalt"
						class="input"
					/>
				</div>
				<div>
					<label for="modelNumber" class="label">Model Number</label>
					<input
						type="text"
						id="modelNumber"
						bind:value={item.model_number}
						placeholder="e.g. DCD771C2"
						class="input"
					/>
				</div>
			</div>

			<div>
				<label for="serialNumber" class="label">Serial Number</label>
				<input
					type="text"
					id="serialNumber"
					bind:value={item.serial_number}
					placeholder="If visible on item"
					class="input"
				/>
			</div>

			<div class="grid grid-cols-2 gap-3">
				<div>
					<label for="purchasePrice" class="label">Purchase Price</label>
					<input
						type="number"
						id="purchasePrice"
						step="0.01"
						min="0"
						bind:value={item.purchase_price}
						placeholder="0.00"
						class="input"
					/>
				</div>
				<div>
					<label for="purchaseFrom" class="label">Purchased From</label>
					<input
						type="text"
						id="purchaseFrom"
						bind:value={item.purchase_from}
						placeholder="e.g. Amazon"
						class="input"
					/>
				</div>
			</div>

			<div>
				<label for="notes" class="label">Notes</label>
				<textarea
					id="notes"
					bind:value={item.notes}
					rows="2"
					placeholder="Additional notes about the item..."
					class="input resize-none"
				></textarea>
			</div>
		</div>
	{/if}
</div>





