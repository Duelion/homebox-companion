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

	let editedItem = $state<ReviewItem | null>(null);
	let showExtendedFields = $state(false);
	let showAiCorrection = $state(false);
	let showThumbnailEditor = $state(false);

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
	let correctionPrompt = $state('');
	let isCorrectingWithAi = $state(false);
	let additionalImages = $state<File[]>([]);
	let additionalImageInput: HTMLInputElement;

	// Initialize edited item from current item
	$effect(() => {
		if ($currentItem) {
			editedItem = { ...$currentItem };
			// Reset states when item changes
			showAiCorrection = false;
			correctionPrompt = '';
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

	function handleAdditionalImages(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;
		
		for (const file of Array.from(input.files)) {
			if (file.size > 10 * 1024 * 1024) {
				showToast(`${file.name} is too large (max 10MB)`, 'warning');
				continue;
			}
			additionalImages = [...additionalImages, file];
		}
		input.value = '';
	}

	function removeAdditionalImage(index: number) {
		additionalImages = additionalImages.filter((_, i) => i !== index);
	}

	async function correctWithAi() {
		if (!editedItem || !correctionPrompt.trim()) {
			showToast('Please enter correction instructions', 'warning');
			return;
		}

		// Get the original image file
		const sourceImage = $capturedImages[editedItem.sourceImageIndex];
		if (!sourceImage) {
			showToast('Original image not found', 'error');
			return;
		}

		isCorrectingWithAi = true;

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
				correctionPrompt = '';
				showAiCorrection = false;
			}
		} catch (error) {
			console.error('AI correction failed:', error);
			showToast(
				error instanceof Error ? error.message : 'Correction failed',
				'error'
			);
		} finally {
			isCorrectingWithAi = false;
		}
	}

	async function analyzeWithMoreImages() {
		if (!editedItem || additionalImages.length === 0) {
			showToast('Please add additional images first', 'warning');
			return;
		}

		isCorrectingWithAi = true;

		try {
			// Combine original image with additional images
			const sourceImage = $capturedImages[editedItem.sourceImageIndex];
			const allImages = sourceImage 
				? [sourceImage.file, ...additionalImages]
				: additionalImages;

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
			showToast(
				error instanceof Error ? error.message : 'Analysis failed',
				'error'
			);
		} finally {
			isCorrectingWithAi = false;
		}
	}

	function getThumbnailUrl(file: File): string {
		return URL.createObjectURL(file);
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
						onclick={() => showThumbnailEditor = true}
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

				<!-- Extended Fields Section -->
				<div class="border-t border-border pt-4">
					<button
						type="button"
						class="flex items-center gap-2 text-sm text-text-muted hover:text-text w-full"
						onclick={() => showExtendedFields = !showExtendedFields}
					>
						<svg 
							class="w-4 h-4 transition-transform {showExtendedFields ? 'rotate-180' : ''}" 
							fill="none" 
							stroke="currentColor" 
							viewBox="0 0 24 24"
						>
							<polyline points="6 9 12 15 18 9" />
						</svg>
						<span>Extended Fields</span>
						{#if editedItem.manufacturer || editedItem.model_number || editedItem.serial_number || editedItem.purchase_price || editedItem.notes}
							<span class="px-1.5 py-0.5 bg-primary/20 text-primary-light rounded text-xs">Has data</span>
						{/if}
					</button>

					{#if showExtendedFields}
						<div class="mt-4 space-y-4">
							<div class="grid grid-cols-2 gap-3">
								<div>
									<label for="manufacturer" class="label">Manufacturer</label>
									<input
										type="text"
										id="manufacturer"
										bind:value={editedItem.manufacturer}
										placeholder="e.g. DeWalt"
										class="input"
									/>
								</div>
								<div>
									<label for="modelNumber" class="label">Model Number</label>
									<input
										type="text"
										id="modelNumber"
										bind:value={editedItem.model_number}
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
									bind:value={editedItem.serial_number}
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
										bind:value={editedItem.purchase_price}
										placeholder="0.00"
										class="input"
									/>
								</div>
								<div>
									<label for="purchaseFrom" class="label">Purchased From</label>
									<input
										type="text"
										id="purchaseFrom"
										bind:value={editedItem.purchase_from}
										placeholder="e.g. Amazon"
										class="input"
									/>
								</div>
							</div>

							<div>
								<label for="notes" class="label">Notes</label>
								<textarea
									id="notes"
									bind:value={editedItem.notes}
									rows="2"
									placeholder="Additional notes about the item..."
									class="input resize-none"
								></textarea>
							</div>
						</div>
					{/if}
				</div>

				<!-- Additional Images Section -->
				<div class="border-t border-border pt-4">
					<div class="flex items-center justify-between mb-3">
						<span class="text-sm text-text-muted">Additional Images</span>
						<button
							type="button"
							class="text-xs text-primary hover:underline"
							onclick={() => additionalImageInput.click()}
						>
							+ Add Images
						</button>
					</div>
					
					<input
						type="file"
						accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
						multiple
						bind:this={additionalImageInput}
						onchange={handleAdditionalImages}
						class="hidden"
					/>

					{#if additionalImages.length > 0}
						<div class="flex flex-wrap gap-2 mb-3">
							{#each additionalImages as img, index}
								<div class="relative w-16 h-16 rounded-lg overflow-hidden bg-surface-elevated group">
									<img
										src={getThumbnailUrl(img)}
										alt="Additional {index + 1}"
										class="w-full h-full object-cover"
									/>
									<button
										type="button"
										class="absolute inset-0 bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
										aria-label="Remove image"
										onclick={() => removeAdditionalImage(index)}
									>
										<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<line x1="18" y1="6" x2="6" y2="18" />
											<line x1="6" y1="6" x2="18" y2="18" />
										</svg>
									</button>
								</div>
							{/each}
						</div>
						<Button 
							variant="secondary" 
							onclick={analyzeWithMoreImages}
							loading={isCorrectingWithAi}
							disabled={isCorrectingWithAi}
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<circle cx="11" cy="11" r="8" />
								<path d="m21 21-4.35-4.35" />
							</svg>
							<span>Re-analyze with Images</span>
						</Button>
					{:else}
						<p class="text-xs text-text-dim">Add more photos to help AI extract details like serial numbers</p>
					{/if}
				</div>

				<!-- AI Correction Section -->
				<div class="border-t border-border pt-4">
					<button
						type="button"
						class="flex items-center gap-2 text-sm text-text-muted hover:text-text w-full"
						onclick={() => showAiCorrection = !showAiCorrection}
					>
						<svg 
							class="w-4 h-4 transition-transform {showAiCorrection ? 'rotate-180' : ''}" 
							fill="none" 
							stroke="currentColor" 
							viewBox="0 0 24 24"
						>
							<polyline points="6 9 12 15 18 9" />
						</svg>
						<span>AI Correction</span>
					</button>

					{#if showAiCorrection}
						<div class="mt-3 space-y-3">
							<p class="text-xs text-text-dim">
								Tell the AI what's wrong and it will re-analyze the image
							</p>
							<textarea
								bind:value={correctionPrompt}
								placeholder="e.g., 'This is actually 3 separate items' or 'The brand is Sony, not Samsung'"
								rows="2"
								class="input resize-none"
							></textarea>
							<Button 
								variant="secondary" 
								onclick={correctWithAi}
								loading={isCorrectingWithAi}
								disabled={isCorrectingWithAi || !correctionPrompt.trim()}
							>
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path d="M12 2a10 10 0 1 0 10 10H12V2z" />
									<path d="M12 2a10 10 0 0 1 10 10" />
								</svg>
								<span>Correct with AI</span>
							</Button>
						</div>
					{/if}
				</div>
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
				onClose={() => showThumbnailEditor = false}
			/>
		{/if}
	{/if}
</div>
