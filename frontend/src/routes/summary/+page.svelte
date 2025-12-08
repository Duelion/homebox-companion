<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { items as itemsApi } from '$lib/api';
	import { isAuthenticated } from '$lib/stores/auth';
	import { labels } from '$lib/stores/labels';
	import { showToast } from '$lib/stores/ui';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import type { ConfirmedItem, ItemInput } from '$lib/types';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import LocationPickerModal from '$lib/components/LocationPickerModal.svelte';

	// Get workflow reference
	const workflow = scanWorkflow;

	// Derived state from workflow
	const confirmedItems = $derived(workflow.state.confirmedItems);
	const images = $derived(workflow.state.images);
	const locationPath = $derived(workflow.state.locationPath);
	const locationId = $derived(workflow.state.locationId);

	// Item creation status tracking
	type ItemStatus = 'pending' | 'creating' | 'success' | 'failed';
	let itemStatuses = $state<Record<number, ItemStatus>>({});
	let isSubmitting = $state(false);
	let showLocationPicker = $state(false);

	function handleLocationChange(id: string, name: string, path: string) {
		workflow.setLocation(id, name, path);
		// Keep status as confirming since we're still on summary page
		workflow.state.status = 'confirming';
		showToast(`Location changed to "${name}"`, 'success');
	}

	function getLabelName(labelId: string): string {
		const label = $labels.find((l) => l.id === labelId);
		return label?.name ?? labelId;
	}

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
		if (!locationId) {
			goto('/location');
			return;
		}
		if (workflow.state.status !== 'confirming') {
			if (workflow.state.status === 'reviewing') {
				goto('/review');
			} else {
				goto('/capture');
			}
			return;
		}
	});

	function addMoreItems() {
		workflow.addMoreImages();
		goto('/capture');
	}

	function removeItem(index: number) {
		const item = confirmedItems[index];
		workflow.removeConfirmedItem(index);
		showToast(`"${item.name}" removed`, 'info');

		if (confirmedItems.length === 0) {
			goto('/capture');
		}
	}

	function editItem(index: number) {
		workflow.editConfirmedItem(index);
		goto('/review');
	}

	function getThumbnail(item: ConfirmedItem): string | null {
		if (item.customThumbnail) return item.customThumbnail;
		const sourceImage = images[item.sourceImageIndex];
		return sourceImage?.dataUrl ?? null;
	}

	async function submitAll() {
		if (confirmedItems.length === 0) {
			showToast('No items to submit', 'warning');
			return;
		}

		isSubmitting = true;
		
		// Initialize all items as pending
		const initialStatuses: Record<number, ItemStatus> = {};
		confirmedItems.forEach((_, index) => {
			initialStatuses[index] = 'pending';
		});
		itemStatuses = initialStatuses;

		let successCount = 0;
		let failCount = 0;

		for (let i = 0; i < confirmedItems.length; i++) {
			const confirmedItem = confirmedItems[i];
			
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
					location_id: locationId,
				});

				if (response.created.length > 0) {
					const createdItem = response.created[0] as { id?: string };
					
					if (createdItem?.id) {
						const sourceImage = images[confirmedItem.sourceImageIndex];
						
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
			showToast(`Created ${successCount} items, ${failCount} failed`, 'warning');
		} else {
			// Don't reset here - let success page handle it so location is preserved for "Scan More"
			goto('/success');
		}
	}

	async function retryFailed() {
		const failedIndices = Object.entries(itemStatuses)
			.filter(([_, status]) => status === 'failed')
			.map(([index]) => parseInt(index));
		
		if (failedIndices.length === 0) return;

		isSubmitting = true;
		let successCount = 0;
		let failCount = 0;

		for (const i of failedIndices) {
			const confirmedItem = confirmedItems[i];
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
					location_id: locationId,
				});

				if (response.created.length > 0) {
					const createdItem = response.created[0] as { id?: string };
					
					if (createdItem?.id) {
						const sourceImage = images[confirmedItem.sourceImageIndex];
						
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
			const allSuccess = Object.values(itemStatuses).every(s => s === 'success');
			if (allSuccess) {
				// Don't reset here - let success page handle it so location is preserved for "Scan More"
				goto('/success');
			}
		}
	}

	function hasFailedItems(): boolean {
		return Object.values(itemStatuses).some(s => s === 'failed');
	}

	function allItemsSuccessful(): boolean {
		return Object.keys(itemStatuses).length > 0 && 
			Object.values(itemStatuses).every(s => s === 'success');
	}

	function continueWithSuccessful() {
		// Don't reset here - let success page handle it so location is preserved for "Scan More"
		goto('/success');
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
		{#each confirmedItems as item, index}
			{@const thumbnail = getThumbnail(item)}
			<div class="bg-surface rounded-xl border border-border p-4 flex items-start gap-3">
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

				<div class="flex flex-col gap-1 items-center justify-center min-w-[40px]">
					{#if itemStatuses[index] === 'creating'}
						<div class="w-8 h-8 flex items-center justify-center">
							<div class="w-5 h-5 rounded-full border-2 border-primary/30 border-t-primary animate-spin"></div>
						</div>
					{:else if itemStatuses[index] === 'success'}
						<div class="w-8 h-8 flex items-center justify-center bg-green-500/20 rounded-full">
							<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
								<polyline points="20 6 9 17 4 12" />
							</svg>
						</div>
					{:else if itemStatuses[index] === 'failed'}
						<div class="w-8 h-8 flex items-center justify-center bg-danger/20 rounded-full">
							<svg class="w-5 h-5 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
								<line x1="18" y1="6" x2="6" y2="18" />
								<line x1="6" y1="6" x2="18" y2="18" />
							</svg>
						</div>
					{:else}
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

	<!-- Location info (clickable to change) -->
	{#if locationPath}
		<button
			type="button"
			class="w-full flex items-center justify-between p-3 bg-surface-elevated hover:bg-surface-hover rounded-xl mb-6 transition-colors group"
			onclick={() => (showLocationPicker = true)}
			disabled={isSubmitting}
		>
			<div class="flex items-center gap-2">
				<svg class="w-4 h-4 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
					<circle cx="12" cy="10" r="3" />
				</svg>
				<span class="text-text-muted text-sm">Location:</span>
				<span class="text-text font-medium">{locationPath}</span>
			</div>
			<svg
				class="w-4 h-4 text-text-muted group-hover:text-primary transition-colors"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
				<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
			</svg>
		</button>
	{/if}

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
				<span>Submit All Items ({confirmedItems.length})</span>
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
				onclick={continueWithSuccessful}
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="20 6 9 17 4 12" />
				</svg>
				<span>Continue with Successful Items</span>
			</Button>
		{/if}
	</div>
</div>

{#if showLocationPicker}
	<LocationPickerModal
		currentLocationId={locationId}
		onSelect={handleLocationChange}
		onClose={() => (showLocationPicker = false)}
	/>
{/if}
