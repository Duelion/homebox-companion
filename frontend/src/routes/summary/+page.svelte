<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";
	import { labels } from "$lib/stores/labels";
	import { showToast } from "$lib/stores/ui";
	import { markSessionExpired } from "$lib/stores/auth";
	import { scanWorkflow } from "$lib/workflows/scan.svelte";
	import { createObjectUrlManager } from "$lib/utils/objectUrl";
	import { routeGuards } from "$lib/utils/routeGuard";
	import type { ConfirmedItem } from "$lib/types";
	import Button from "$lib/components/Button.svelte";
	import StepIndicator from "$lib/components/StepIndicator.svelte";
	import StatusIcon from "$lib/components/StatusIcon.svelte";
	import AnalysisProgressBar from "$lib/components/AnalysisProgressBar.svelte";

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
	let progressBarRef = $state<HTMLDivElement | null>(null);

	// Calculate summary statistics
	const totalPhotos = $derived(
		confirmedItems.reduce((count, item) => {
			let photos = 0;
			// Custom thumbnail replaces original, so count as one primary image
			if (item.originalFile || item.customThumbnail) photos++;
			if (item.additionalImages) photos += item.additionalImages.length;
			return count + photos;
		}, 0),
	);

	function getLabelName(labelId: string): string {
		const label = $labels.find((l) => l.id === labelId);
		return label?.name ?? labelId;
	}

	// Apply route guard and setup cleanup
	onMount(() => {
		if (!routeGuards.summary()) return;
		// Cleanup object URLs only on component unmount
		return () => urlManager.cleanup();
	});

	function removeItem(index: number) {
		const item = confirmedItems[index];
		workflow.removeConfirmedItem(index);

		if (confirmedItems.length === 0) {
			goto("/capture");
		}
	}

	function editItem(index: number) {
		workflow.editConfirmedItem(index);
		goto("/review");
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
			showToast("No items to submit", "warning");
			return;
		}

		isSubmitting = true;
		// Scroll to top of app
		setTimeout(() => {
			window.scrollTo({ top: 0, behavior: "smooth" });
		}, 100);
		const result = await workflow.submitAll();
		isSubmitting = false;

		if (result.sessionExpired) {
			// Token missing - trigger re-auth modal
			markSessionExpired();
			return;
		}

		// Show appropriate toast based on results
		if (
			result.failCount > 0 &&
			result.successCount === 0 &&
			result.partialSuccessCount === 0
		) {
			showToast("All items failed to create", "error");
		} else if (result.failCount > 0) {
			showToast(
				`Created ${result.successCount + result.partialSuccessCount} items, ${result.failCount} failed`,
				"warning",
			);
		} else if (result.partialSuccessCount > 0) {
			showToast(
				`${result.partialSuccessCount} item(s) created with missing attachments`,
				"warning",
			);
			goto("/success");
		} else if (result.success) {
			goto("/success");
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
				"warning",
			);
		} else if (result.partialSuccessCount > 0) {
			showToast(
				`Retry complete: ${result.partialSuccessCount} item(s) with missing attachments`,
				"warning",
			);
			goto("/success");
		} else if (result.success) {
			goto("/success");
		}
	}

	function continueWithSuccessful() {
		// Don't reset here - let success page handle it so location is preserved for "Scan More"
		goto("/success");
	}
</script>

<svelte:head>
	<title>Review & Submit - Homebox Companion</title>
</svelte:head>

