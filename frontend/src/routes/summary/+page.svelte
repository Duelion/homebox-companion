<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, onDestroy } from 'svelte';
	import { labelStore } from '$lib/stores/labels.svelte';
	import { showToast } from '$lib/stores/ui.svelte';
	import { markSessionExpired } from '$lib/stores/auth.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { createObjectUrlManager } from '$lib/utils/objectUrl';
	import { routeGuards } from '$lib/utils/routeGuard';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import type { ConfirmedItem } from '$lib/types';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import StatusIcon from '$lib/components/StatusIcon.svelte';
	import AnalysisProgressBar from '$lib/components/AnalysisProgressBar.svelte';
	import AppContainer from '$lib/components/AppContainer.svelte';

	// Get workflow reference
	const workflow = scanWorkflow;

	// Object URL manager for cleanup
	const urlManager = createObjectUrlManager();

	// Derived state from workflow
	const confirmedItems = $derived(workflow.state.confirmedItems);
	const locationPath = $derived(workflow.state.locationPath);
	const parentItemName = $derived(workflow.state.parentItemName);
	const itemStatuses = $derived(workflow.state.itemStatuses);
	const submissionProgress = $derived(workflow.state.submissionProgress);
	const submissionErrors = $derived(workflow.state.submissionErrors);

	// Local UI state
	let isSubmitting = $state(false);

	// Calculate summary statistics
	const totalPhotos = $derived(
		confirmedItems.reduce((count, item) => {
			let photos = 0;
			// Custom thumbnail replaces original, so count as one primary image
			if (item.originalFile || item.customThumbnail) photos++;
			if (item.additionalImages) photos += item.additionalImages.length;
			return count + photos;
		}, 0)
	);

	function getLabelName(labelId: string): string {
		const label = labelStore.labels.find((l) => l.id === labelId);
		return label?.name ?? labelId;
	}

	// Apply route guard
	onMount(async () => {
		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		if (!routeGuards.summary()) return;
	});

	// Cleanup object URLs on component unmount
	onDestroy(() => urlManager.cleanup());

	function removeItem(index: number) {
		workflow.removeConfirmedItem(index);

		if (confirmedItems.length === 0) {
			goto(resolve('/capture'));
		}
	}

	function editItem(index: number) {
		workflow.editConfirmedItem(index);
		goto(resolve('/review'));
	}

	function getThumbnail(item: ConfirmedItem): string | null {
		if (item.customThumbnail) return item.customThumbnail;
		if (item.originalFile) return urlManager.getUrl(item.originalFile);
		return null;
	}

	// Sync object URLs when items change (cleanup removed files only)
	$effect(() => {
		const currentFiles = confirmedItems
			.map((item) => item.originalFile)
			.filter((f): f is File => f !== undefined);
		urlManager.sync(currentFiles);
	});

	async function submitAll() {
		if (confirmedItems.length === 0) {
			showToast('No items to submit', 'warning');
			return;
		}

		isSubmitting = true;
		// Scroll to top of app
		setTimeout(() => {
			window.scrollTo({ top: 0, behavior: 'smooth' });
		}, 100);
		const result = await workflow.submitAll();
		isSubmitting = false;

		if (result.sessionExpired) {
			// Token missing - trigger re-auth modal
			markSessionExpired();
			return;
		}

		// Show appropriate toast based on results
		if (result.failCount > 0 && result.successCount === 0 && result.partialSuccessCount === 0) {
			showToast('All items failed to create', 'error');
		} else if (result.failCount > 0) {
			showToast(
				`Created ${result.successCount + result.partialSuccessCount} items, ${result.failCount} failed`,
				'warning'
			);
		} else if (result.partialSuccessCount > 0) {
			showToast(
				`${result.partialSuccessCount} item(s) created with missing attachments`,
				'warning'
			);
			goto(resolve('/success'));
		} else if (result.success) {
			goto(resolve('/success'));
		}
	}

	async function retryFailed() {
		if (!workflow.hasFailedItems()) return;

		isSubmitting = true;
		const result = await workflow.retryFailed();
		isSubmitting = false;

		if (result.sessionExpired) {
			// Token missing - trigger re-auth modal
			markSessionExpired();
			return;
		}

		if (result.failCount > 0) {
			showToast(
				`Retried: ${result.successCount + result.partialSuccessCount} succeeded, ${result.failCount} still failing`,
				'warning'
			);
		} else if (result.partialSuccessCount > 0) {
			showToast(
				`Retry complete: ${result.partialSuccessCount} item(s) with missing attachments`,
				'warning'
			);
			goto(resolve('/success'));
		} else if (result.success) {
			goto(resolve('/success'));
		}
	}

	function continueWithSuccessful() {
		// Don't reset here - let success page handle it so location is preserved for "Scan More"
		goto(resolve('/success'));
	}
