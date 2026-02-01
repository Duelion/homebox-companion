<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, onDestroy } from 'svelte';
	import { vision } from '$lib/api/vision';
	import { getConfig } from '$lib/api/settings';
	import { showToast } from '$lib/stores/ui.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { createObjectUrlManager } from '$lib/utils/objectUrl';
	import { routeGuards } from '$lib/utils/routeGuard';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import type { ReviewItem } from '$lib/types';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import ThumbnailEditor from '$lib/components/ThumbnailEditor.svelte';
	import { ItemCoreFields, ItemExtendedFields, TagSelector } from '$lib/components/form';
	import AppContainer from '$lib/components/AppContainer.svelte';
	import ImagesPanel from '$lib/components/ImagesPanel.svelte';
	import AiCorrectionPanel from '$lib/components/AiCorrectionPanel.svelte';
	import BackLink from '$lib/components/BackLink.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import DuplicateWarningIcon from '$lib/components/DuplicateWarningIcon.svelte';
	import { workflowLogger as log } from '$lib/utils/logger';
	import { longpress } from '$lib/actions/longpress';
	import { SquarePen, ImageIcon, ChevronsRight, Check } from 'lucide-svelte';

	// Capture limits (loaded from config, with safe defaults)
	let maxImages = $state(30);
	let maxFileSizeMb = $state(10);

	// Get workflow reference
	const workflow = scanWorkflow;

	// Object URL manager for cleanup
	const urlManager = createObjectUrlManager();

	// Derived state from workflow
	const detectedItems = $derived(workflow.state.detectedItems);
	const currentIndex = $derived(workflow.state.currentReviewIndex);
	const currentItem = $derived(workflow.currentItem);
	const images = $derived(workflow.state.images);

	// Local UI state
	let editedItem = $state<ReviewItem | null>(null);
	let showExtendedFields = $state(false);
	let showImagesPanel = $state(false);
	let showAiCorrection = $state(false);
	let showThumbnailEditor = $state(false);
	let isProcessing = $state(false);
	let allImages = $state<File[]>([]);
	let showConfirmAllDialog = $state(false);

	// Track original images to detect modifications (for invalidating compressed URLs)
	let originalImageSet = $state<Set<File>>(new Set());

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
			const imageArray = [
				...(currentItem.originalFile ? [currentItem.originalFile] : []),
				...(currentItem.additionalImages || []),
			];
			allImages = imageArray;
			// Track original images to detect modifications
			originalImageSet = new Set(imageArray);
			// Auto-expand extended fields if they have data, otherwise close all panels
			showExtendedFields = hasExtendedFieldData(currentItem);
			showImagesPanel = false;
			showAiCorrection = false;
		}
	});

	// Accordion behavior: when one panel opens, close the others
	function toggleExtendedFields() {
		showExtendedFields = !showExtendedFields;
		if (showExtendedFields) {
			showImagesPanel = false;
			showAiCorrection = false;
		}
	}

	function toggleImagesPanel() {
		showImagesPanel = !showImagesPanel;
		if (showImagesPanel) {
			showExtendedFields = false;
			showAiCorrection = false;
		}
	}

	function toggleAiCorrection() {
		showAiCorrection = !showAiCorrection;
		if (showAiCorrection) {
			showExtendedFields = false;
			showImagesPanel = false;
		}
	}

	// Apply route guard
	onMount(async () => {
		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		if (!routeGuards.review()) return;

		// Load capture limits from config
		try {
			const config = await getConfig();
			maxImages = config.capture_max_images;
			maxFileSizeMb = config.capture_max_file_size_mb;
		} catch (error) {
			log.warn('Failed to load capture config, using defaults', error);
		}
	});

	// Cleanup object URLs on component unmount
	onDestroy(() => urlManager.cleanup());

	// Watch for status changes
	$effect(() => {
		if (workflow.state.status === 'confirming') {
			goto(resolve('/summary'));
		}
	});

	function goBack() {
		workflow.backToCapture();
		goto(resolve('/capture'));
	}

	function skipItem() {
		workflow.skipItem();

		// Scroll to top for next item
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	/**
	 * Prepare the edited item for confirmation by syncing images and clearing stale URLs.
	 * Returns the prepared item ready for confirmation.
	 */
	function prepareItemForConfirmation(): ReviewItem | null {
		if (!editedItem) return null;

		// Check if images were modified (added, removed, or reordered)
		// If so, compressed URLs are stale and must be cleared
		const imagesModified = (() => {
			// Check if count changed
			if (allImages.length !== originalImageSet.size) return true;
			// Check if any image was removed or a new one added
			for (const img of allImages) {
				if (!originalImageSet.has(img)) return true;
			}
			// Check if order changed - compare full array order, not just primary
			// This ensures reordering additional images also invalidates compressed data
			const originalArray = currentItem?.originalFile
				? [currentItem.originalFile, ...(currentItem.additionalImages || [])]
				: [];
			for (let i = 0; i < allImages.length; i++) {
				if (allImages[i] !== originalArray[i]) return true;
			}
			return false;
		})();

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

		// Clear stale compressed URLs if images were modified
		if (imagesModified) {
			editedItem.compressedDataUrl = undefined;
			editedItem.compressedAdditionalDataUrls = undefined;
		}

		return editedItem;
	}

	function confirmItem() {
		const item = prepareItemForConfirmation();
		if (!item) return;

		workflow.confirmItem(item);

		// Scroll to top for next item
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	function handleLongPressConfirm() {
		showConfirmAllDialog = true;
	}

	function handleConfirmAll() {
		// Prepare the current item with any user edits
		const preparedItem = prepareItemForConfirmation();

		// Use the workflow method that handles confirming all items including the current one
		workflow.confirmAllRemainingItems(preparedItem ?? undefined);
		showConfirmAllDialog = false;

		// Navigate to summary
		goto(resolve('/summary'));
	}

	// Calculate remaining items count for dialog
	const remainingCount = $derived(detectedItems.length - currentIndex);

	function toggleTag(tagId: string) {
		if (!editedItem) return;

		const currentTags = editedItem.tag_ids || [];
		if (currentTags.includes(tagId)) {
			editedItem.tag_ids = currentTags.filter((id) => id !== tagId);
		} else {
			editedItem.tag_ids = [...currentTags, tagId];
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
					tag_ids: corrected.tag_ids ?? null,
					manufacturer: corrected.manufacturer ?? null,
					model_number: corrected.model_number ?? null,
					serial_number: corrected.serial_number ?? null,
					purchase_price: corrected.purchase_price ?? null,
					purchase_from: corrected.purchase_from ?? null,
					notes: corrected.notes ?? null,
				};

				// Visual feedback is sufficient - form updates are visible
				showAiCorrection = false;
			}
		} catch (error) {
			log.error('AI correction failed:', error);
			showToast(error instanceof Error ? error.message : 'Correction failed', 'error');
		} finally {
			isProcessing = false;
		}
	}

	// Derived images with data URLs for thumbnail editor
	const availableImages = $derived(
		allImages.map((file) => ({
			file,
			dataUrl: urlManager.getUrl(file),
		}))
	);

	// Open thumbnail editor
	function openThumbnailEditor() {
		if (!editedItem) return;
		showThumbnailEditor = true;
	}

	// Handle thumbnail save from editor
	function handleThumbnailSave(
		dataUrl: string,
		sourceImageIndex: number,
		transform: import('$lib/types').ThumbnailTransform
	) {
		if (!editedItem) return;

		editedItem.customThumbnail = dataUrl;
		editedItem.thumbnailTransform = transform;

		// If thumbnail was created from a non-primary image, reorder so it becomes primary
		if (sourceImageIndex > 0 && sourceImageIndex < allImages.length) {
			const selectedImage = allImages[sourceImageIndex];
			const reorderedImages = [
				selectedImage,
				...allImages.slice(0, sourceImageIndex),
				...allImages.slice(sourceImageIndex + 1),
			];
			allImages = reorderedImages;
			// Update transform's sourceImageIndex since we reordered
			editedItem.thumbnailTransform.sourceImageIndex = 0;
		}

		showThumbnailEditor = false;
	}

	// Derived display thumbnail - custom takes precedence, then first image
	const displayThumbnail = $derived.by(() => {
		if (!editedItem) return null;
		if (editedItem.customThumbnail) return editedItem.customThumbnail;
		if (allImages.length > 0) return urlManager.getUrl(allImages[0]);
		return null;
	});

	// Sync object URLs when images change (cleanup removed files only)
	$effect(() => {
		urlManager.sync(allImages);
	});
