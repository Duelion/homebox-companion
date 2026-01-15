<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { showToast } from '$lib/stores/ui.svelte';
	import { createObjectUrlManager } from '$lib/utils/objectUrl';

	interface Props {
		images: File[];
		customThumbnail?: string;
		onCustomThumbnailClear?: () => void;
		expanded: boolean;
		onToggle: () => void;
		/** Maximum file size in MB (default: 10) */
		maxFileSizeMb?: number;
		/** Maximum number of images (optional, no limit if not provided) */
		maxImages?: number;
	}

	let {
		images = $bindable(),
		customThumbnail,
		onCustomThumbnailClear,
		expanded,
		onToggle,
		maxFileSizeMb = 10,
		maxImages,
	}: Props = $props();

	let fileInput: HTMLInputElement;
	let cameraInput: HTMLInputElement;

	// Object URL manager for cleanup
	const urlManager = createObjectUrlManager();

	// Sync object URLs when images change (cleanup removed files only)
	$effect(() => {
		urlManager.sync(images);
	});

	// Validate props on mount and cleanup URLs on unmount
	onMount(() => {
		if (maxFileSizeMb <= 0) {
			throw new Error('maxFileSizeMb must be positive');
		}
		if (maxImages !== undefined && maxImages < 0) {
			throw new Error('maxImages must be non-negative');
		}
		return () => urlManager.cleanup();
	});

	function handleAddImages(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;

		for (const file of Array.from(input.files)) {
			// Check max images limit if provided
			if (maxImages !== undefined && images.length >= maxImages) {
				showToast(`Maximum ${maxImages} images allowed`, 'warning');
				break;
			}

			// Check file size
			if (file.size > maxFileSizeMb * 1024 * 1024) {
				showToast(`${file.name} is too large (max ${maxFileSizeMb}MB)`, 'warning');
				continue;
			}
			images = [...images, file];
		}
		input.value = '';
	}

	function removeImage(index: number) {
		images = images.filter((_, i) => i !== index);
		// If removing the primary image (index 0) and there's a custom thumbnail, clear it
		if (index === 0 && customThumbnail && onCustomThumbnailClear) {
			onCustomThumbnailClear();
		}
	}

	function getThumbnailUrl(file: File, index: number): string {
		// Show custom thumbnail for the first image if it exists
		if (index === 0 && customThumbnail) {
			return customThumbnail;
		}
		return urlManager.getUrl(file);
	}
</script>

<!-- Reusable snippet for Camera/Upload buttons to avoid duplication -->
{#snippet addPhotoButtons()}
	<div class="flex gap-2">
		<button
			type="button"
			class="hover:border-primary-500/40 hover:bg-primary-500/5 flex flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-700/40 px-3 py-2.5 transition-all"
			onclick={() => cameraInput.click()}
		>
			<svg
				class="h-4 w-4 text-neutral-400"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				viewBox="0 0 24 24"
			>
				<path
					d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
				/>
				<circle cx="12" cy="13" r="4" />
			</svg>
			<span class="text-xs font-medium text-neutral-400">Camera</span>
		</button>
		<button
			type="button"
			class="hover:border-primary-500/40 hover:bg-primary-500/5 flex flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-700/40 px-3 py-2.5 transition-all"
			onclick={() => fileInput.click()}
		>
			<svg
				class="h-4 w-4 text-neutral-400"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				viewBox="0 0 24 24"
			>
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="17 8 12 3 7 8" />
				<line x1="12" y1="3" x2="12" y2="15" />
			</svg>
			<span class="text-xs font-medium text-neutral-400">Upload</span>
		</button>
	</div>
{/snippet}

<input
	type="file"
	accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
	multiple
	bind:this={fileInput}
	onchange={handleAddImages}
	class="hidden"
/>
<input
	type="file"
	accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
	capture="environment"
	multiple
	bind:this={cameraInput}
	onchange={handleAddImages}
	class="hidden"
/>

<div class="border-t border-neutral-700 pt-4">
	<button
		type="button"
		class="mb-3 flex w-full items-center gap-2 text-sm text-neutral-400 transition-colors hover:text-neutral-100"
		onclick={onToggle}
	>
		<svg
			class="h-4 w-4 transition-transform {expanded ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
		<span class="font-medium">Attached Photos</span>
		{#if images.length > 0}
			<span class="ml-auto rounded-full bg-neutral-800 px-2 py-0.5 text-xs">{images.length}</span>
		{/if}
	</button>

	{#if expanded}
		<div transition:slide={{ duration: 200 }}>
			{#if images.length > 0}
				<!-- Has images: show gallery strip -->
				<div class="mb-3 flex items-center gap-2">
					<svg
						class="text-primary-300 h-4 w-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
						<circle cx="8.5" cy="8.5" r="1.5" />
						<polyline points="21 15 16 10 5 21" />
					</svg>
					<span class="text-sm font-medium text-neutral-200">
						{images.length} photo{images.length !== 1 ? 's' : ''}
					</span>
				</div>

				<!-- Thumbnail gallery -->
				<div class="scrollbar-thin -mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
					{#each images as img, index (`${img.name}-${img.size}-${index}`)}
						<div
							class="group relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl bg-neutral-700 ring-1 ring-white/10"
						>
							<img
								src={getThumbnailUrl(img, index)}
								alt="Photo {index + 1}"
								class="h-full w-full object-cover"
							/>
							<button
								type="button"
								class="hover:bg-error-500 absolute top-1 right-1 flex h-6 w-6 items-center justify-center rounded-full bg-black/70 opacity-0 transition-all group-hover:opacity-100"
								aria-label="Remove image"
								onclick={() => removeImage(index)}
							>
								<svg
									class="h-3.5 w-3.5 text-white"
									fill="none"
									stroke="currentColor"
									stroke-width="2.5"
									viewBox="0 0 24 24"
								>
									<line x1="18" y1="6" x2="6" y2="18" />
									<line x1="6" y1="6" x2="18" y2="18" />
								</svg>
							</button>
							<div
								class="text-xxs absolute bottom-1 left-1 rounded bg-black/60 px-1.5 py-0.5 font-medium text-white"
							>
								{#if index === 0}
									{#if customThumbnail}
										<span class="flex items-center gap-0.5">
											<svg
												class="h-2.5 w-2.5"
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
												<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
											</svg>
											Edited
										</span>
									{:else}
										Primary
									{/if}
								{:else}
									{index + 1}
								{/if}
							</div>
						</div>
					{/each}
				</div>

				<!-- Add more buttons below gallery -->
				<div class="mt-2">
					{@render addPhotoButtons()}
				</div>
			{:else}
				<!-- Empty state: compact add buttons (same style as when photos exist) -->
				<p class="mb-2 text-xs text-neutral-500">Add labels, serial numbers, different angles</p>
				{@render addPhotoButtons()}
			{/if}
		</div>
	{/if}
</div>