</script>

<svelte:head>
	<title>Review & Submit - Homebox Companion</title>
</svelte:head>

<div class="animate-in pb-28">
	<StepIndicator currentStep={4} />

	<h2 class="mb-1 text-h2 text-neutral-100">Review & Submit</h2>
	<p class="mb-6 text-body-sm text-neutral-400">Confirm items to add to your inventory</p>

	<!-- Compact location header -->
	{#if locationPath}
		<div class="mb-6 flex flex-wrap items-start gap-x-4 gap-y-2 text-body-sm text-neutral-400">
			<!-- Location block -->
			<div class="flex items-center gap-2">
				<svg
					class="h-4 w-4"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
					<circle cx="12" cy="10" r="3" />
				</svg>
				<span>Items will be added to:</span>
				<span class="font-semibold text-neutral-200">{locationPath}</span>
			</div>

			<!-- Parent item block (if present) -->
			{#if parentItemName}
				<div class="flex items-center gap-2">
					<span class="text-neutral-500">Inside:</span>
					<span class="font-semibold text-primary-400">{parentItemName}</span>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Submission progress bar -->
	{#if submissionProgress && isSubmitting}
		<div class="mb-4">
			<AnalysisProgressBar
				current={submissionProgress.current}
				total={submissionProgress.total}
				message={submissionProgress.message || 'Submitting...'}
			/>
		</div>
	{/if}

	<!-- Items list with improved cards -->
	<div class="mb-6 space-y-3">
		{#each confirmedItems as item, index (`${item.name}-${index}`)}
			{@const thumbnail = getThumbnail(item)}
			<div
				class="flex items-start gap-4 rounded-xl border border-neutral-700 bg-neutral-900 p-4 shadow-md transition-all hover:border-neutral-600"
			>
				<!-- Larger thumbnail -->
				{#if thumbnail}
					<div class="h-20 w-20 flex-shrink-0 overflow-hidden rounded-lg bg-neutral-800">
						<img src={thumbnail} alt={item.name} class="h-full w-full object-cover" />
					</div>
				{:else}
					<div
						class="flex h-20 w-20 flex-shrink-0 items-center justify-center rounded-lg bg-neutral-800"
					>
						<svg
							class="h-8 w-8 text-neutral-600"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1"
						>
							<rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
							<circle cx="8.5" cy="8.5" r="1.5" />
							<polyline points="21 15 16 10 5 21" />
						</svg>
					</div>
				{/if}

				<div class="min-w-0 flex-1">
					<div class="mb-1 flex items-start justify-between gap-2">
						<h3 class="truncate font-semibold text-neutral-100">
							{item.name}
						</h3>
						<span
							class="flex-shrink-0 rounded bg-neutral-800 px-2 py-0.5 text-caption text-neutral-400"
						>
							×{item.quantity}
						</span>
					</div>
					{#if item.description}
						<p class="mb-2 line-clamp-2 text-body-sm text-neutral-400">
							{item.description}
						</p>
					{/if}
					{#if item.label_ids && item.label_ids.length > 0}
						<div class="flex flex-wrap gap-1">
							{#each item.label_ids.slice(0, 3) as labelId (labelId)}
								<span class="rounded bg-primary-500/20 px-2 py-0.5 text-caption text-primary-300">
									{getLabelName(labelId)}
								</span>
							{/each}
							{#if item.label_ids.length > 3}
								<span class="rounded bg-neutral-800 px-2 py-0.5 text-caption text-neutral-400">
									+{item.label_ids.length - 3}
								</span>
							{/if}
						</div>
					{/if}
				</div>

				<!-- Action buttons / status -->
				<div class="flex min-w-11 flex-col items-center justify-start gap-1">
					{#if itemStatuses[index] && itemStatuses[index] !== 'pending'}
						<!-- Show status icon during/after submission -->
						<StatusIcon status={itemStatuses[index]} />
					{:else}
						<button
							type="button"
							class="flex h-11 w-11 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-primary-500/10 hover:text-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
							aria-label="Edit item"
							title="Edit item"
							disabled={isSubmitting}
							onclick={() => editItem(index)}
						>
							<svg
								class="h-5 w-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
								<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
							</svg>
						</button>
						<button
							type="button"
							class="hover:text-error-400 flex h-11 w-11 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-error-500/10 focus:outline-none focus:ring-2 focus:ring-error-500/50"
							aria-label="Remove item"
							title="Remove item"
							disabled={isSubmitting}
							onclick={() => removeItem(index)}
						>
							<svg
								class="h-5 w-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<polyline points="3 6 5 6 21 6" />
								<path
									d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
								/>
							</svg>
						</button>
					{/if}
				</div>
			</div>
		{/each}
	</div>

	<!-- Summary statistics card -->
	<div class="mb-6 rounded-xl border border-neutral-700 bg-neutral-900 p-4">
		<div class="mb-3 flex items-center gap-2">
			<svg
				class="h-4 w-4 text-neutral-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
				/>
			</svg>
			<span class="text-body-sm font-medium text-neutral-300">Summary</span>
		</div>
		<ul class="space-y-1.5 text-body-sm text-neutral-400">
			<li class="flex items-center gap-2">
				<svg
					class="h-4 w-4 text-neutral-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
				</svg>
				{confirmedItems.length} item{confirmedItems.length !== 1 ? 's' : ''} ready to submit
			</li>
			<li class="flex items-center gap-2">
				<svg
					class="h-4 w-4 text-neutral-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
					<circle cx="8.5" cy="8.5" r="1.5" />
					<polyline points="21 15 16 10 5 21" />
				</svg>
				{totalPhotos} photo{totalPhotos !== 1 ? 's' : ''} will be uploaded
			</li>
		</ul>
	</div>

	<!-- Error details (shown when there are submission errors) -->
	{#if submissionErrors.length > 0}
		<div class="mb-6 rounded-xl border border-error-500/30 bg-error-500/10 p-4">
			<div class="flex items-start gap-3">
				<svg
					class="text-error-400 mt-0.5 h-5 w-5 flex-shrink-0"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="2"
				>
					<circle cx="12" cy="12" r="10" />
					<line x1="12" y1="8" x2="12" y2="12" />
					<line x1="12" y1="16" x2="12.01" y2="16" />
				</svg>
				<div class="min-w-0 flex-1">
					<h4 class="text-error-300 mb-2 text-body-sm font-semibold">
						{submissionErrors.length === 1 ? 'Error' : `${submissionErrors.length} Errors`} occurred during
						submission
					</h4>
					<ul class="text-error-200/80 space-y-1.5 text-body-sm">
						{#each submissionErrors as error, i (i)}
							<li class="flex items-start gap-2">
								<span class="text-error-400 flex-shrink-0">•</span>
								<span class="break-words">{error}</span>
							</li>
						{/each}
					</ul>
				</div>
			</div>
		</div>
	{/if}
</div>

<!-- Sticky Submit button at bottom - above navigation bar -->
<div
	class="bottom-nav-offset fixed left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-950/95 p-4 backdrop-blur-lg"
>
	<AppContainer class="space-y-3">
		{#if !workflow.hasFailedItems() && !workflow.allItemsSuccessful()}
			<Button variant="primary" full size="lg" loading={isSubmitting} onclick={submitAll}>
				<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
					<polyline points="20 6 9 17 4 12" />
				</svg>
				<span>Submit All Items ({confirmedItems.length})</span>
			</Button>
		{:else if workflow.hasFailedItems()}
			<Button variant="primary" full size="lg" loading={isSubmitting} onclick={retryFailed}>
				<svg
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M1 4v6h6" />
					<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
				</svg>
				<span>Retry Failed Items</span>
			</Button>

			<Button variant="secondary" full disabled={isSubmitting} onclick={continueWithSuccessful}>
				<svg
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<polyline points="20 6 9 17 4 12" />
				</svg>
				<span>Continue with Successful Items</span>
			</Button>
		{/if}
	</AppContainer>
</div>
