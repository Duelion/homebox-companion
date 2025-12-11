<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { vision } from '$lib/api/vision';
	import { labels } from '$lib/stores/labels';
	import { showToast } from '$lib/stores/ui';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { createObjectUrlManager } from '$lib/utils/objectUrl';
	import { routeGuards } from '$lib/utils/routeGuard';
	import type { ReviewItem } from '$lib/types';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import ThumbnailEditor from '$lib/components/ThumbnailEditor.svelte';
	import ExtendedFieldsPanel from '$lib/components/ExtendedFieldsPanel.svelte';
	import ImagesPanel from '$lib/components/ImagesPanel.svelte';
	import AiCorrectionPanel from '$lib/components/AiCorrectionPanel.svelte';
	import BackLink from '$lib/components/BackLink.svelte';

	// Get workflow reference
	const workflow = scanWorkflow;

	// Object URL manager for cleanup
	const urlManager = createObjectUrlManager();

	// Derived state from workflow
	const detectedItems = $derived(workflow.state.detectedItems);
	const currentIndex = $derived(workflow.state.currentReviewIndex);
	const currentItem = $derived(workflow.currentItem);
	const confirmedItems = $derived(workflow.state.confirmedItems);
	const images = $derived(workflow.state.images);

	// Local UI state
	let editedItem = $state<ReviewItem | null>(null);
	let showExtendedFields = $state(false);
	let showAiCorrection = $state(false);
	let showThumbnailEditor = $state(false);
	let isProcessing = $state(false);
	let allImages = $state<File[]>([]);

	// Check if item has any extended field data
	function hasExtendedFieldData(item: ReviewItem | null): boolean {
		if (!item) return false;
		return !!(
			item.manufacturer ||
			item.model_number ||
			item.serial_number ||
			item.purchase_price ||
			item.purchase_from ||
			item.notes
		);
	}

	// Sync editedItem when currentItem changes
	$effect(() => {
		if (currentItem) {
			editedItem = { ...currentItem };
			showAiCorrection = false;
			// Build unified images array: original first, then additional
			allImages = [
				...(currentItem.originalFile ? [currentItem.originalFile] : []),
				...(currentItem.additionalImages || [])
			];
			showExtendedFields = hasExtendedFieldData(currentItem);
		}
	});

	// Apply route guard: requires auth, location, and reviewing status
	onMount(() => {
		if (!routeGuards.review()) return;
	});

	// Watch for status changes
	$effect(() => {
		if (workflow.state.status === 'confirming') {
			goto('/summary');
		}
	});

	function goBack() {
		workflow.backToCapture();
		goto('/capture');
	}

	function previousItem() {
		workflow.previousItem();
	}

	function nextItem() {
		workflow.nextItem();
	}

	function skipItem() {
		workflow.skipItem();
	}

	function confirmItem() {
		if (!editedItem) return;

		// Sync unified allImages back to item structure
		// First image becomes "original", rest become "additional"
		if (allImages.length > 0) {
			editedItem.originalFile = allImages[0];
			editedItem.additionalImages = allImages.slice(1);
		} else {
			// No images left - clear everything including custom thumbnail
			editedItem.originalFile = undefined;
			editedItem.additionalImages = [];
			editedItem.customThumbnail = undefined;
		}

		workflow.confirmItem(editedItem);
		showToast(`"${editedItem.name}" confirmed`, 'success');
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

	async function handleAiCorrection(correctionPrompt: string) {
		if (!editedItem) return;

		const sourceImage = images[editedItem.sourceImageIndex];
		if (!sourceImage) {
			showToast('Original image not found', 'error');
			return;
		}

		isProcessing = true;

		try {
			const response = await vision.correct(
				sourceImage.file,
				{
					name: editedItem.name,
					quantity: editedItem.quantity,
					description: editedItem.description,
					manufacturer: editedItem.manufacturer,
					model_number: editedItem.model_number,
					serial_number: editedItem.serial_number,
					purchase_price: editedItem.purchase_price,
					purchase_from: editedItem.purchase_from,
					notes: editedItem.notes,
				},
				correctionPrompt
			);

			if (response.items.length > 0) {
				const corrected = response.items[0];
				editedItem = {
					...editedItem,
					name: corrected.name,
					quantity: corrected.quantity,
					description: corrected.description ?? null,
					label_ids: corrected.label_ids ?? null,
					manufacturer: corrected.manufacturer ?? null,
					model_number: corrected.model_number ?? null,
					serial_number: corrected.serial_number ?? null,
					purchase_price: corrected.purchase_price ?? null,
					purchase_from: corrected.purchase_from ?? null,
					notes: corrected.notes ?? null,
				};

				showToast('Item corrected by AI', 'success');
				showAiCorrection = false;
			}
		} catch (error) {
			console.error('AI correction failed:', error);
			showToast(error instanceof Error ? error.message : 'Correction failed', 'error');
		} finally {
			isProcessing = false;
		}
	}

	function getAvailableImages(): { file: File; dataUrl: string }[] {
		return allImages.map(file => ({
			file,
			dataUrl: urlManager.getUrl(file)
		}));
	}

	function handleThumbnailSave(dataUrl: string) {
		if (editedItem) {
			editedItem.customThumbnail = dataUrl;
			showToast('Thumbnail updated', 'success');
		}
		showThumbnailEditor = false;
	}

	function getDisplayThumbnail(): string | null {
		if (!editedItem) return null;
		if (editedItem.customThumbnail) return editedItem.customThumbnail;
		if (allImages.length > 0) return urlManager.getUrl(allImages[0]);
		return null;
	}

	// Cleanup object URLs when component is destroyed or images change
	$effect(() => {
		urlManager.sync(allImages);
		return () => urlManager.cleanup();
	});
</script>

<svelte:head>
	<title>Review Items - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	<BackLink href="/capture" label="Back to Capture" onclick={goBack} />

	<StepIndicator currentStep={3} />

	<h2 class="text-2xl font-bold text-text mb-2">Review Items</h2>
	<p class="text-text-muted mb-6">Edit or skip detected items</p>

	{#if editedItem}
		{@const displayThumbnail = getDisplayThumbnail()}
		<div class="bg-surface rounded-2xl border border-border overflow-hidden mb-4">
			{#if displayThumbnail}
				<div class="aspect-video bg-surface-elevated relative group">
					<img
						src={displayThumbnail}
						alt={editedItem.name}
						class="w-full h-full object-contain"
					/>
					<button
						type="button"
						class="absolute bottom-3 right-3 px-3 py-2 bg-black/60 hover:bg-black/80 rounded-lg text-white text-sm flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
						onclick={() => (showThumbnailEditor = true)}
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
							<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
						</svg>
						<span>Edit Thumbnail</span>
					</button>
					{#if editedItem.customThumbnail}
						<span class="absolute top-3 left-3 px-2 py-1 bg-primary/80 rounded text-xs text-white">
							Custom
						</span>
					{/if}
				</div>
			{:else}
				<!-- No image placeholder -->
				<div class="aspect-video bg-surface-elevated flex flex-col items-center justify-center text-text-muted">
					<svg class="w-16 h-16 mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
						<circle cx="8.5" cy="8.5" r="1.5"/>
						<polyline points="21 15 16 10 5 21"/>
					</svg>
					<p class="text-sm">No image available</p>
					<p class="text-xs mt-1">Add photos below</p>
				</div>
			{/if}

			<div class="p-4 space-y-4">
				<div>
					<label for="itemName" class="label">Name</label>
					<input type="text" id="itemName" bind:value={editedItem.name} class="input" />
				</div>

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

				<div>
					<label for="itemDescription" class="label">Description</label>
					<textarea
						id="itemDescription"
						bind:value={editedItem.description}
						rows="2"
						class="input resize-none"
					></textarea>
				</div>

				{#if $labels.length > 0}
					<div>
						<span class="label">Labels</span>
						<div class="flex flex-wrap gap-2" role="group" aria-label="Select labels">
							{#each $labels as label}
								{@const isSelected = editedItem.label_ids?.includes(label.id)}
								<button
									type="button"
									class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors {isSelected ? 'bg-primary text-white' : 'bg-surface-elevated text-text-muted hover:bg-surface-hover'}"
									onclick={() => toggleLabel(label.id)}
								>
									{label.name}
								</button>
							{/each}
						</div>
					</div>
				{/if}

				<ExtendedFieldsPanel
					bind:item={editedItem}
					expanded={showExtendedFields}
					onToggle={() => (showExtendedFields = !showExtendedFields)}
				/>

				<ImagesPanel 
					bind:images={allImages} 
					customThumbnail={editedItem.customThumbnail}
					onCustomThumbnailClear={() => {
						if (editedItem) {
							editedItem.customThumbnail = undefined;
						}
					}}
				/>

				<AiCorrectionPanel
					expanded={showAiCorrection}
					loading={isProcessing}
					onToggle={() => (showAiCorrection = !showAiCorrection)}
					onCorrect={handleAiCorrection}
				/>
			</div>
		</div>

		<div class="flex items-center justify-center mb-4">
			<span class="text-text-muted">
				{currentIndex + 1} / {detectedItems.length}
			</span>
		</div>

		<div class="flex gap-3">
			<Button variant="secondary" onclick={skipItem} disabled={isProcessing}>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
				<span>Skip</span>
			</Button>
			<Button variant="primary" onclick={confirmItem} disabled={isProcessing}>
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

	{#if showThumbnailEditor && editedItem && allImages.length > 0}
		{@const availableImages = getAvailableImages()}
		<ThumbnailEditor
			images={availableImages}
			currentThumbnail={editedItem.customThumbnail}
			onSave={handleThumbnailSave}
			onClose={() => (showThumbnailEditor = false)}
		/>
	{/if}
</div>
