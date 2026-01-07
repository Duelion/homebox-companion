<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { routeGuards } from '$lib/utils/routeGuard';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import { showToast } from '$lib/stores/ui.svelte';
	import { workflowLogger as log } from '$lib/utils/logger';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import BackLink from '$lib/components/BackLink.svelte';
	import AppContainer from '$lib/components/AppContainer.svelte';

	// Get workflow reference
	const workflow = scanWorkflow;

	// Derived state from workflow
	let imageGroups = $derived(workflow.state.imageGroups);
	let images = $derived(workflow.state.images);
	let status = $derived(workflow.state.status);

	// Drag state
	let draggedImageIndex = $state<number | null>(null);
	let dragOverGroupId = $state<string | null>(null);

	// Computed: groups with detected items vs ungrouped images
	let detectedGroups = $derived(imageGroups.filter((g) => g.item !== null));
	let ungroupedImages = $derived(
		imageGroups.filter((g) => g.item === null).flatMap((g) => g.imageIndices)
	);

	// Route guard
	onMount(async () => {
		await getInitPromise();

		// Must be in grouping status
		if (workflow.state.status !== 'grouping') {
			log.warn('Not in grouping status, redirecting to capture');
			goto(resolve('/capture'));
			return;
		}
	});

	// Watch for status changes
	$effect(() => {
		if (status === 'reviewing') {
			goto(resolve('/review'));
		} else if (status === 'capturing' || status === 'idle') {
			goto(resolve('/capture'));
		}
	});

	// Watch for errors
	$effect(() => {
		if (workflow.state.error) {
			showToast(workflow.state.error, 'error');
			workflow.clearError();
		}
	});

	// Drag handlers
	function handleDragStart(e: DragEvent, imageIndex: number) {
		draggedImageIndex = imageIndex;
		if (e.dataTransfer) {
			e.dataTransfer.effectAllowed = 'move';
			e.dataTransfer.setData('text/plain', String(imageIndex));
		}
	}

	function handleDragEnd() {
		draggedImageIndex = null;
		dragOverGroupId = null;
	}

	function handleDragOver(e: DragEvent, groupId: string) {
		e.preventDefault();
		if (e.dataTransfer) {
			e.dataTransfer.dropEffect = 'move';
		}
		dragOverGroupId = groupId;
	}

	function handleDragLeave() {
		dragOverGroupId = null;
	}

	function handleDrop(e: DragEvent, targetGroupId: string) {
		e.preventDefault();
		if (draggedImageIndex !== null) {
			workflow.moveImageToGroup(draggedImageIndex, targetGroupId);
			log.info(`Moved image ${draggedImageIndex} to group ${targetGroupId}`);
		}
		draggedImageIndex = null;
		dragOverGroupId = null;
	}

	function handleNewGroupDrop(e: DragEvent) {
		e.preventDefault();
		if (draggedImageIndex !== null) {
			const newGroupId = workflow.createNewGroup([draggedImageIndex]);
			log.info(`Created new group ${newGroupId} with image ${draggedImageIndex}`);
		}
		draggedImageIndex = null;
		dragOverGroupId = null;
	}

	// Actions
	function goBack() {
		workflow.backFromGrouping();
	}

	function confirmGrouping() {
		workflow.confirmGrouping();
	}

	function splitGroup(groupId: string) {
		workflow.splitGroup(groupId);
	}

	// Get image preview URL
	function getImagePreview(imageIndex: number): string {
		const image = images[imageIndex];
		return image?.dataUrl || '';
	}

	// Get item name for a group
	function getGroupItemName(group: typeof imageGroups[0]): string {
		return group.item?.name || 'Unknown Item';
	}
</script>

<svelte:head>
	<title>Adjust Groups - Homebox Companion</title>
</svelte:head>

