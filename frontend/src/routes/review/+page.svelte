<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { isAuthenticated } from '$lib/stores/auth';
	import { selectedLocation } from '$lib/stores/locations';
	import { labels } from '$lib/stores/items';
	import {
		detectedItems,
		currentItemIndex,
		currentItem,
		confirmedItems,
		confirmCurrentItem,
		type ReviewItem,
	} from '$lib/stores/items';
	import { showToast } from '$lib/stores/ui';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';

	let editedItem = $state<ReviewItem | null>(null);

	// Initialize edited item from current item
	$effect(() => {
		if ($currentItem) {
			editedItem = { ...$currentItem };
		}
	});

	// Redirect if not authenticated or no items
	onMount(() => {
		if (!$isAuthenticated) {
			goto('/');
			return;
		}
		if (!$selectedLocation) {
			goto('/location');
			return;
		}
		if ($detectedItems.length === 0) {
			goto('/capture');
			return;
		}
	});

	function goBack() {
		goto('/capture');
	}

	function previousItem() {
		if ($currentItemIndex > 0) {
			currentItemIndex.update((i) => i - 1);
		}
	}

	function nextItem() {
		if ($currentItemIndex < $detectedItems.length - 1) {
			currentItemIndex.update((i) => i + 1);
		}
	}

	function skipItem() {
		if ($currentItemIndex < $detectedItems.length - 1) {
			nextItem();
		} else {
			// Last item, go to summary
			finishReview();
		}
	}

	function confirmItem() {
		if (!editedItem) return;

		// Update the item with edits before confirming
		confirmCurrentItem(editedItem);
		showToast(`"${editedItem.name}" confirmed`, 'success');

		if ($currentItemIndex < $detectedItems.length - 1) {
			nextItem();
		} else {
			finishReview();
		}
	}

	function finishReview() {
		if ($confirmedItems.length === 0) {
			showToast('No items confirmed. Please confirm at least one item.', 'warning');
			return;
		}
		goto('/summary');
	}

	function toggleLabel(labelId: string) {
		if (!editedItem) return;
		
		const currentLabels = editedItem.label_ids || [];
		if (currentLabels.includes(labelId)) {
			editedItem.label_ids = currentLabels.filter((id) => id !== labelId);
		} else {
			editedItem.label_ids = [...currentLabels, labelId];
		}
	}
</script>

<svelte:head>
	<title>Review Items - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	<button
		type="button"
		class="flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4 transition-colors"
		onclick={goBack}
	>
		<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<polyline points="15 18 9 12 15 6" />
		</svg>
		<span>Back to Capture</span>
	</button>

	<StepIndicator currentStep={3} />

	<h2 class="text-2xl font-bold text-text mb-2">Review Items</h2>
	<p class="text-text-muted mb-6">Edit or skip detected items</p>

	{#if editedItem}
		<!-- Item card -->
		<div class="bg-surface rounded-2xl border border-border overflow-hidden mb-4">
			<!-- Image preview -->
			{#if editedItem.originalFile}
				{@const imageUrl = URL.createObjectURL(editedItem.originalFile)}
				<div class="aspect-video bg-surface-elevated">
					<img
						src={imageUrl}
						alt={editedItem.name}
						class="w-full h-full object-contain"
					/>
				</div>
			{/if}

			<div class="p-4 space-y-4">
				<!-- Name -->
				<div>
					<label for="itemName" class="label">Name</label>
					<input
						type="text"
						id="itemName"
						bind:value={editedItem.name}
						class="input"
					/>
				</div>

				<!-- Quantity -->
				<div>
					<label for="itemQuantity" class="label">Quantity</label>
					<input
						type="number"
						id="itemQuantity"
						min="1"
						bind:value={editedItem.quantity}
						class="input"
					/>
				</div>

				<!-- Description -->
				<div>
					<label for="itemDescription" class="label">Description</label>
					<textarea
						id="itemDescription"
						bind:value={editedItem.description}
						rows="2"
						class="input resize-none"
					></textarea>
				</div>

			<!-- Labels -->
			{#if $labels.length > 0}
				<div>
					<span class="label">Labels</span>
					<div class="flex flex-wrap gap-2" role="group" aria-label="Select labels">
							{#each $labels as label}
								{@const isSelected = editedItem.label_ids?.includes(label.id)}
								<button
									type="button"
									class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
									class:bg-primary={isSelected}
									class:text-white={isSelected}
									class:bg-surface-elevated={!isSelected}
									class:text-text-muted={!isSelected}
									class:hover:bg-surface-hover={!isSelected}
									onclick={() => toggleLabel(label.id)}
								>
									{label.name}
								</button>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Extended fields (collapsed) -->
				{#if editedItem.manufacturer || editedItem.model_number || editedItem.serial_number}
					<details class="text-sm">
						<summary class="text-text-muted cursor-pointer hover:text-text">
							Additional details detected
						</summary>
						<div class="mt-2 space-y-2 pl-4 border-l-2 border-border">
							{#if editedItem.manufacturer}
								<p><span class="text-text-dim">Manufacturer:</span> {editedItem.manufacturer}</p>
							{/if}
							{#if editedItem.model_number}
								<p><span class="text-text-dim">Model:</span> {editedItem.model_number}</p>
							{/if}
							{#if editedItem.serial_number}
								<p><span class="text-text-dim">Serial:</span> {editedItem.serial_number}</p>
							{/if}
						</div>
					</details>
				{/if}
			</div>
		</div>

	<!-- Navigation -->
	<div class="flex items-center justify-center gap-4 mb-4">
		<button
			type="button"
			class="btn-icon"
			disabled={$currentItemIndex === 0}
			aria-label="Previous item"
			onclick={previousItem}
		>
				<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="15 18 9 12 15 6" />
				</svg>
			</button>
			<span class="text-text-muted">
				{$currentItemIndex + 1} / {$detectedItems.length}
			</span>
		<button
			type="button"
			class="btn-icon"
			disabled={$currentItemIndex === $detectedItems.length - 1}
			aria-label="Next item"
			onclick={nextItem}
		>
				<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="9 18 15 12 9 6" />
				</svg>
			</button>
		</div>

		<!-- Actions -->
		<div class="flex gap-3">
			<Button variant="secondary" onclick={skipItem}>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
				<span>Skip</span>
			</Button>
			<Button variant="primary" onclick={confirmItem}>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="20 6 9 17 4 12" />
				</svg>
				<span>Confirm</span>
			</Button>
		</div>
	{:else}
		<div class="py-12 text-center text-text-muted">
			<p>No items to review</p>
		</div>
	{/if}
</div>

