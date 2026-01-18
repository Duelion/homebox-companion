<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { showToast } from '$lib/stores/ui.svelte';
	import { createObjectUrlManager } from '$lib/utils/objectUrl';
	import { Camera, Upload, ChevronDown, ImageIcon, X, SquarePen } from 'lucide-svelte';

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
			class="flex flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-700/40 px-3 py-2.5 transition-all hover:border-primary-500/40 hover:bg-primary-500/5"
			onclick={() => cameraInput.click()}
		>
			<Camera class="text-neutral-400" size={16} strokeWidth={1.5} />
			<span class="text-xs font-medium text-neutral-400">Camera</span>
		</button>
		<button
			type="button"
			class="flex flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-700/40 px-3 py-2.5 transition-all hover:border-primary-500/40 hover:bg-primary-500/5"
			onclick={() => fileInput.click()}
		>
			<Upload class="text-neutral-400" size={16} strokeWidth={1.5} />
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
		<ChevronDown
			class="transition-transform {expanded ? 'rotate-180' : ''}"
			size={16}
			strokeWidth={1.5}
		/>
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
					<ImageIcon class="text-primary-300" size={16} />
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
								class="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-black/70 opacity-0 transition-all hover:bg-error-500 group-hover:opacity-100"
								aria-label="Remove image"
								onclick={() => removeImage(index)}
							>
								<X class="text-white" size={14} strokeWidth={2.5} />
							</button>
							<div
								class="absolute bottom-1 left-1 rounded bg-black/60 px-1.5 py-0.5 text-xxs font-medium text-white"
							>
								{#if index === 0}
									{#if customThumbnail}
										<span class="flex items-center gap-0.5">
											<SquarePen size={10} />
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