<div class="animate-in pb-28">
	<StepIndicator currentStep={4} />

	<h2 class="text-h2 text-neutral-100 mb-1">Review & Submit</h2>
	<p class="text-body-sm text-neutral-400 mb-6">
		Confirm items to add to your inventory
	</p>

	<!-- Compact location header -->
	{#if locationPath}
		<div
			class="flex flex-wrap items-start gap-x-4 gap-y-2 text-body-sm text-neutral-400 mb-6"
		>
			<!-- Location block -->
			<div class="flex items-center gap-2">
				<svg
					class="w-4 h-4"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
					<circle cx="12" cy="10" r="3" />
				</svg>
				<span>Items will be added to:</span>
				<span class="font-semibold text-neutral-200"
					>{locationPath}</span
				>
			</div>

			<!-- Parent item block (if present) -->
			{#if parentItemName}
				<div class="flex items-center gap-2">
					<span class="text-neutral-500">Inside:</span>
					<span class="font-semibold text-primary-400"
						>{parentItemName}</span
					>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Submission progress bar -->
	{#if submissionProgress && isSubmitting}
		<div class="mb-4" bind:this={progressBarRef}>
			<AnalysisProgressBar
				current={submissionProgress.current}
				total={submissionProgress.total}
				message={submissionProgress.message || "Submitting..."}
			/>
		</div>
	{/if}

	<!-- Items list with improved cards -->
	<div class="space-y-3 mb-6">
		{#each confirmedItems as item, index}
			{@const thumbnail = getThumbnail(item)}
			<div
				class="bg-neutral-900 rounded-xl border border-neutral-700 shadow-md p-4 flex items-start gap-4 transition-all hover:border-neutral-600"
			>
				<!-- Larger thumbnail -->
				{#if thumbnail}
					<div
						class="w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-neutral-800"
					>
						<img
							src={thumbnail}
							alt={item.name}
							class="w-full h-full object-cover"
						/>
					</div>
				{:else}
					<div
						class="w-20 h-20 flex-shrink-0 rounded-lg bg-neutral-800 flex items-center justify-center"
					>
						<svg
							class="w-8 h-8 text-neutral-600"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1"
						>
							<rect
								x="3"
								y="3"
								width="18"
								height="18"
								rx="2"
								ry="2"
							/>
							<circle cx="8.5" cy="8.5" r="1.5" />
							<polyline points="21 15 16 10 5 21" />
						</svg>
					</div>
				{/if}

				<div class="flex-1 min-w-0">
					<div class="flex items-start justify-between gap-2 mb-1">
						<h3 class="font-semibold text-neutral-100 truncate">
							{item.name}
						</h3>
						<span
							class="px-2 py-0.5 bg-neutral-800 rounded text-caption text-neutral-400 flex-shrink-0"
						>
							×{item.quantity}
						</span>
					</div>
					{#if item.description}
						<p
							class="text-body-sm text-neutral-400 line-clamp-2 mb-2"
						>
							{item.description}
						</p>
					{/if}
					{#if item.label_ids && item.label_ids.length > 0}
						<div class="flex flex-wrap gap-1">
							{#each item.label_ids.slice(0, 3) as labelId}
								<span
									class="px-2 py-0.5 bg-primary-500/20 text-primary-300 rounded text-caption"
								>
									{getLabelName(labelId)}
								</span>
							{/each}
							{#if item.label_ids.length > 3}
								<span
									class="px-2 py-0.5 bg-neutral-800 text-neutral-400 rounded text-caption"
								>
									+{item.label_ids.length - 3}
								</span>
							{/if}
						</div>
					{/if}
				</div>

				<!-- Action buttons / status -->
				<div
					class="flex flex-col gap-1 items-center justify-start min-w-[44px]"
				>
					{#if itemStatuses[index] && itemStatuses[index] !== "pending"}
						<!-- Show status icon during/after submission -->
						<StatusIcon status={itemStatuses[index]} />
					{:else}
						<button
							type="button"
							class="w-11 h-11 flex items-center justify-center text-neutral-400 hover:text-primary-400 hover:bg-primary-500/10 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500/50"
							aria-label="Edit item"
							title="Edit item"
							disabled={isSubmitting}
							onclick={() => editItem(index)}
						>
							<svg
								class="w-5 h-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"
								/>
								<path
									d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"
								/>
							</svg>
						</button>
						<button
							type="button"
							class="w-11 h-11 flex items-center justify-center text-neutral-400 hover:text-error-400 hover:bg-error-500/10 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-error-500/50"
							aria-label="Remove item"
							title="Remove item"
							disabled={isSubmitting}
							onclick={() => removeItem(index)}
						>
							<svg
								class="w-5 h-5"
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
	<div class="bg-neutral-900 border border-neutral-700 rounded-xl p-4 mb-6">
		<div class="flex items-center gap-2 mb-3">
			<svg
				class="w-4 h-4 text-neutral-400"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path
					d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
				/>
			</svg>
			<span class="text-body-sm font-medium text-neutral-300"
				>Summary</span
			>
		</div>
		<ul class="space-y-1.5 text-body-sm text-neutral-400">
			<li class="flex items-center gap-2">
				<svg
					class="w-4 h-4 text-neutral-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
					/>
				</svg>
				{confirmedItems.length} item{confirmedItems.length !== 1
					? "s"
					: ""} ready to submit
			</li>
			<li class="flex items-center gap-2">
				<svg
					class="w-4 h-4 text-neutral-500"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
					<circle cx="8.5" cy="8.5" r="1.5" />
					<polyline points="21 15 16 10 5 21" />
				</svg>
				{totalPhotos} photo{totalPhotos !== 1 ? "s" : ""} will be uploaded
			</li>
		</ul>
	</div>

	<!-- Error details (shown when there are submission errors) -->
	{#if submissionErrors.length > 0}
		<div
			class="bg-error-500/10 border border-error-500/30 rounded-xl p-4 mb-6"
		>
			<div class="flex items-start gap-3">
				<svg
					class="w-5 h-5 text-error-400 flex-shrink-0 mt-0.5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="2"
				>
					<circle cx="12" cy="12" r="10" />
					<line x1="12" y1="8" x2="12" y2="12" />
					<line x1="12" y1="16" x2="12.01" y2="16" />
				</svg>
				<div class="flex-1 min-w-0">
					<h4 class="text-body-sm font-semibold text-error-300 mb-2">
						{submissionErrors.length === 1
							? "Error"
							: `${submissionErrors.length} Errors`} occurred during
						submission
					</h4>
					<ul class="space-y-1.5 text-body-sm text-error-200/80">
						{#each submissionErrors as error}
							<li class="flex items-start gap-2">
								<span class="text-error-400 flex-shrink-0"
									>•</span
								>
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
	class="fixed bottom-nav-offset left-0 right-0 bg-neutral-950/95 backdrop-blur-lg border-t border-neutral-800 p-4 z-40"
>
	<div class="max-w-lg mx-auto space-y-3">
		{#if !workflow.hasFailedItems() && !workflow.allItemsSuccessful()}
			<Button
				variant="primary"
				full
				size="lg"
				loading={isSubmitting}
				onclick={submitAll}
			>
				<svg
					class="w-5 h-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="2"
				>
					<polyline points="20 6 9 17 4 12" />
				</svg>
				<span>Submit All Items ({confirmedItems.length})</span>
			</Button>
		{:else if workflow.hasFailedItems()}
			<Button
				variant="primary"
				full
				size="lg"
				loading={isSubmitting}
				onclick={retryFailed}
			>
				<svg
					class="w-5 h-5"
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

			<Button
				variant="secondary"
				full
				disabled={isSubmitting}
				onclick={continueWithSuccessful}
			>
				<svg
					class="w-5 h-5"
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
	</div>
</div>
