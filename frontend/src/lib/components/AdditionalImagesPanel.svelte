<script lang="ts">
	import { showToast } from '$lib/stores/ui';
	import Button from './Button.svelte';

	interface Props {
		images: File[];
		loading: boolean;
		onAnalyze: () => void;
	}

	let { images = $bindable(), loading, onAnalyze }: Props = $props();

	let fileInput: HTMLInputElement;

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
	}

	function getThumbnailUrl(file: File): string {
		return URL.createObjectURL(file);
	}
</script>

<div class="border-t border-border pt-4">
	<div class="flex items-center justify-between mb-3">
		<span class="text-sm text-text-muted">Additional Images</span>
		<button
			type="button"
			class="text-xs text-primary hover:underline"
			onclick={() => fileInput.click()}
		>
			+ Add Images
		</button>
	</div>

	<input
		type="file"
		accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
		multiple
		bind:this={fileInput}
		onchange={handleAddImages}
		class="hidden"
	/>

	{#if images.length > 0}
		<div class="flex flex-wrap gap-2 mb-3">
			{#each images as img, index}
				<div class="relative w-16 h-16 rounded-lg overflow-hidden bg-surface-elevated group">
					<img
						src={getThumbnailUrl(img)}
						alt="Additional {index + 1}"
						class="w-full h-full object-cover"
					/>
					<button
						type="button"
						class="absolute inset-0 bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
						aria-label="Remove image"
						onclick={() => removeImage(index)}
					>
						<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<line x1="18" y1="6" x2="6" y2="18" />
							<line x1="6" y1="6" x2="18" y2="18" />
						</svg>
					</button>
				</div>
			{/each}
		</div>
		<Button variant="secondary" onclick={onAnalyze} {loading} disabled={loading}>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<circle cx="11" cy="11" r="8" />
				<path d="m21 21-4.35-4.35" />
			</svg>
			<span>Re-analyze with Images</span>
		</Button>
	{:else}
		<p class="text-xs text-text-dim">
			Add more photos to help AI extract details like serial numbers
		</p>
	{/if}
</div>