</script>

<svelte:head>
	<title>Review Items - Homebox Companion</title>
</svelte:head>

<div class="animate-in pb-32">
	<StepIndicator currentStep={3} />

	<h2 class="mb-1 text-h2 text-neutral-100">Review Items</h2>
	<p class="mb-6 text-body-sm text-neutral-400">Edit or skip detected items</p>

	<BackLink href="/capture" label="Back to Capture" onclick={goBack} disabled={isProcessing} />

	{#if editedItem}
		{@const thumbnail = displayThumbnail}

		<div
			class="mb-4 overflow-hidden rounded-2xl border border-neutral-700 bg-neutral-900 shadow-md"
		>
			<!-- Thumbnail section -->
			{#if thumbnail}
				<div class="group relative aspect-video bg-neutral-800">
					<img src={thumbnail} alt={editedItem.name} class="h-full w-full object-contain" />
					<!-- Edit overlay - always visible on mobile, hover on desktop -->
					<button
						type="button"
						class="absolute bottom-3 right-3 flex min-h-[44px] items-center gap-2 rounded-lg bg-black/70 px-3 py-2.5 text-sm text-white transition-all hover:bg-black/90 focus:outline-none focus:ring-2 focus:ring-white/50 md:opacity-0 md:group-hover:opacity-100"
						onclick={openThumbnailEditor}
						aria-label="Edit thumbnail image"
					>
						<SquarePen size={16} strokeWidth={1.5} />
						<span>Edit Thumbnail</span>
					</button>
					{#if editedItem.customThumbnail}
						<span
							class="absolute left-3 top-3 rounded bg-primary-600/90 px-2 py-1 text-xs font-medium text-white"
						>
							Custom
						</span>
					{/if}
				</div>
			{:else}
				<!-- No image placeholder -->
				<div
					class="flex aspect-video flex-col items-center justify-center bg-neutral-800 text-neutral-500"
				>
					<ImageIcon class="mb-2 opacity-40" size={64} strokeWidth={1} />
					<p class="text-body-sm">No image available</p>
					<p class="mt-1 text-caption">Add photos below</p>
				</div>
			{/if}

			<!-- Duplicate warning banner -->
			{#if editedItem.duplicate_match}
				<div
					class="mx-4 mt-4 flex items-center gap-3 rounded-lg border border-warning-500/30 bg-warning-500/10 p-3"
				>
					<DuplicateWarningIcon match={editedItem.duplicate_match} />
					<div class="text-body-sm">
						<p class="font-medium text-warning-300">Possible Duplicate</p>
						<p class="text-warning-200/80">This item may already exist in your inventory</p>
						<p class="mt-0.5 text-xs text-warning-200/60">
							Serial number "{editedItem.duplicate_match.serial_number}" found in "{editedItem
								.duplicate_match.item_name}"
						</p>
					</div>
				</div>
			{/if}

			<div class="space-y-5 p-4">
				<!-- Core fields: name, quantity, description -->
				<ItemCoreFields
					bind:name={editedItem.name}
					bind:quantity={editedItem.quantity}
					bind:description={editedItem.description}
					idPrefix="review"
				/>

				<!-- Tags with chip selection -->
				<TagSelector selectedIds={editedItem.tag_ids ?? []} onToggle={toggleTag} />

				<!-- Extended fields panel -->
				<ItemExtendedFields
					bind:manufacturer={editedItem.manufacturer}
					bind:modelNumber={editedItem.model_number}
					bind:serialNumber={editedItem.serial_number}
					bind:purchasePrice={editedItem.purchase_price}
					bind:purchaseFrom={editedItem.purchase_from}
					bind:notes={editedItem.notes}
					expanded={showExtendedFields}
					onToggle={toggleExtendedFields}
					idPrefix="review"
				/>

				<!-- Images panel -->
				<ImagesPanel
					bind:images={allImages}
					customThumbnail={editedItem.customThumbnail}
					onCustomThumbnailClear={() => {
						if (editedItem) {
							editedItem.customThumbnail = undefined;
						}
					}}
					expanded={showImagesPanel}
					onToggle={toggleImagesPanel}
					{maxFileSizeMb}
					{maxImages}
				/>

				<!-- AI Correction panel -->
				<AiCorrectionPanel
					expanded={showAiCorrection}
					loading={isProcessing}
					onToggle={toggleAiCorrection}
					onCorrect={handleAiCorrection}
				/>
			</div>
		</div>
	{:else}
		<div class="py-12 text-center text-neutral-500">
			<p>No items to review</p>
		</div>
	{/if}

	{#if showThumbnailEditor && editedItem && allImages.length > 0}
		<ThumbnailEditor
			images={availableImages}
			itemName={editedItem.name}
			initialTransform={editedItem.thumbnailTransform}
			onSave={handleThumbnailSave}
			onClose={() => (showThumbnailEditor = false)}
		/>
	{/if}
</div>

<!-- Sticky action footer -->
{#if editedItem}
	<div
		class="bottom-nav-offset fixed left-0 right-0 z-40 border-t border-neutral-700 bg-neutral-900/95 backdrop-blur-lg"
	>
		<AppContainer>
			<!-- Item counter in footer for mobile - positioned above bottom nav -->
			<div class="flex items-center justify-center py-3 md:hidden">
				<span class="text-body-sm font-medium text-neutral-300">
					Item {currentIndex + 1} of {detectedItems.length}
				</span>
			</div>
			<!-- Action buttons -->
			<div class="flex gap-3 px-4 pb-4">
				<div class="flex-1">
					<Button variant="secondary" full onclick={skipItem} disabled={isProcessing}>
						<ChevronsRight size={20} strokeWidth={1.5} />
						<span>Skip</span>
					</Button>
				</div>
				<div
					class="flex-1"
					use:longpress={{ onLongPress: handleLongPressConfirm, disabled: isProcessing }}
				>
					<Button variant="primary" full onclick={confirmItem} disabled={isProcessing}>
						<Check size={20} strokeWidth={2} />
						<span>Confirm</span>
					</Button>
				</div>
			</div>
		</AppContainer>
	</div>
{/if}

<!-- Confirm All Dialog -->
<ConfirmDialog
	open={showConfirmAllDialog}
	title="Confirm All Remaining Items"
	message="Confirm all {remainingCount} remaining {remainingCount === 1
		? 'item'
		: 'items'} and proceed to review & submit?"
	confirmLabel="Confirm All"
	cancelLabel="Cancel"
	onConfirm={handleConfirmAll}
	onCancel={() => (showConfirmAllDialog = false)}
/>
