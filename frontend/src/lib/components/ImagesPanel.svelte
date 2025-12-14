<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { showToast } from '$lib/stores/ui';
	import { createObjectUrlManager } from '$lib/utils/objectUrl';

	interface Props {
		images: File[];
		customThumbnail?: string;
		onCustomThumbnailClear?: () => void;
		expanded: boolean;
		onToggle: () => void;
	}

	let { images = $bindable(), customThumbnail, onCustomThumbnailClear, expanded, onToggle }: Props = $props();

	let fileInput: HTMLInputElement;
	let cameraInput: HTMLInputElement;

	// Object URL manager for cleanup
	const urlManager = createObjectUrlManager();

	// Sync object URLs when images change (cleanup removed files only)
	$effect(() => {
		urlManager.sync(images);
	});

	// Only cleanup all URLs on component unmount
	onMount(() => {
		return () => urlManager.cleanup();
	});

	function handleAddImages(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;

		for (const file of Array.from(input.files)) {
			if (file.size > 10 * 1024 * 1024) {
				showToast(`${file.name} is too large (max 10MB)`, 'warning');
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
		class="flex items-center gap-2 text-sm text-neutral-400 hover:text-neutral-100 w-full mb-3 transition-colors"
		onclick={onToggle}
	>
		<svg
			class="w-4 h-4 transition-transform {expanded ? 'rotate-180' : ''}"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			stroke-width="1.5"
		>
			<polyline points="6 9 12 15 18 9" />
		</svg>
		<span class="font-medium">Attached Photos</span>
		{#if images.length > 0}
			<span class="ml-auto text-xs bg-neutral-800 px-2 py-0.5 rounded-full">{images.length}</span>
		{/if}
	</button>
	
	{#if expanded}
		<div transition:slide={{ duration: 200 }}>
			{#if images.length > 0}
		<!-- Has images: show gallery strip -->
		<div class="flex items-center gap-2 mb-3">
			<svg class="w-4 h-4 text-primary-light" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
				<circle cx="8.5" cy="8.5" r="1.5"/>
				<polyline points="21 15 16 10 5 21"/>
			</svg>
			<span class="text-sm font-medium text-text">
				{images.length} photo{images.length !== 1 ? 's' : ''}
			</span>
		</div>
		
		<!-- Thumbnail gallery -->
		<div class="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-thin">
			{#each images as img, index}
				<div class="relative flex-shrink-0 w-20 h-20 rounded-xl overflow-hidden bg-surface-elevated group ring-1 ring-border/50">
					<img
						src={getThumbnailUrl(img, index)}
						alt="Photo {index + 1}"
						class="w-full h-full object-cover"
					/>
					<button
						type="button"
						class="absolute top-1 right-1 w-6 h-6 bg-black/70 hover:bg-danger rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"
						aria-label="Remove image"
						onclick={() => removeImage(index)}
					>
						<svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
							<line x1="18" y1="6" x2="6" y2="18" />
							<line x1="6" y1="6" x2="18" y2="18" />
						</svg>
					</button>
					<div class="absolute bottom-1 left-1 bg-black/60 text-white text-[10px] font-medium px-1.5 py-0.5 rounded">
						{#if index === 0}
							{#if customThumbnail}
								<span class="flex items-center gap-0.5">
									<svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
		<div class="flex gap-2 mt-2">
			<button
				type="button"
				class="flex-1 py-2.5 px-3 rounded-lg border border-dashed border-border/40 hover:border-primary/40 hover:bg-primary/5 flex items-center justify-center gap-2 transition-all"
				onclick={() => cameraInput.click()}
			>
				<svg class="w-4 h-4 text-text-muted" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
					<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
					<circle cx="12" cy="13" r="4" />
				</svg>
				<span class="text-xs text-text-muted font-medium">Camera</span>
			</button>
			<button
				type="button"
				class="flex-1 py-2.5 px-3 rounded-lg border border-dashed border-border/40 hover:border-primary/40 hover:bg-primary/5 flex items-center justify-center gap-2 transition-all"
				onclick={() => fileInput.click()}
			>
				<svg class="w-4 h-4 text-text-muted" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
					<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
					<polyline points="17 8 12 3 7 8" />
					<line x1="12" y1="3" x2="12" y2="15" />
				</svg>
				<span class="text-xs text-text-muted font-medium">Upload</span>
			</button>
		</div>
{:else}
	<!-- Empty state: prominent add buttons -->
	<div class="flex gap-3">
		<button
			type="button"
			class="flex-1 p-4 rounded-xl border border-dashed border-border/40 hover:border-primary/40 hover:bg-primary/5 transition-all group"
			onclick={() => cameraInput.click()}
		>
			<div class="flex flex-col items-center gap-2">
				<div class="w-10 h-10 rounded-xl bg-surface-elevated flex items-center justify-center group-hover:bg-primary/10 transition-colors">
					<svg class="w-5 h-5 text-text-muted group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
						<circle cx="12" cy="13" r="4" />
					</svg>
				</div>
				<span class="text-xs font-medium text-text-muted group-hover:text-primary transition-colors">Camera</span>
			</div>
		</button>
		<button
			type="button"
			class="flex-1 p-4 rounded-xl border border-dashed border-border/40 hover:border-primary/40 hover:bg-primary/5 transition-all group"
			onclick={() => fileInput.click()}
		>
			<div class="flex flex-col items-center gap-2">
				<div class="w-10 h-10 rounded-xl bg-surface-elevated flex items-center justify-center group-hover:bg-primary/10 transition-colors">
					<svg class="w-5 h-5 text-text-muted group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
						<polyline points="17 8 12 3 7 8" />
						<line x1="12" y1="3" x2="12" y2="15" />
					</svg>
				</div>
				<span class="text-xs font-medium text-text-muted group-hover:text-primary transition-colors">Upload</span>
			</div>
		</button>
	</div>
	<p class="text-xs text-text-dim text-center mt-2">Labels, serial numbers, different angles</p>
		{/if}
		</div>
	{/if}
</div>

