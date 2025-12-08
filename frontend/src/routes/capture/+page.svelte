<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { isAuthenticated } from '$lib/stores/auth';
	import { showToast } from '$lib/stores/ui';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import type { CapturedImage } from '$lib/types';
	import Button from '$lib/components/Button.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import CaptureButtons from '$lib/components/CaptureButtons.svelte';
	import BackLink from '$lib/components/BackLink.svelte';

	const MAX_IMAGES = 30;
	const MAX_FILE_SIZE_MB = 10;

	let fileInput: HTMLInputElement;
	let cameraInput: HTMLInputElement;
	
	// Local UI state (not workflow state)
	let expandedImages = $state<Set<number>>(new Set());
	let additionalImageInputs: { [key: number]: HTMLInputElement } = {};

	// Get workflow state for reading
	const workflow = scanWorkflow;

	// Derived values from workflow state
	const images = $derived(workflow.state.images);
	const isAnalyzing = $derived(workflow.state.status === 'analyzing');
	const progress = $derived(workflow.state.analysisProgress);
	const locationName = $derived(workflow.state.locationName);

	// Redirect if not authenticated or no location
	onMount(() => {
		if (!$isAuthenticated) {
			goto('/');
			return;
		}
		
		// If no location selected, redirect to location page
		if (!workflow.state.locationId) {
			goto('/location');
			return;
		}

		// If we're in reviewing state (analysis finished while away), redirect to review
		if (workflow.state.status === 'reviewing') {
			goto('/review');
			return;
		}
	});

	// Watch for workflow errors
	$effect(() => {
		if (workflow.state.error) {
			showToast(workflow.state.error, 'error');
			workflow.clearError();
		}
	});

	// Watch for status changes to navigate
	$effect(() => {
		if (workflow.state.status === 'reviewing') {
			showToast(`Detected ${workflow.state.detectedItems.length} item(s)`, 'success');
			goto('/review');
		}
	});

	// ==========================================================================
	// FILE HANDLING
	// ==========================================================================

	function handleFileSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;

		for (const file of Array.from(input.files)) {
			if (images.length >= MAX_IMAGES) {
				showToast(`Maximum ${MAX_IMAGES} images allowed`, 'warning');
				break;
			}

			if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
				showToast(`File ${file.name} is too large (max ${MAX_FILE_SIZE_MB}MB)`, 'warning');
				continue;
			}

			const reader = new FileReader();
			reader.onload = (e) => {
				const dataUrl = e.target?.result as string;
				workflow.addImage({
					file,
					dataUrl,
					separateItems: false,
					extraInstructions: '',
				});
			};
			reader.readAsDataURL(file);
		}

		input.value = '';
	}

	function handleAdditionalImageSelect(imageIndex: number, e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;

		const newFiles: File[] = [];
		const newDataUrls: string[] = [];
		let processedCount = 0;
		const totalFiles = input.files.length;

		for (const file of Array.from(input.files)) {
			if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
				showToast(`File ${file.name} is too large (max ${MAX_FILE_SIZE_MB}MB)`, 'warning');
				processedCount++;
				continue;
			}

			const reader = new FileReader();
			reader.onload = (e) => {
				const dataUrl = e.target?.result as string;
				newFiles.push(file);
				newDataUrls.push(dataUrl);
				processedCount++;

				if (processedCount === totalFiles && newFiles.length > 0) {
					workflow.addAdditionalImages(imageIndex, newFiles, newDataUrls);
				}
			};
			reader.readAsDataURL(file);
		}

		input.value = '';
	}

	// ==========================================================================
	// IMAGE ACTIONS
	// ==========================================================================

	function toggleImageExpanded(index: number) {
		expandedImages = new Set(expandedImages);
		if (expandedImages.has(index)) {
			expandedImages.delete(index);
		} else {
			expandedImages.add(index);
		}
	}

	function removeImage(index: number) {
		workflow.removeImage(index);
		expandedImages = new Set(
			[...expandedImages]
				.filter(i => i !== index)
				.map(i => i > index ? i - 1 : i)
		);
	}

	function clearAll() {
		workflow.clearImages();
		expandedImages = new Set();
	}

	function updateImageOption(index: number, field: 'separateItems' | 'extraInstructions', value: boolean | string) {
		workflow.updateImageOptions(index, { [field]: value });
	}

	function removeAdditionalImage(imageIndex: number, additionalIndex: number) {
		workflow.removeAdditionalImage(imageIndex, additionalIndex);
	}

	// ==========================================================================
	// HELPERS
	// ==========================================================================

	function formatFileSize(bytes: number): string {
		if (bytes < 1024) return bytes + ' B';
		if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
		return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
	}

	function goBack() {
		goto('/location');
	}

	// ==========================================================================
	// ANALYSIS - delegate to workflow
	// ==========================================================================

	function startAnalysis() {
		workflow.startAnalysis();
	}

	function cancelAnalysis() {
		workflow.cancelAnalysis();
	}
