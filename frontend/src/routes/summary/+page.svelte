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
	import { showToast } from '$lib/stores/ui';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';

	// Item creation status tracking
	type ItemStatus = 'pending' | 'creating' | 'success' | 'failed';
	let itemStatuses = $state<Record<number, ItemStatus>>({});
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
		
		// Initialize all items as pending
		const initialStatuses: Record<number, ItemStatus> = {};
		$confirmedItems.forEach((_, index) => {
			initialStatuses[index] = 'pending';
		});
		itemStatuses = initialStatuses;

		let successCount = 0;
		let failCount = 0;

		// Create items one-by-one with visual feedback
		for (let i = 0; i < $confirmedItems.length; i++) {
			const confirmedItem = $confirmedItems[i];
			
			// Update status to creating
			itemStatuses = { ...itemStatuses, [i]: 'creating' };

			try {
				// Create single item
				const itemInput: ItemInput = {
					name: confirmedItem.name,
					quantity: confirmedItem.quantity,
					description: confirmedItem.description,
					label_ids: confirmedItem.label_ids,
					manufacturer: confirmedItem.manufacturer,
					model_number: confirmedItem.model_number,
					serial_number: confirmedItem.serial_number,
					purchase_price: confirmedItem.purchase_price,
					purchase_from: confirmedItem.purchase_from,
					notes: confirmedItem.notes,
				};

				const response = await itemsApi.create({
					items: [itemInput],
					location_id: $selectedLocation?.id,
				});

				if (response.created.length > 0) {
					const createdItem = response.created[0] as { id?: string };
					
					// Upload images for this item
					if (createdItem?.id) {
						const sourceImage = $capturedImages[confirmedItem.sourceImageIndex];
						
						// Upload custom thumbnail or original image
						if (confirmedItem.customThumbnail) {
							try {
								const thumbnailFile = await dataUrlToFile(
									confirmedItem.customThumbnail, 
									`thumbnail_${confirmedItem.name.replace(/\s+/g, '_')}.jpg`
								);
								await itemsApi.uploadAttachment(createdItem.id, thumbnailFile);
							} catch (error) {
								console.error(`Failed to upload thumbnail for ${confirmedItem.name}:`, error);
							}
						} else if (sourceImage?.file) {
							try {
								await itemsApi.uploadAttachment(createdItem.id, sourceImage.file);
							} catch (error) {
								console.error(`Failed to upload image for ${confirmedItem.name}:`, error);
							}
						}

						// Upload additional images if any
						if (confirmedItem.additionalImages) {
							for (const addImage of confirmedItem.additionalImages) {
								try {
									await itemsApi.uploadAttachment(createdItem.id, addImage);
								} catch (error) {
									console.error(`Failed to upload additional image for ${confirmedItem.name}:`, error);
								}
							}
						}
					}

					// Mark as success
					itemStatuses = { ...itemStatuses, [i]: 'success' };
					successCount++;
				} else {
					// Item creation failed
					itemStatuses = { ...itemStatuses, [i]: 'failed' };
					failCount++;
				}
			} catch (error) {
				console.error(`Failed to create item ${confirmedItem.name}:`, error);
				itemStatuses = { ...itemStatuses, [i]: 'failed' };
				failCount++;
			}
		}

		// All items processed
		isSubmitting = false;

		// Handle results
		if (failCount > 0) {
			showToast(`Created ${successCount} items, ${failCount} failed`, 'warning');
		} else {
			// All items created successfully - navigate to success
			resetItemState();
			goto('/success');
		}
	}

	// Retry failed items
	async function retryFailed() {
		const failedIndices = Object.entries(itemStatuses)
			.filter(([_, status]) => status === 'failed')
			.map(([index]) => parseInt(index));
		
		if (failedIndices.length === 0) return;

		isSubmitting = true;
		let successCount = 0;
		let failCount = 0;

		for (const i of failedIndices) {
			const confirmedItem = $confirmedItems[i];
			if (!confirmedItem) continue;
			
			itemStatuses = { ...itemStatuses, [i]: 'creating' };

			try {
				const itemInput: ItemInput = {
					name: confirmedItem.name,
					quantity: confirmedItem.quantity,
					description: confirmedItem.description,
					label_ids: confirmedItem.label_ids,
					manufacturer: confirmedItem.manufacturer,
					model_number: confirmedItem.model_number,
					serial_number: confirmedItem.serial_number,
					purchase_price: confirmedItem.purchase_price,
					purchase_from: confirmedItem.purchase_from,
					notes: confirmedItem.notes,
				};

				const response = await itemsApi.create({
					items: [itemInput],
					location_id: $selectedLocation?.id,
				});

				if (response.created.length > 0) {
					const createdItem = response.created[0] as { id?: string };
					
					if (createdItem?.id) {
						const sourceImage = $capturedImages[confirmedItem.sourceImageIndex];
						
						if (confirmedItem.customThumbnail) {
							try {
								const thumbnailFile = await dataUrlToFile(
									confirmedItem.customThumbnail, 
									`thumbnail_${confirmedItem.name.replace(/\s+/g, '_')}.jpg`
								);
								await itemsApi.uploadAttachment(createdItem.id, thumbnailFile);
							} catch (error) {
								console.error(`Failed to upload thumbnail for ${confirmedItem.name}:`, error);
							}
						} else if (sourceImage?.file) {
							try {
								await itemsApi.uploadAttachment(createdItem.id, sourceImage.file);
							} catch (error) {
								console.error(`Failed to upload image for ${confirmedItem.name}:`, error);
							}
						}

						if (confirmedItem.additionalImages) {
							for (const addImage of confirmedItem.additionalImages) {
								try {
									await itemsApi.uploadAttachment(createdItem.id, addImage);
								} catch (error) {
									console.error(`Failed to upload additional image for ${confirmedItem.name}:`, error);
								}
							}
						}
					}

					itemStatuses = { ...itemStatuses, [i]: 'success' };
					successCount++;
				} else {
					itemStatuses = { ...itemStatuses, [i]: 'failed' };
					failCount++;
				}
			} catch (error) {
				console.error(`Failed to create item ${confirmedItem.name}:`, error);
				itemStatuses = { ...itemStatuses, [i]: 'failed' };
				failCount++;
			}
		}

		isSubmitting = false;

		if (failCount > 0) {
			showToast(`Retried: ${successCount} succeeded, ${failCount} still failing`, 'warning');
		} else {
			// Check if all items are now successful
			const allSuccess = Object.values(itemStatuses).every(s => s === 'success');
			if (allSuccess) {
				resetItemState();
				goto('/success');
			}
		}
	}

	// Check if there are any failed items
	function hasFailedItems(): boolean {
		return Object.values(itemStatuses).some(s => s === 'failed');
	}

	// Check if all items are successful
	function allItemsSuccessful(): boolean {
		return Object.keys(itemStatuses).length > 0 && 
			Object.values(itemStatuses).every(s => s === 'success');
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

				<!-- Status indicator or action buttons -->
				<div class="flex flex-col gap-1 items-center justify-center min-w-[40px]">
					{#if itemStatuses[index] === 'creating'}
						<!-- Spinner -->
						<div class="w-8 h-8 flex items-center justify-center">
							<div class="w-5 h-5 rounded-full border-2 border-primary/30 border-t-primary animate-spin"></div>
						</div>
					{:else if itemStatuses[index] === 'success'}
						<!-- Checkmark -->
						<div class="w-8 h-8 flex items-center justify-center bg-green-500/20 rounded-full">
							<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
								<polyline points="20 6 9 17 4 12" />
							</svg>
						</div>
					{:else if itemStatuses[index] === 'failed'}
						<!-- Error icon -->
						<div class="w-8 h-8 flex items-center justify-center bg-danger/20 rounded-full">
							<svg class="w-5 h-5 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
								<line x1="18" y1="6" x2="6" y2="18" />
								<line x1="6" y1="6" x2="18" y2="18" />
							</svg>
						</div>
					{:else}
						<!-- Default: Edit/Remove buttons -->
						<button
							type="button"
							class="p-2 text-text-muted hover:text-primary hover:bg-primary/10 rounded-lg transition-colors"
							aria-label="Edit item"
							title="Edit item"
							disabled={isSubmitting}
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
							disabled={isSubmitting}
							onclick={() => removeItem(index)}
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<polyline points="3 6 5 6 21 6" />
								<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
							</svg>
						</button>
					{/if}
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
		{#if !hasFailedItems() && !allItemsSuccessful()}
			<Button variant="secondary" full onclick={addMoreItems} disabled={isSubmitting}>
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
		{:else if hasFailedItems()}
			<Button
				variant="primary"
				full
				loading={isSubmitting}
				onclick={retryFailed}
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path d="M1 4v6h6" />
					<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
				</svg>
				<span>Retry Failed Items</span>
			</Button>

			<Button
				variant="secondary"
				full
				disabled={isSubmitting}
				onclick={() => { resetItemState(); goto('/success'); }}
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="20 6 9 17 4 12" />
				</svg>
				<span>Continue with Successful Items</span>
			</Button>
		{/if}
	</div>
</div>

