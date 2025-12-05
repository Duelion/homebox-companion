<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { vision, type DetectedItem } from '$lib/api';
	import { isAuthenticated } from '$lib/stores/auth';
	import { selectedLocation } from '$lib/stores/locations';
	import { labels, capturedImages } from '$lib/stores/items';
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
	import ThumbnailEditor from '$lib/components/ThumbnailEditor.svelte';
	import ExtendedFieldsPanel from '$lib/components/ExtendedFieldsPanel.svelte';
	import AdditionalImagesPanel from '$lib/components/AdditionalImagesPanel.svelte';
	import AiCorrectionPanel from '$lib/components/AiCorrectionPanel.svelte';

	let editedItem = $state<ReviewItem | null>(null);
	let showExtendedFields = $state(false);
	let showAiCorrection = $state(false);
	let showThumbnailEditor = $state(false);
	let isProcessing = $state(false);
	let additionalImages = $state<File[]>([]);

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

	// Initialize edited item from current item
	$effect(() => {
		if ($currentItem) {
			editedItem = { ...$currentItem };
			// Reset states when item changes
			showAiCorrection = false;
			// Initialize with existing additional images from the item
			additionalImages = $currentItem.additionalImages ? [...$currentItem.additionalImages] : [];
			// Auto-expand extended fields if there's data
			showExtendedFields = hasExtendedFieldData($currentItem);
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
			finishReview();
		}
	}

	function confirmItem() {
		if (!editedItem) return;

		// Set all additional images (combines original + newly added)
		editedItem.additionalImages = additionalImages;

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

	async function handleAiCorrection(correctionPrompt: string) {
		if (!editedItem) return;

		// Get the original image file
		const sourceImage = $capturedImages[editedItem.sourceImageIndex];
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
				// Apply ALL corrected data to the edited item (replace, don't merge)
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

	async function handleAnalyzeWithImages() {
		if (!editedItem || additionalImages.length === 0) {
			showToast('Please add additional images first', 'warning');
			return;
		}

		isProcessing = true;

		try {
			// Combine original image with additional images
			const sourceImage = $capturedImages[editedItem.sourceImageIndex];
			const allImages = sourceImage ? [sourceImage.file, ...additionalImages] : additionalImages;

			const response = await vision.analyze(
				allImages,
				editedItem.name,
				editedItem.description || undefined
			);

			// Apply ALL analyzed data (replace with new values, keep existing if not detected)
			editedItem = {
				...editedItem,
				name: response.name ?? editedItem.name,
				description: response.description ?? editedItem.description,
				label_ids: response.label_ids ?? editedItem.label_ids,
				manufacturer: response.manufacturer ?? editedItem.manufacturer,
				model_number: response.model_number ?? editedItem.model_number,
				serial_number: response.serial_number ?? editedItem.serial_number,
				purchase_price: response.purchase_price ?? editedItem.purchase_price,
				notes: response.notes ?? editedItem.notes,
			};

			showToast('Item details updated from images', 'success');
		} catch (error) {
			console.error('Analysis failed:', error);
			showToast(error instanceof Error ? error.message : 'Analysis failed', 'error');
		} finally {
			isProcessing = false;
		}
	}

	// Get all available images for this item (primary + additional) - no duplicates
	function getAvailableImages(): { file: File; dataUrl: string }[] {
		if (!editedItem) return [];

		const images: { file: File; dataUrl: string }[] = [];
		const seenFiles = new Set<string>();

		// Helper to add image if not already added (use file name + size as key)
		function addImage(file: File, dataUrl: string) {
			const key = `${file.name}-${file.size}-${file.lastModified}`;
			if (!seenFiles.has(key)) {
				seenFiles.add(key);
				images.push({ file, dataUrl });
			}
		}

		// Add primary image from captured images
		const sourceImage = $capturedImages[editedItem.sourceImageIndex];
		if (sourceImage) {
			addImage(sourceImage.file, sourceImage.dataUrl);
		}

		// Add additional images from local state (these are the current additional images)
		for (const file of additionalImages) {
			addImage(file, URL.createObjectURL(file));
		}

		return images;
	}

	function handleThumbnailSave(dataUrl: string) {
		if (editedItem) {
			editedItem.customThumbnail = dataUrl;
			showToast('Thumbnail updated', 'success');
		}
		showThumbnailEditor = false;
	}

	// Get display thumbnail (custom or original)
	function getDisplayThumbnail(): string | null {
		if (!editedItem) return null;
		if (editedItem.customThumbnail) return editedItem.customThumbnail;
		if (editedItem.originalFile) return URL.createObjectURL(editedItem.originalFile);
		return null;
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
		{@const displayThumbnail = getDisplayThumbnail()}
		<div class="bg-surface rounded-2xl border border-border overflow-hidden mb-4">
			<!-- Image preview with edit button -->
			{#if displayThumbnail}
				<div class="aspect-video bg-surface-elevated relative group">
					<img
						src={displayThumbnail}
						alt={editedItem.name}
						class="w-full h-full object-contain"
					/>
					<!-- Edit thumbnail button -->
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
			{/if}

			<div class="p-4 space-y-4">
				<!-- Name -->
				<div>
					<label for="itemName" class="label">Name</label>
					<input type="text" id="itemName" bind:value={editedItem.name} class="input" />
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

				<!-- Extended Fields Panel -->
				<ExtendedFieldsPanel
					bind:item={editedItem}
					expanded={showExtendedFields}
					onToggle={() => (showExtendedFields = !showExtendedFields)}
				/>

				<!-- Additional Images Panel -->
				<AdditionalImagesPanel
					bind:images={additionalImages}
					loading={isProcessing}
					onAnalyze={handleAnalyzeWithImages}
				/>

				<!-- AI Correction Panel -->
				<AiCorrectionPanel
					expanded={showAiCorrection}
					loading={isProcessing}
					onToggle={() => (showAiCorrection = !showAiCorrection)}
					onCorrect={handleAiCorrection}
				/>
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

	<!-- Thumbnail Editor Modal -->
	{#if showThumbnailEditor && editedItem}
		{@const availableImages = getAvailableImages()}
		{#if availableImages.length > 0}
			<ThumbnailEditor
				images={availableImages}
				currentThumbnail={editedItem.customThumbnail}
				onSave={handleThumbnailSave}
				onClose={() => (showThumbnailEditor = false)}
			/>
		{/if}
	{/if}
</div>
