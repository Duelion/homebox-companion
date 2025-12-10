<script lang="ts">
	import { showToast } from '$lib/stores/ui';
	import { createObjectUrlManager } from '$lib/utils/objectUrl';

	interface Props {
		images: File[];
		customThumbnail?: string;
		onCustomThumbnailClear?: () => void;
	}

	let { images = $bindable(), customThumbnail, onCustomThumbnailClear }: Props = $props();

	let fileInput: HTMLInputElement;

	// Object URL manager for cleanup
	const urlManager = createObjectUrlManager();

	// Cleanup object URLs when component is destroyed or images change
	$effect(() => {
		urlManager.sync(images);
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

<div class="border-t border-border pt-4">
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
			
			<!-- Add more button inline -->
			<button
				type="button"
				class="flex-shrink-0 w-20 h-20 rounded-xl border border-dashed border-border/40 hover:border-primary/40 hover:bg-primary/5 flex flex-col items-center justify-center gap-1 transition-all"
				onclick={() => fileInput.click()}
			>
				<svg class="w-6 h-6 text-text-muted" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
					<line x1="12" y1="5" x2="12" y2="19" />
					<line x1="5" y1="12" x2="19" y2="12" />
				</svg>
				<span class="text-[10px] text-text-muted font-medium">Add</span>
			</button>
		</div>
	{:else}
		<!-- Empty state: prominent add button -->
		<button
			type="button"
			class="w-full p-4 rounded-xl border border-dashed border-border/40 hover:border-primary/40 hover:bg-primary/5 transition-all group"
			onclick={() => fileInput.click()}
		>
			<div class="flex items-center gap-4">
				<div class="w-12 h-12 rounded-xl bg-surface-elevated flex items-center justify-center group-hover:bg-primary/10 transition-colors">
					<svg class="w-6 h-6 text-text-muted group-hover:text-primary transition-colors" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
						<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
						<circle cx="8.5" cy="8.5" r="1.5"/>
						<polyline points="21 15 16 10 5 21"/>
						<line x1="15" y1="6" x2="15" y2="12" stroke-width="2"/>
						<line x1="12" y1="9" x2="18" y2="9" stroke-width="2"/>
					</svg>
				</div>
				<div class="flex-1 text-left">
					<p class="text-sm font-medium text-text group-hover:text-primary transition-colors">Add photos</p>
					<p class="text-xs text-text-dim">Labels, serial numbers, different angles</p>
				</div>
				<svg class="w-5 h-5 text-text-muted group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="9 18 15 12 9 6" />
				</svg>
			</div>
		</button>
	{/if}
</div>

