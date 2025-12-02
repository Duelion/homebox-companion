<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { items as itemsApi, type ItemInput } from '$lib/api';
	import { isAuthenticated } from '$lib/stores/auth';
	import { selectedLocation, selectedLocationPath } from '$lib/stores/locations';
	import {
		confirmedItems,
		capturedImages,
		labels,
		removeConfirmedItem,
		editConfirmedItem,
		resetItemState,
		type ConfirmedItem,
	} from '$lib/stores/items';
	import { showToast, setLoading } from '$lib/stores/ui';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';

	let isSubmitting = $state(false);

	// Helper to get label name by ID
	function getLabelName(labelId: string): string {
		const label = $labels.find((l) => l.id === labelId);
		return label?.name ?? labelId;
	}

	// Helper to convert data URL to File
	async function dataUrlToFile(dataUrl: string, filename: string): Promise<File> {
		const response = await fetch(dataUrl);
		const blob = await response.blob();
		return new File([blob], filename, { type: blob.type || 'image/jpeg' });
	}

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
		if ($confirmedItems.length === 0) {
			goto('/capture');
			return;
		}
	});

	function addMoreItems() {
		goto('/capture');
	}

	function removeItem(index: number) {
		const item = $confirmedItems[index];
		removeConfirmedItem(index);
		showToast(`"${item.name}" removed`, 'info');

		if ($confirmedItems.length === 0) {
			goto('/capture');
		}
	}

	function editItem(index: number) {
		const item = editConfirmedItem(index);
		if (item) {
			goto('/review');
		}
	}

	function getThumbnail(item: ConfirmedItem): string | null {
		// Use custom thumbnail if available
		if (item.customThumbnail) return item.customThumbnail;
		// Otherwise get from captured images using sourceImageIndex
		const sourceImage = $capturedImages[item.sourceImageIndex];
		return sourceImage?.dataUrl ?? null;
	}

	async function submitAll() {
		if ($confirmedItems.length === 0) {
			showToast('No items to submit', 'warning');
			return;
		}

		isSubmitting = true;
		setLoading(true, 'Creating items...');

		try {
			const itemInputs: ItemInput[] = $confirmedItems.map((item) => ({
				name: item.name,
				quantity: item.quantity,
				description: item.description,
				label_ids: item.label_ids,
				manufacturer: item.manufacturer,
				model_number: item.model_number,
				serial_number: item.serial_number,
				purchase_price: item.purchase_price,
				purchase_from: item.purchase_from,
				notes: item.notes,
			}));

			const response = await itemsApi.create({
				items: itemInputs,
				location_id: $selectedLocation?.id,
			});

			if (response.errors.length > 0) {
				showToast(`Created ${response.created.length} items, ${response.errors.length} failed`, 'warning');
			} else {
				showToast(`Successfully created ${response.created.length} items!`, 'success');
			}

			// Upload images for created items
			if (response.created.length > 0) {
				setLoading(true, 'Uploading images...');
				let uploadedCount = 0;
				let uploadErrors = 0;

				for (let i = 0; i < response.created.length; i++) {
					const createdItem = response.created[i] as { id?: string };
					const confirmedItem = $confirmedItems[i];
					
					if (!createdItem?.id || !confirmedItem) continue;

					// Get the source image
					const sourceImage = $capturedImages[confirmedItem.sourceImageIndex];
					
					// Upload custom thumbnail if it exists (replaces original image)
					// OR upload original image if no custom thumbnail
					if (confirmedItem.customThumbnail) {
						// Custom thumbnail replaces the original - only upload the thumbnail
						try {
							const thumbnailFile = await dataUrlToFile(
								confirmedItem.customThumbnail, 
								`thumbnail_${confirmedItem.name.replace(/\s+/g, '_')}.jpg`
							);
							await itemsApi.uploadAttachment(createdItem.id, thumbnailFile);
							uploadedCount++;
						} catch (error) {
							console.error(`Failed to upload thumbnail for ${confirmedItem.name}:`, error);
							uploadErrors++;
						}
					} else if (sourceImage?.file) {
						// No custom thumbnail - upload original image
						try {
							await itemsApi.uploadAttachment(createdItem.id, sourceImage.file);
							uploadedCount++;
						} catch (error) {
							console.error(`Failed to upload image for ${confirmedItem.name}:`, error);
							uploadErrors++;
						}
					}

					// Upload additional images if any
					if (confirmedItem.additionalImages) {
						for (const addImage of confirmedItem.additionalImages) {
							try {
								await itemsApi.uploadAttachment(createdItem.id, addImage);
								uploadedCount++;
							} catch (error) {
								console.error(`Failed to upload additional image for ${confirmedItem.name}:`, error);
								uploadErrors++;
							}
						}
					}
				}

				if (uploadErrors > 0) {
					showToast(`Uploaded ${uploadedCount} images, ${uploadErrors} failed`, 'warning');
				} else if (uploadedCount > 0) {
					showToast(`Uploaded ${uploadedCount} images`, 'success');
				}
			}

			// Reset state and go to success
			resetItemState();
			goto('/success');
		} catch (error) {
			console.error('Failed to create items:', error);
			showToast(
				error instanceof Error ? error.message : 'Failed to create items. Please try again.',
				'error'
			);
		} finally {
			isSubmitting = false;
			setLoading(false);
		}
	}