<div class="animate-in pb-28">
	<StepIndicator currentStep={3} />

	<h2 class="mb-1 text-h2 text-neutral-100">Adjust Image Groups</h2>
	<p class="mb-6 text-body-sm text-neutral-400">
		Drag images between groups to correct the AI grouping
	</p>

	<BackLink href="/capture" label="Back to Capture" onclick={goBack} />

	<!-- Instructions -->
	<div class="mb-6 mt-4 flex items-start gap-3 rounded-xl border border-primary-500/20 bg-primary-500/5 p-4">
		<svg
			class="mt-0.5 h-5 w-5 shrink-0 text-primary-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
		<div class="text-body-sm text-primary-200/80">
			<p class="mb-2">The AI has grouped photos it thinks show the same item.</p>
			<ul class="list-inside list-disc space-y-1 text-primary-300/70">
				<li>Drag images between groups to correct mistakes</li>
				<li>Use "Split" to separate incorrectly merged images</li>
				<li>Drag to "New Group" to create a separate item</li>
			</ul>
		</div>
	</div>

	<!-- Detected Groups -->
	{#if detectedGroups.length > 0}
		<h3 class="mb-3 text-body font-medium text-neutral-200">
			Detected Items ({detectedGroups.length})
		</h3>
		<div class="mb-6 space-y-4">
			{#each detectedGroups as group (group.id)}
				<div
					class="rounded-xl border transition-all {dragOverGroupId === group.id
						? 'border-primary-500 bg-primary-500/10'
						: 'border-neutral-700 bg-neutral-900'}"
					role="region"
					aria-label="Image group for {getGroupItemName(group)}"
					ondragover={(e) => handleDragOver(e, group.id)}
					ondragleave={handleDragLeave}
					ondrop={(e) => handleDrop(e, group.id)}
				>
					<!-- Group header -->
					<div class="flex items-center justify-between border-b border-neutral-800 p-4">
						<div class="flex items-center gap-3">
							<div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-500/10">
								<svg
									class="h-5 w-5 text-primary-400"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									stroke-width="1.5"
								>
									<path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
								</svg>
							</div>
							<div>
								<div class="text-body font-medium text-neutral-100">
									{getGroupItemName(group)}
								</div>
								<div class="text-caption text-neutral-500">
									{group.imageIndices.length} photo{group.imageIndices.length !== 1 ? 's' : ''}
								</div>
							</div>
						</div>

						{#if group.imageIndices.length > 1}
							<button
								type="button"
								class="flex items-center gap-1.5 rounded-lg border border-neutral-700 px-3 py-1.5 text-caption font-medium text-neutral-300 transition-colors hover:border-neutral-600 hover:bg-neutral-800"
								onclick={() => splitGroup(group.id)}
							>
								<svg
									class="h-4 w-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									stroke-width="1.5"
								>
									<path d="M8 7h8m-8 5h8m-8 5h8M4 7v10a2 2 0 002 2h12a2 2 0 002-2V7" />
								</svg>
								Split
							</button>
						{/if}
					</div>

					<!-- Group images -->
					<div class="flex flex-wrap gap-3 p-4">
						{#each group.imageIndices as imageIndex (imageIndex)}
							<div
								class="group relative h-24 w-24 cursor-grab overflow-hidden rounded-lg bg-neutral-800 ring-1 ring-neutral-700 transition-all active:cursor-grabbing {draggedImageIndex === imageIndex
									? 'opacity-50'
									: 'hover:ring-primary-500'}"
								draggable="true"
								ondragstart={(e) => handleDragStart(e, imageIndex)}
								ondragend={handleDragEnd}
								role="img"
								aria-label="Image {imageIndex + 1}"
							>
								<img
									src={getImagePreview(imageIndex)}
									alt="Image {imageIndex + 1}"
									class="h-full w-full object-cover"
								/>
								<div
									class="absolute bottom-1 left-1 rounded bg-black/70 px-1.5 py-0.5 text-xxs font-medium text-white"
								>
									{imageIndex + 1}
								</div>
								<!-- Drag handle indicator -->
								<div
									class="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100"
								>
									<svg
										class="h-6 w-6 text-white"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										stroke-width="1.5"
									>
										<path d="M8 9h.01M8 12h.01M8 15h.01M12 9h.01M12 12h.01M12 15h.01M16 9h.01M16 12h.01M16 15h.01" />
									</svg>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Ungrouped Images -->
	{#if ungroupedImages.length > 0}
		<h3 class="mb-3 text-body font-medium text-neutral-200">
			Ungrouped Images ({ungroupedImages.length})
		</h3>
		<div class="mb-6 rounded-xl border border-warning-500/30 bg-warning-500/5 p-4">
			<div class="mb-3 flex items-center gap-2 text-body-sm text-warning-200">
				<svg
					class="h-4 w-4 text-warning-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
				</svg>
				These images weren't identified. Drag them to a group above.
			</div>
			<div class="flex flex-wrap gap-3">
				{#each ungroupedImages as imageIndex (imageIndex)}
					<div
						class="group relative h-20 w-20 cursor-grab overflow-hidden rounded-lg bg-neutral-800 ring-1 ring-warning-500/30 transition-all active:cursor-grabbing {draggedImageIndex === imageIndex
							? 'opacity-50'
							: 'hover:ring-warning-500'}"
						draggable="true"
						ondragstart={(e) => handleDragStart(e, imageIndex)}
						ondragend={handleDragEnd}
						role="img"
						aria-label="Ungrouped image {imageIndex + 1}"
					>
						<img
							src={getImagePreview(imageIndex)}
							alt="Ungrouped {imageIndex + 1}"
							class="h-full w-full object-cover"
						/>
						<div
							class="absolute bottom-1 left-1 rounded bg-black/70 px-1.5 py-0.5 text-xxs font-medium text-white"
						>
							{imageIndex + 1}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- New Group Drop Zone -->
	<div
		class="rounded-xl border-2 border-dashed transition-all {draggedImageIndex !== null
			? dragOverGroupId === 'new-group'
				? 'border-primary-500 bg-primary-500/10'
				: 'border-neutral-600 bg-neutral-900/50'
			: 'border-neutral-800 bg-transparent'}"
		role="region"
		aria-label="Drop zone for creating new group"
		ondragover={(e) => {
			e.preventDefault();
			dragOverGroupId = 'new-group';
		}}
		ondragleave={() => {
			if (dragOverGroupId === 'new-group') dragOverGroupId = null;
		}}
		ondrop={handleNewGroupDrop}
	>
		<div class="flex items-center justify-center gap-2 p-6 text-body-sm {draggedImageIndex !== null ? 'text-neutral-300' : 'text-neutral-600'}">
			<svg
				class="h-5 w-5"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				stroke-width="1.5"
			>
				<path d="M12 4v16m8-8H4" />
			</svg>
			<span>Drop here to create a new group</span>
		</div>
	</div>
</div>

<!-- Sticky action button -->
<div
	class="bottom-nav-offset fixed left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-950/95 p-4 backdrop-blur-lg"
>
	<AppContainer>
		<div class="flex gap-3">
			<Button variant="secondary" onclick={goBack}>
				<svg
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
				</svg>
				<span>Back</span>
			</Button>
			<Button
				variant="primary"
				full
				disabled={detectedGroups.length === 0}
				onclick={confirmGrouping}
			>
				<span>Continue to Review</span>
				<svg
					class="h-5 w-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
				</svg>
			</Button>
		</div>
		{#if detectedGroups.length === 0}
			<p class="mt-2 text-center text-caption text-neutral-500">
				No items detected. Go back and add more photos.
			</p>
		{:else if ungroupedImages.length > 0}
			<p class="mt-2 text-center text-caption text-warning-400">
				{ungroupedImages.length} image{ungroupedImages.length !== 1 ? 's' : ''} not assigned to any item
			</p>
		{/if}
	</AppContainer>
</div>
