<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { vision, type DetectedItem } from '$lib/api';
	import { isAuthenticated } from '$lib/stores/auth';
	import { selectedLocation, selectedLocationPath } from '$lib/stores/locations';
	import {
		capturedImages,
		detectedItems,
		currentItemIndex,
		addCapturedImage,
		removeCapturedImage,
		clearCapturedImages,
		type CapturedImage,
		type ReviewItem,
	} from '$lib/stores/items';
	import { showToast, setLoading } from '$lib/stores/ui';
	import Button from '$lib/components/Button.svelte';
	import Loader from '$lib/components/Loader.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';

	const MAX_IMAGES = 10;
	const MAX_FILE_SIZE_MB = 10;

	let fileInput: HTMLInputElement;
	let cameraInput: HTMLInputElement;
	let isAnalyzing = $state(false);
	let analysisProgress = $state({ current: 0, total: 0, status: '' });
	
	// Track which images are expanded (collapsed by default after adding)
	let expandedImages = $state<Set<number>>(new Set());

	// Redirect if not authenticated or no location selected
	onMount(() => {
		if (!$isAuthenticated) {
			goto('/');
			return;
		}
		if (!$selectedLocation) {
			goto('/location');
			return;
		}
	});

	function toggleImageExpanded(index: number) {
		expandedImages = new Set(expandedImages);
		if (expandedImages.has(index)) {
			expandedImages.delete(index);
		} else {
			expandedImages.add(index);
		}
	}

	function handleFileSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;

		const startIndex = $capturedImages.length;

		for (const file of Array.from(input.files)) {
			if ($capturedImages.length >= MAX_IMAGES) {
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
				addCapturedImage({
					file,
					dataUrl,
					separateItems: false,
					extraInstructions: '',
				});
				// Images are collapsed by default (not added to expandedImages)
			};
			reader.readAsDataURL(file);
		}

		// Reset input
		input.value = '';
	}

	function removeImage(index: number) {
		removeCapturedImage(index);
		// Adjust expanded indices
		expandedImages = new Set(
			[...expandedImages]
				.filter(i => i !== index)
				.map(i => i > index ? i - 1 : i)
		);
	}

	function clearAll() {
		clearCapturedImages();
		expandedImages = new Set();
	}

	function updateImageOption(index: number, field: 'separateItems' | 'extraInstructions', value: boolean | string) {
		capturedImages.update(images => {
			const updated = [...images];
			updated[index] = { ...updated[index], [field]: value };
			return updated;
		});
	}

	// Track which image is receiving additional files
	let additionalImageInputs: { [key: number]: HTMLInputElement } = {};

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

				// When all files are processed, update the store
				if (processedCount === totalFiles) {
					capturedImages.update(images => {
						const updated = [...images];
						const current = updated[imageIndex];
						updated[imageIndex] = {
							...current,
							additionalFiles: [...(current.additionalFiles || []), ...newFiles],
							additionalDataUrls: [...(current.additionalDataUrls || []), ...newDataUrls],
						};
						return updated;
					});
				}
			};
			reader.readAsDataURL(file);
		}

		input.value = '';
	}

	function removeAdditionalImage(imageIndex: number, additionalIndex: number) {
		capturedImages.update(images => {
			const updated = [...images];
			const current = updated[imageIndex];
			updated[imageIndex] = {
				...current,
				additionalFiles: current.additionalFiles?.filter((_, i) => i !== additionalIndex),
				additionalDataUrls: current.additionalDataUrls?.filter((_, i) => i !== additionalIndex),
			};
			return updated;
		});
	}

	function formatFileSize(bytes: number): string {
		if (bytes < 1024) return bytes + ' B';
		if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
		return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
	}

	async function analyzeImages() {
		if ($capturedImages.length === 0) {
			showToast('Please add at least one image', 'warning');
			return;
		}

		isAnalyzing = true;
		analysisProgress = { current: 0, total: $capturedImages.length, status: 'Starting analysis...' };

		const allDetectedItems: ReviewItem[] = [];

		try {
			for (let i = 0; i < $capturedImages.length; i++) {
				const image = $capturedImages[i];
				analysisProgress = {
					current: i,
					total: $capturedImages.length,
					status: `Analyzing item ${i + 1} of ${$capturedImages.length}...`,
				};

				const response = await vision.detect(image.file, {
					singleItem: !image.separateItems, // Note: separateItems=true means multiple items
					extraInstructions: image.extraInstructions || undefined,
					extractExtendedFields: true,
					additionalImages: image.additionalFiles,
				});

				// Add source image info to each detected item
				for (const item of response.items) {
					allDetectedItems.push({
						...item,
						sourceImageIndex: i,
						originalFile: image.file,
						additionalImages: image.additionalFiles || [],
					});
				}
			}

			if (allDetectedItems.length === 0) {
				showToast('No items detected in the images', 'warning');
				isAnalyzing = false;
				return;
			}

			// Store detected items and navigate to review
			detectedItems.set(allDetectedItems);
			currentItemIndex.set(0);
			showToast(`Detected ${allDetectedItems.length} item(s)`, 'success');
			goto('/review');
		} catch (error) {
			console.error('Analysis failed:', error);
			showToast(
				error instanceof Error ? error.message : 'Analysis failed. Please try again.',
				'error'
			);
		} finally {
			isAnalyzing = false;
		}
	}

	function goBack() {
		goto('/location');
	}