</script>

<svelte:head>
	<title>Capture Items - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	<BackLink href="/location" label="Change Location" onclick={goBack} />

	<StepIndicator currentStep={2} />

	<h2 class="text-2xl font-bold text-text mb-2">Capture Items</h2>
	<p class="text-text-muted mb-6">Add photos and configure detection options for each</p>

	<!-- Image list with collapsible cards -->
	{#if images.length > 0}
		<div class="space-y-3 mb-4">
			{#each images as image, index}
				<div class="bg-surface rounded-xl border border-border overflow-hidden">
					<!-- Header (always visible) -->
					<div class="flex items-center gap-3 p-3">
						<!-- Thumbnail -->
						<div class="w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden bg-surface-elevated relative">
							<img
								src={image.dataUrl}
								alt="Captured {index + 1}"
								class="w-full h-full object-cover"
							/>
							<div class="absolute bottom-0.5 right-0.5 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
								{index + 1}
							</div>
						</div>

						<!-- File info -->
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2">
								<p class="text-sm font-medium text-text truncate">{image.file.name}</p>
								{#if image.additionalFiles && image.additionalFiles.length > 0}
									<span class="px-1.5 py-0.5 bg-primary/20 text-primary-light rounded text-xs">
										+{image.additionalFiles.length}
									</span>
								{/if}
							</div>
							<p class="text-xs text-text-muted">{formatFileSize(image.file.size)}</p>
						</div>

						<!-- Action buttons -->
						<div class="flex items-center gap-1">
							<button
								type="button"
								class="p-2 text-text-muted hover:text-text transition-colors"
								aria-label={expandedImages.has(index) ? 'Collapse options' : 'Expand options'}
								onclick={() => toggleImageExpanded(index)}
								disabled={isAnalyzing}
							>
								<svg 
									class="w-5 h-5 transition-transform {expandedImages.has(index) ? 'rotate-180' : ''}" 
									fill="none" 
									stroke="currentColor" 
									viewBox="0 0 24 24"
								>
									<polyline points="18 15 12 9 6 15" />
								</svg>
							</button>
							<button
								type="button"
								class="p-2 text-text-muted hover:text-danger transition-colors"
								aria-label="Remove image"
								onclick={() => removeImage(index)}
								disabled={isAnalyzing}
							>
								<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<line x1="18" y1="6" x2="6" y2="18" />
									<line x1="6" y1="6" x2="18" y2="18" />
								</svg>
							</button>
						</div>
					</div>

					<!-- Expandable options -->
					{#if expandedImages.has(index)}
						<div class="px-3 pb-3 pt-0 space-y-3 border-t border-border/50 mt-0">
							<!-- Separate into multiple items toggle -->
							<label class="flex items-center gap-3 pt-3 cursor-pointer">
								<div class="relative">
									<input
										type="checkbox"
										checked={image.separateItems}
										onchange={(e) => updateImageOption(index, 'separateItems', (e.target as HTMLInputElement).checked)}
										class="sr-only peer"
										disabled={isAnalyzing}
									/>
									<div class="w-10 h-6 bg-surface-elevated rounded-full peer-checked:bg-primary transition-colors"></div>
									<div class="absolute left-1 top-1 w-4 h-4 bg-text-muted rounded-full peer-checked:translate-x-4 peer-checked:bg-white transition-all"></div>
								</div>
								<span class="text-sm text-text">Separate into multiple items</span>
							</label>

							<!-- Optional instructions -->
							<div>
								<input
									type="text"
									placeholder="Optional: describe what's in this photo..."
									value={image.extraInstructions}
									oninput={(e) => updateImageOption(index, 'extraInstructions', (e.target as HTMLInputElement).value)}
									class="w-full px-3 py-2 bg-surface-elevated border border-border rounded-lg text-sm text-text placeholder:text-text-dim focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
									disabled={isAnalyzing}
								/>
							</div>

							<!-- Additional images for this item -->
							<div class="pt-2 border-t border-border/30">
								<div class="flex items-center justify-between mb-2">
									<span class="text-xs text-text-muted">
										Additional photos for this item
										{#if image.additionalFiles && image.additionalFiles.length > 0}
											<span class="text-primary-light">({image.additionalFiles.length})</span>
										{/if}
									</span>
									<button
										type="button"
										class="text-xs text-primary hover:underline"
										onclick={() => additionalImageInputs[index]?.click()}
										disabled={isAnalyzing}
									>
										+ Add photos
									</button>
								</div>
								
								<input
									type="file"
									accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
									multiple
									bind:this={additionalImageInputs[index]}
									onchange={(e) => handleAdditionalImageSelect(index, e)}
									class="hidden"
								/>

								{#if image.additionalDataUrls && image.additionalDataUrls.length > 0}
									<div class="flex flex-wrap gap-2">
										{#each image.additionalDataUrls as additionalUrl, additionalIndex}
											<div class="relative w-12 h-12 rounded-lg overflow-hidden bg-surface-elevated group">
												<img
													src={additionalUrl}
													alt="Additional {additionalIndex + 1}"
													class="w-full h-full object-cover"
												/>
												<button
													type="button"
													class="absolute inset-0 bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
													aria-label="Remove additional image"
													onclick={() => removeAdditionalImage(index, additionalIndex)}
													disabled={isAnalyzing}
												>
													<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<line x1="18" y1="6" x2="6" y2="18" />
														<line x1="6" y1="6" x2="18" y2="18" />
													</svg>
												</button>
											</div>
										{/each}
									</div>
								{:else}
									<p class="text-xs text-text-dim">Add extra angles or close-ups to help AI detect details</p>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			{/each}

			<!-- Capture buttons inside dashed border -->
			{#if images.length < MAX_IMAGES && !isAnalyzing}
				<CaptureButtons 
					onCamera={() => cameraInput.click()} 
					onUpload={() => fileInput.click()} 
				/>
			{/if}
		</div>

		<div class="flex items-center justify-between mb-6 text-sm">
			<span class="text-text-muted">{images.length} item{images.length !== 1 ? 's' : ''} selected</span>
			{#if !isAnalyzing}
				<button
					type="button"
					class="text-danger hover:underline"
					onclick={clearAll}
				>
					Clear all
				</button>
			{/if}
		</div>
	{:else}
		<!-- Empty state - same capture buttons -->
		<div class="mb-6">
			<CaptureButtons 
				onCamera={() => cameraInput.click()} 
				onUpload={() => fileInput.click()} 
			/>
		</div>
	{/if}

	<!-- Hidden file inputs -->
	<input
		type="file"
		accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
		multiple
		bind:this={fileInput}
		onchange={handleFileSelect}
		class="hidden"
	/>
	<input
		type="file"
		accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
		capture="environment"
		bind:this={cameraInput}
		onchange={handleFileSelect}
		class="hidden"
	/>

	<!-- Analysis progress -->
	{#if isAnalyzing && progress}
		<div class="bg-surface rounded-xl border border-border p-4 mb-6">
			<div class="flex items-center justify-between mb-2">
				<span class="text-sm font-medium text-text">{progress.message || 'Analyzing...'}</span>
				<span class="text-sm text-text-muted">{progress.current} / {progress.total}</span>
			</div>
			<div class="h-2 bg-surface-elevated rounded-full overflow-hidden">
				<div
					class="h-full bg-primary transition-all duration-300"
					style="width: {progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%"
				></div>
			</div>
			<button
				type="button"
				class="mt-3 w-full py-2 text-sm text-text-muted hover:text-danger transition-colors"
				onclick={cancelAnalysis}
			>
				Cancel
			</button>
		</div>
	{/if}

	{#if !isAnalyzing}
		<Button
			variant="primary"
			full
			disabled={images.length === 0}
			onclick={startAnalysis}
		>
			<span>Analyze with AI</span>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<circle cx="11" cy="11" r="8" />
				<path d="m21 21-4.35-4.35" />
			</svg>
		</Button>
	{/if}
</div>
