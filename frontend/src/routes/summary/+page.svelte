<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount, onDestroy } from 'svelte';
	import { tagStore } from '$lib/stores/tags.svelte';
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
	import DuplicateWarningIcon from '$lib/components/DuplicateWarningIcon.svelte';
	import {
		MapPin,
		ImageIcon,
		SquarePen,
		Trash2,
		BarChart3,
		Package,
		AlertCircle,
		Check,
		RefreshCw,
	} from 'lucide-svelte';

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

	function getTagName(tagId: string): string {
		const tag = tagStore.tags.find((t) => t.id === tagId);
		return tag?.name ?? tagId;
	}

	// Apply route guard
	onMount(async () => {
		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		if (!routeGuards.summary()) return;

		// Show toast if any items have potential duplicates
		const duplicateCount = confirmedItems.filter((item) => item.duplicate_match).length;
		if (duplicateCount > 0) {
			showToast(
				`${duplicateCount} item${duplicateCount > 1 ? 's' : ''} may already exist in your inventory`,
				'warning'
			);
		}
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
				<MapPin size={16} strokeWidth={1.5} />
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
				class="flex items-start gap-4 rounded-xl border bg-neutral-900 p-4 shadow-md transition-all {item.duplicate_match
					? 'border-warning-500/70 hover:border-warning-400'
					: 'border-neutral-700 hover:border-neutral-600'}"
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
						<ImageIcon class="text-neutral-600" size={32} strokeWidth={1} />
					</div>
				{/if}

				<div class="min-w-0 flex-1">
					<div class="mb-1 flex items-start justify-between gap-2">
						<div class="flex min-w-0 items-center gap-2">
							<h3 class="truncate font-semibold text-neutral-100">
								{item.name}
							</h3>
							{#if item.duplicate_match}
								<DuplicateWarningIcon match={item.duplicate_match} />
							{/if}
						</div>
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
					{#if item.tag_ids && item.tag_ids.length > 0}
						<div class="flex flex-wrap gap-1.5">
							{#each item.tag_ids.slice(0, 3) as tagId (tagId)}
								<span class="rounded-md bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
									{getTagName(tagId)}
								</span>
							{/each}
							{#if item.tag_ids.length > 3}
								<span class="rounded-md bg-neutral-800 px-2 py-0.5 text-xs text-neutral-500">
									+{item.tag_ids.length - 3}
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
							<SquarePen size={20} strokeWidth={1.5} />
						</button>
						<button
							type="button"
							class="hover:text-error-400 flex h-11 w-11 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-error-500/10 focus:outline-none focus:ring-2 focus:ring-error-500/50"
							aria-label="Remove item"
							title="Remove item"
							disabled={isSubmitting}
							onclick={() => removeItem(index)}
						>
							<Trash2 size={20} strokeWidth={1.5} />
						</button>
					{/if}
				</div>
			</div>
		{/each}
	</div>

	<!-- Summary statistics card -->
	<div class="mb-6 rounded-xl border border-neutral-700 bg-neutral-900 p-4">
		<div class="mb-3 flex items-center gap-2">
			<BarChart3 class="text-neutral-400" size={16} strokeWidth={1.5} />
			<span class="text-body-sm font-medium text-neutral-300">Summary</span>
		</div>
		<ul class="space-y-1.5 text-body-sm text-neutral-400">
			<li class="flex items-center gap-2">
				<Package class="text-neutral-500" size={16} strokeWidth={1.5} />
				{confirmedItems.length} item{confirmedItems.length !== 1 ? 's' : ''} ready to submit
			</li>
			<li class="flex items-center gap-2">
				<ImageIcon class="text-neutral-500" size={16} strokeWidth={1.5} />
				{totalPhotos} photo{totalPhotos !== 1 ? 's' : ''} will be uploaded
			</li>
		</ul>
	</div>

	<!-- Error details (shown when there are submission errors) -->
	{#if submissionErrors.length > 0}
		<div class="mb-6 rounded-xl border border-error-500/30 bg-error-500/10 p-4">
			<div class="flex items-start gap-3">
				<AlertCircle class="text-error-400 mt-0.5 shrink-0" size={20} strokeWidth={2} />
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
				<Check size={20} strokeWidth={2} />
				<span>Submit All Items ({confirmedItems.length})</span>
			</Button>
		{:else if workflow.hasFailedItems()}
			<Button variant="primary" full size="lg" loading={isSubmitting} onclick={retryFailed}>
				<RefreshCw size={20} strokeWidth={1.5} />
				<span>Retry Failed Items</span>
			</Button>

			<Button variant="secondary" full disabled={isSubmitting} onclick={continueWithSuccessful}>
				<Check size={20} strokeWidth={1.5} />
				<span>Continue with Successful Items</span>
			</Button>
		{/if}
	</AppContainer>
</div>