</script>

<svelte:head>
	<title>Review & Submit - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	<StepIndicator currentStep={4} />

	<h2 class="text-2xl font-bold text-text mb-2">Review & Submit</h2>
	<p class="text-text-muted mb-6">Confirm items to add to your inventory</p>

	<!-- Items list -->
	<div class="space-y-3 mb-6">
		{#each $confirmedItems as item, index}
			{@const thumbnail = getThumbnail(item)}
			<div class="bg-surface rounded-xl border border-border p-4 flex items-start gap-3">
				<!-- Thumbnail -->
				{#if thumbnail}
					<div class="w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden bg-surface-elevated">
						<img
							src={thumbnail}
							alt={item.name}
							class="w-full h-full object-cover"
						/>
					</div>
				{:else}
					<div class="w-16 h-16 flex-shrink-0 rounded-lg bg-surface-elevated flex items-center justify-center">
						<svg class="w-6 h-6 text-text-dim" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
							<circle cx="8.5" cy="8.5" r="1.5" />
							<polyline points="21 15 16 10 5 21" />
						</svg>
					</div>
				{/if}

				<!-- Item details -->
				<div class="flex-1 min-w-0">
					<div class="flex items-center gap-2 mb-1">
						<h3 class="font-medium text-text truncate">{item.name}</h3>
						<span class="px-2 py-0.5 bg-surface-elevated rounded text-xs text-text-muted">
							×{item.quantity}
						</span>
					</div>
					{#if item.description}
						<p class="text-sm text-text-muted line-clamp-2">{item.description}</p>
					{/if}
					{#if item.label_ids && item.label_ids.length > 0}
						<div class="flex flex-wrap gap-1 mt-2">
							{#each item.label_ids as labelId}
								<span class="px-2 py-0.5 bg-primary/20 text-primary-light rounded text-xs">
									{getLabelName(labelId)}
								</span>
							{/each}
						</div>
					{/if}
				</div>

				<!-- Action buttons -->
				<div class="flex flex-col gap-1">
					<button
						type="button"
						class="p-2 text-text-muted hover:text-primary hover:bg-primary/10 rounded-lg transition-colors"
						aria-label="Edit item"
						title="Edit item"
						onclick={() => editItem(index)}
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
							<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
						</svg>
					</button>
					<button
						type="button"
						class="p-2 text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
						aria-label="Remove item"
						title="Remove item"
						onclick={() => removeItem(index)}
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<polyline points="3 6 5 6 21 6" />
							<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
						</svg>
					</button>
				</div>
			</div>
		{/each}
	</div>

	<!-- Location info -->
	<div class="flex items-center gap-2 p-3 bg-surface-elevated rounded-xl mb-6">
		<span class="text-text-muted text-sm">Location:</span>
		<span class="text-text font-medium">{$selectedLocationPath}</span>
	</div>

	<!-- Actions -->
	<div class="space-y-3">
		<Button variant="secondary" full onclick={addMoreItems}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<line x1="12" y1="5" x2="12" y2="19" />
				<line x1="5" y1="12" x2="19" y2="12" />
			</svg>
			<span>Scan More Items</span>
		</Button>

		<Button
			variant="primary"
			full
			loading={isSubmitting}
			onclick={submitAll}
		>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<polyline points="20 6 9 17 4 12" />
			</svg>
			<span>Submit All Items ({$confirmedItems.length})</span>
		</Button>
	</div>
</div>