</script>

<svelte:head>
	<title>Capture Items - Homebox Companion</title>
</svelte:head>

<div class="animate-in">
	<button
		type="button"
		class="flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4 transition-colors"
		onclick={goBack}
	>
		<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<polyline points="15 18 9 12 15 6" />
		</svg>
		<span>Change Location</span>
	</button>

	<StepIndicator currentStep={2} />

	<h2 class="text-2xl font-bold text-text mb-2">Capture Items</h2>
	<p class="text-text-muted mb-6">Add photos and configure detection options for each</p>

	<!-- Image list with collapsible cards -->
	{#if $capturedImages.length > 0}
		<div class="space-y-3 mb-4">
			{#each $capturedImages as image, index}
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

			<!-- Add more button -->
			{#if $capturedImages.length < MAX_IMAGES}
				<button
					type="button"
					class="w-full p-4 rounded-xl border-2 border-dashed border-border hover:border-primary/50 flex items-center justify-center gap-2 text-text-muted hover:text-text transition-colors"
					onclick={() => fileInput.click()}
				>
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<line x1="12" y1="5" x2="12" y2="19" />
						<line x1="5" y1="12" x2="19" y2="12" />
					</svg>
					<span>Add more photos</span>
				</button>
			{/if}
		</div>

		<div class="flex items-center justify-between mb-6 text-sm">
			<span class="text-text-muted">{$capturedImages.length} photo{$capturedImages.length !== 1 ? 's' : ''} selected</span>
			<button
				type="button"
				class="text-danger hover:underline"
				onclick={clearAll}
			>
				Clear all
			</button>
		</div>
	{:else}
		<!-- Empty state -->
		<button
			type="button"
			class="w-full aspect-video rounded-2xl border-2 border-dashed border-border hover:border-primary/50 flex flex-col items-center justify-center gap-3 text-text-muted hover:text-text transition-colors mb-6"
			onclick={() => fileInput.click()}
		>
			<svg class="w-16 h-16 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
				<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
				<circle cx="12" cy="13" r="4" />
			</svg>
			<p>Tap to capture or upload photos</p>
			<span class="text-xs text-text-dim">You can select multiple photos at once</span>
		</button>
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

	<!-- Action buttons -->
	<div class="flex gap-3 mb-6">
		<Button variant="secondary" onclick={() => cameraInput.click()}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
				<circle cx="12" cy="13" r="4" />
			</svg>
			<span>Camera</span>
		</Button>
		<Button variant="secondary" onclick={() => fileInput.click()}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
				<polyline points="17 8 12 3 7 8" />
				<line x1="12" y1="3" x2="12" y2="15" />
			</svg>
			<span>Upload</span>
		</Button>
	</div>

	<!-- Analysis progress -->
	{#if isAnalyzing}
		<div class="bg-surface rounded-xl border border-border p-4 mb-6">
			<div class="flex items-center justify-between mb-2">
				<span class="text-sm font-medium text-text">Analyzing photos...</span>
				<span class="text-sm text-text-muted">{analysisProgress.current} / {analysisProgress.total}</span>
			</div>
			<div class="h-2 bg-surface-elevated rounded-full overflow-hidden">
				<div
					class="h-full bg-primary transition-all duration-300"
					style="width: {(analysisProgress.current / analysisProgress.total) * 100}%"
				></div>
			</div>
			<p class="text-sm text-text-muted mt-2">{analysisProgress.status}</p>
		</div>
	{/if}

	<Button
		variant="primary"
		full
		disabled={$capturedImages.length === 0 || isAnalyzing}
		loading={isAnalyzing}
		onclick={analyzeImages}
	>
		<span>Analyze with AI</span>
		<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<circle cx="11" cy="11" r="8" />
			<path d="m21 21-4.35-4.35" />
		</svg>
	</Button>
</div>
