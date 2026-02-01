<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { slide } from 'svelte/transition';
	import { resetLocationState } from '$lib/stores/locations.svelte';
	import { showToast } from '$lib/stores/ui.svelte';
	import { markSessionExpired } from '$lib/stores/auth.svelte';
	import { scanWorkflow } from '$lib/workflows/scan.svelte';
	import { hasToken } from '$lib/utils/token';
	import { routeGuards } from '$lib/utils/routeGuard';
	import { getInitPromise } from '$lib/services/tokenRefresh';
	import { createLogger } from '$lib/utils/logger';
	import { getConfig } from '$lib/api/settings';
	import Button from '$lib/components/Button.svelte';
	import AppContainer from '$lib/components/AppContainer.svelte';
	import StepIndicator from '$lib/components/StepIndicator.svelte';
	import BackLink from '$lib/components/BackLink.svelte';
	import AnalysisProgressBar from '$lib/components/AnalysisProgressBar.svelte';
	import StatusIcon from '$lib/components/StatusIcon.svelte';
	import { AssetIdInput } from '$lib/components/form';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import {
		TriangleAlert,
		RefreshCw,
		ChevronRight,
		Trash2,
		ChevronDown,
		X,
		Camera,
		Upload,
		Image,
		MapPin,
		Lightbulb,
	} from 'lucide-svelte';

	const log = createLogger({ prefix: 'Capture' });

	// Capture limits (loaded from config, with safe defaults)
	let maxImages = $state(30);
	let maxFileSizeMb = $state(10);

	let fileInput: HTMLInputElement;
	let cameraInput: HTMLInputElement;

	// Local UI state (not workflow state)
	let expandedImages = new SvelteSet<number>();
	let additionalImageInputs: { [key: number]: HTMLInputElement } = {};
	let additionalCameraInputs: { [key: number]: HTMLInputElement } = {};
	let analysisAnimationComplete = $state(false);
	let isStartingAnalysis = $state(false);

	// Track object URLs for cleanup (prevents memory leaks)
	// Note: We only revoke URLs when images are explicitly removed, NOT on component
	// destroy. This is because the workflow state persists across navigation, and
	// we need the URLs to remain valid if the user navigates back to this page.
	// The browser automatically cleans up Object URLs when the page/tab is closed.
	// eslint-disable-next-line svelte/prefer-svelte-reactivity -- Internal tracking, not reactive state
	const createdObjectUrls = new Set<string>();

	/** Create an object URL and track it for cleanup */
	function createTrackedObjectUrl(file: File): string {
		const url = URL.createObjectURL(file);
		createdObjectUrls.add(url);
		return url;
	}

	/** Revoke an object URL and remove from tracking */
	function revokeObjectUrl(url: string): void {
		// Only revoke if we created this URL (it's in our tracking set)
		// This handles the case where user navigates back and URLs were
		// created in a previous component instance
		if (createdObjectUrls.has(url)) {
			URL.revokeObjectURL(url);
			createdObjectUrls.delete(url);
			log.debug(`Revoked object URL (${createdObjectUrls.size} remaining)`);
		} else {
			// URL was created by a previous component instance - still try to revoke
			// to free memory, but don't log errors since this is expected behavior
			try {
				URL.revokeObjectURL(url);
			} catch {
				// Ignore - URL may have already been revoked or is invalid
			}
		}
	}

	// Get workflow state for reading
	const workflow = scanWorkflow;

	// Derived values from workflow state
	// Using getter pattern to ensure reactivity with class-based $state
	let images = $derived(workflow.state.images);
	let status = $derived(workflow.state.status);
	let isAnalyzing = $derived(status === 'analyzing');
	let progress = $derived(workflow.state.analysisProgress);
	let imageStatuses = $derived(workflow.state.imageStatuses);
	let locationPath = $derived(workflow.state.locationPath);
	let parentItemName = $derived(workflow.state.parentItemName);

	// Analysis status counts (computed once for efficiency)
	let failedImageCount = $derived(
		Object.values(imageStatuses).filter((s) => s === 'failed').length
	);
	let succeededImageCount = $derived(
		Object.values(imageStatuses).filter((s) => s === 'success').length
	);
	let detectedItemCount = $derived(workflow.state.detectedItems.length);

	// Total image count including additional images (for limit enforcement)
	let totalImageCount = $derived(
		images.reduce((count, img) => count + 1 + (img.additionalFiles?.length || 0), 0)
	);

	// True while analyzing OR while the completion animation is playing
	// This prevents UI elements from appearing/disappearing during animation
	let showAnalyzingUI = $derived(
		isAnalyzing || (status === 'reviewing' && !analysisAnimationComplete)
	);

	// Cleanup orphaned Object URLs when workflow is reset (images array becomes empty)
	// This handles cases like workflow.startNew() or workflow.reset()
	let previousImageCount = 0;
	$effect(() => {
		const currentCount = images.length;
		// If images were cleared (went to 0 from non-zero), revoke all tracked URLs
		if (previousImageCount > 0 && currentCount === 0) {
			log.debug(`Workflow reset detected, revoking ${createdObjectUrls.size} orphaned URLs`);
			for (const url of createdObjectUrls) {
				URL.revokeObjectURL(url);
			}
			createdObjectUrls.clear();
		}
		previousImageCount = currentCount;
	});

	// Apply route guard: requires auth, location, and not in reviewing state
	onMount(async () => {
		// Wait for auth initialization to complete to avoid race conditions
		// where we check isAuthenticated before initializeAuth clears expired tokens
		await getInitPromise();

		if (!routeGuards.capture()) return;

		// Load capture limits from config
		try {
			const config = await getConfig();
			maxImages = config.capture_max_images;
			maxFileSizeMb = config.capture_max_file_size_mb;
		} catch (error) {
			log.warn('Failed to load capture config, using defaults', error);
		}

		// If workflow is complete (just finished submission), reset for a new scan session
		if (workflow.state.status === 'complete') {
			log.info('Workflow complete, resetting for new scan session');
			workflow.startNew();
		}
	});

	// Watch for workflow errors
	$effect(() => {
		if (workflow.state.error) {
			showToast(workflow.state.error, 'error');
			workflow.clearError();
		}
	});

	// Handle analysis animation completion - navigate directly to avoid CaptureButtons appearing
	function handleAnalysisComplete() {
		analysisAnimationComplete = true;
		// Clear progress after animation finishes
		workflow.clearAnalysisProgress();

		// Navigate immediately to prevent UI shift from buttons reappearing
		if (workflow.state.status === 'reviewing') {
			goto(resolve('/review'));
		}
	}

	// ==========================================================================
	// FILE HANDLING
	// ==========================================================================

	/** Check if file exceeds size limit and show toast if so */
	function isFileTooLarge(file: File): boolean {
		if (file.size > maxFileSizeMb * 1024 * 1024) {
			showToast(`File ${file.name} is too large (max ${maxFileSizeMb}MB)`, 'warning');
			return true;
		}
		return false;
	}

	function handleFileSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;

		// Track count locally for limit enforcement
		let currentCount = totalImageCount;

		for (const file of Array.from(input.files)) {
			if (currentCount >= maxImages) {
				showToast(`Maximum ${maxImages} images allowed`, 'warning');
				break;
			}

			if (isFileTooLarge(file)) continue;

			currentCount++;

			// Use Object URL instead of base64 data URL - much more memory efficient
			// Object URLs are tiny strings that reference the File blob in memory
			// instead of duplicating the entire file as a base64 string
			const previewUrl = createTrackedObjectUrl(file);

			workflow.addImage({
				file,
				dataUrl: previewUrl,
				separateItems: false,
				extraInstructions: '',
			});
			// Collapse all expanded accordions when a new image is added
			expandedImages.clear();
		}

		input.value = '';
	}

	function handleAdditionalImageSelect(imageIndex: number, e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files) return;

		const newFiles: File[] = [];
		const newPreviewUrls: string[] = [];

		// Track how many more we can accept
		const remainingSlots = maxImages - totalImageCount;

		for (const file of Array.from(input.files)) {
			// Check total image limit (including additional images)
			if (newFiles.length >= remainingSlots) {
				showToast(`Maximum ${maxImages} images allowed`, 'warning');
				break;
			}

			if (isFileTooLarge(file)) continue;

			// Use Object URL instead of base64 - much more memory efficient
			const previewUrl = createTrackedObjectUrl(file);
			newFiles.push(file);
			newPreviewUrls.push(previewUrl);
		}

		// Add all valid files at once (synchronous, no FileReader needed)
		if (newFiles.length > 0) {
			workflow.addAdditionalImages(imageIndex, newFiles, newPreviewUrls);
		}

		input.value = '';
	}

	/** Handle paste event on the description input to add images from clipboard */
	function handlePaste(imageIndex: number, e: ClipboardEvent) {
		const clipboardData = e.clipboardData;
		if (!clipboardData) return;

		// Check for image files in clipboard
		const imageFiles: File[] = [];
		for (const item of Array.from(clipboardData.items)) {
			if (item.type.startsWith('image/')) {
				const file = item.getAsFile();
				if (file) imageFiles.push(file);
			}
		}

		// If no images found, let the paste proceed normally (for text)
		if (imageFiles.length === 0) return;

		// Prevent default paste behavior since we're handling an image
		e.preventDefault();

		const newFiles: File[] = [];
		const newPreviewUrls: string[] = [];
		const remainingSlots = maxImages - totalImageCount;

		for (const file of imageFiles) {
			if (newFiles.length >= remainingSlots) {
				showToast(`Maximum ${maxImages} images allowed`, 'warning');
				break;
			}

			if (isFileTooLarge(file)) continue;

			const previewUrl = createTrackedObjectUrl(file);
			newFiles.push(file);
			newPreviewUrls.push(previewUrl);
		}

		if (newFiles.length > 0) {
			workflow.addAdditionalImages(imageIndex, newFiles, newPreviewUrls);
			log.info(`Pasted ${newFiles.length} image(s) as additional photos for image ${imageIndex}`);
		}
	}

	// ==========================================================================
	// IMAGE ACTIONS
	// ==========================================================================

	function toggleImageExpanded(index: number) {
		if (expandedImages.has(index)) {
			// Collapse if already expanded
			expandedImages.clear();
		} else {
			// Expand this one and collapse all others
			expandedImages.clear();
			expandedImages.add(index);
		}
	}

	function removeImage(index: number) {
		// Revoke object URLs before removing to free memory
		const imageToRemove = images[index];
		if (imageToRemove) {
			revokeObjectUrl(imageToRemove.dataUrl);
			// Also revoke any additional image URLs
			if (imageToRemove.additionalDataUrls) {
				for (const url of imageToRemove.additionalDataUrls) {
					revokeObjectUrl(url);
				}
			}
		}

		workflow.removeImage(index);
		// Update expanded indices: remove this index and shift higher indices down
		const updated = [...expandedImages]
			.filter((i) => i !== index)
			.map((i) => (i > index ? i - 1 : i));
		expandedImages.clear();
		updated.forEach((i) => expandedImages.add(i));
	}

	function updateImageOption(
		index: number,
		field: 'separateItems' | 'extraInstructions' | 'assetId',
		value: boolean | string | null
	) {
		workflow.updateImageOptions(index, { [field]: value });
	}

	function removeAdditionalImage(imageIndex: number, additionalIndex: number) {
		// Revoke object URL before removing to free memory
		const image = images[imageIndex];
		if (image?.additionalDataUrls?.[additionalIndex]) {
			revokeObjectUrl(image.additionalDataUrls[additionalIndex]);
		}

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
		resetLocationState();
		workflow.clearLocation();
		goto(resolve('/location'));
	}

	// ==========================================================================
	// ANALYSIS - delegate to workflow
	// ==========================================================================

	async function startAnalysis() {
		// Entry logging
		log.info('Analyze button clicked');

		// Prevent double-clicks
		if (isStartingAnalysis || isAnalyzing) {
			log.debug('Analysis already starting or in progress, ignoring click');
			return;
		}

		isStartingAnalysis = true;
		log.debug('Starting analysis flow...');

		try {
			// Check token validity before starting analysis
			log.debug('Checking authentication...');
			if (!hasToken()) {
				// Token missing - trigger re-auth modal
				log.warn('Auth check failed, marking session expired');
				markSessionExpired();
				return;
			}
			log.debug('Auth check passed');

			// Before workflow call
			log.info(`Starting workflow analysis for ${workflow.state.images.length} image(s)`);
			analysisAnimationComplete = false;
			// Collapse all expanded cards when analysis starts
			expandedImages.clear();
			// Scroll to top of app after analysis starts
			setTimeout(() => {
				window.scrollTo({ top: 0, behavior: 'smooth' });
			}, 100);
			await workflow.startAnalysis();
			log.debug('Workflow.startAnalysis() completed');
		} catch (error) {
			// Error logging
			log.error('Analysis failed with exception', error);
			throw error;
		} finally {
			isStartingAnalysis = false;
		}
	}

	function cancelAnalysis() {
		workflow.cancelAnalysis();
		// Reset the starting flag in case cancel happened during startup
		isStartingAnalysis = false;
	}
</script>

<svelte:head>
	<title>Capture Items - Homebox Companion</title>
</svelte:head>

<div class="animate-in pb-28">
	<StepIndicator currentStep={2} />

	<h2 class="mb-1 text-h2 text-neutral-100">Capture Items</h2>
	<p class="mb-6 text-body-sm text-neutral-400">Add photos and configure detection options</p>

	<!-- Current location display -->
	{#if locationPath}
		<BackLink href="/location" label="Change Location" onclick={goBack} disabled={isAnalyzing} />

		<div class="mb-3 mt-2 flex flex-col gap-2 text-body-sm text-neutral-400">
			<!-- Location block -->
			<div class="flex flex-col gap-1">
				<div class="flex items-center gap-2">
					<MapPin class="shrink-0" size={16} strokeWidth={1.5} />
					<span>Items will be added to:</span>
				</div>
				<span class="pl-6 font-semibold text-neutral-200">{locationPath}</span>
			</div>

			<!-- Parent item block (if present) -->
			{#if parentItemName}
				<div class="flex items-center gap-2 pl-6 sm:pl-0">
					<span class="text-neutral-500">Inside:</span>
					<span class="font-semibold text-primary-400">{parentItemName}</span>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Analysis progress bar (above images for context) -->
	{#if progress && showAnalyzingUI}
		<div class="mb-4">
			<AnalysisProgressBar
				current={progress.current}
				total={progress.total}
				message={status === 'reviewing' ? 'Analysis complete!' : progress.message || 'Analyzing...'}
				onComplete={handleAnalysisComplete}
			/>
		</div>
	{/if}

	<!-- Partial failure panel (when some images failed analysis) -->
	{#if status === 'partial_analysis'}
		<div
			class="mb-4 rounded-xl border border-warning-500/30 bg-warning-500/10 p-4"
			transition:slide={{ duration: 200 }}
		>
			<div class="mb-4 flex items-start gap-3">
				<!-- Warning icon -->
				<TriangleAlert class="mt-0.5 shrink-0 text-warning-400" size={24} strokeWidth={1.5} />

				<div class="flex-1">
					<h3 class="mb-1 text-body font-semibold text-warning-100">
						Some Images Failed to Analyze
					</h3>
					<p class="mb-3 text-body-sm text-warning-200/80">
						{failedImageCount} of {images.length} image(s) could not be processed. You can retry the failed
						images, continue with the successful ones, or remove the failed images.
					</p>

					<!-- Stats -->
					<div class="mb-4 flex gap-4 text-caption">
						<div class="flex items-center gap-1.5">
							<div class="bg-success-400 h-2 w-2 rounded-full"></div>
							<span class="text-neutral-300">{succeededImageCount} succeeded</span>
						</div>
						<div class="flex items-center gap-1.5">
							<div class="bg-error-400 h-2 w-2 rounded-full"></div>
							<span class="text-neutral-300">{failedImageCount} failed</span>
						</div>
						<div class="flex items-center gap-1.5">
							<div class="h-2 w-2 rounded-full bg-primary-400"></div>
							<span class="text-neutral-300">{detectedItemCount} items detected</span>
						</div>
					</div>

					<!-- Action buttons -->
					<div class="flex flex-col gap-2 sm:flex-row">
						<Button
							variant="warning"
							onclick={async () => {
								// Reset animation flag so progress bar works correctly
								analysisAnimationComplete = false;
								await workflow.retryFailedAnalysis();
							}}
							disabled={isStartingAnalysis}
						>
							<RefreshCw size={16} strokeWidth={1.5} />
							<span>Retry Failed Images</span>
						</Button>
						<Button
							variant="primary"
							onclick={() => {
								workflow.continueWithSuccessful();
								goto(resolve('/review'));
							}}
							disabled={isStartingAnalysis}
						>
							<span>Continue with Successful</span>
							<ChevronRight size={16} strokeWidth={1.5} />
						</Button>
						<Button
							variant="secondary"
							onclick={() => {
								workflow.removeFailedImages();
								goto(resolve('/review'));
							}}
							disabled={isStartingAnalysis}
						>
							<Trash2 size={16} strokeWidth={1.5} />
							<span>Remove Failed</span>
						</Button>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<!-- Image list with collapsible cards -->
	{#if images.length > 0}
		<div class="mb-4 space-y-3">
			{#each images as image, index (image.dataUrl)}
				<div
					class="overflow-hidden rounded-xl border border-neutral-700 bg-neutral-900 shadow-sm transition-all hover:border-neutral-600"
				>
					<!-- Header (always visible) -->
					<div class="flex items-center gap-3 p-3">
						<!-- Thumbnail -->
						<div class="relative h-16 w-16 flex-shrink-0 overflow-hidden rounded-lg bg-neutral-800">
							<img
								src={image.dataUrl}
								alt="Captured {index + 1}"
								class="h-full w-full object-cover"
							/>
							<div
								class="absolute bottom-0.5 right-0.5 rounded bg-black/70 px-1.5 py-0.5 text-xs font-medium text-white"
							>
								{index + 1}
							</div>
						</div>

						<!-- File info -->
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<p class="truncate text-body-sm font-medium text-neutral-200">
									{image.file.name}
								</p>
								{#if image.additionalFiles && image.additionalFiles.length > 0}
									<span
										class="rounded bg-primary-500/20 px-1.5 py-0.5 text-caption font-medium text-primary-300"
									>
										+{image.additionalFiles.length}
									</span>
								{/if}
							</div>
							<p class="text-caption text-neutral-500">
								{formatFileSize(image.file.size)}
							</p>
						</div>

						<!-- Action buttons / status -->
						<div class="flex items-center gap-1">
							{#if showAnalyzingUI && imageStatuses[index]}
								<!-- Show status icon during analysis -->
								<StatusIcon status={imageStatuses[index]} size="sm" />
							{:else}
								<button
									type="button"
									class="rounded-lg p-2 text-neutral-400 transition-colors hover:bg-neutral-800 hover:text-neutral-200"
									aria-label={expandedImages.has(index) ? 'Collapse options' : 'Expand options'}
									onclick={() => toggleImageExpanded(index)}
									disabled={isAnalyzing}
								>
									<ChevronDown
										class="transition-transform duration-200 {expandedImages.has(index)
											? 'rotate-180'
											: ''}"
										size={20}
										strokeWidth={1.5}
									/>
								</button>
								<button
									type="button"
									class="hover:text-error-400 rounded-lg p-2 text-neutral-400 transition-colors hover:bg-error-500/10"
									aria-label="Remove image"
									onclick={() => removeImage(index)}
									disabled={isAnalyzing}
								>
									<X size={20} strokeWidth={1.5} />
								</button>
							{/if}
						</div>
					</div>

					<!-- Expandable options -->
					{#if expandedImages.has(index)}
						<div
							class="mt-0 space-y-3 border-t border-neutral-800 px-3 pb-3 pt-0"
							transition:slide={{ duration: 200 }}
						>
							<!-- Separate into multiple items toggle -->
							<label class="flex cursor-pointer items-center gap-3 pt-3">
								<div class="relative">
									<input
										type="checkbox"
										checked={image.separateItems}
										onchange={(e) =>
											updateImageOption(
												index,
												'separateItems',
												(e.target as HTMLInputElement).checked
											)}
										class="peer sr-only"
										disabled={isAnalyzing}
									/>
									<div
										class="h-6 w-10 rounded-full bg-neutral-700 transition-colors peer-checked:bg-primary-600"
									></div>
									<div
										class="absolute left-1 top-1 h-4 w-4 rounded-full bg-neutral-400 transition-all peer-checked:translate-x-4 peer-checked:bg-white"
									></div>
								</div>
								<span class="text-body-sm text-neutral-200">Separate into multiple items</span>
							</label>

							<!-- Asset ID input (for pre-printed QR codes) -->
							{#if !image.separateItems}
								<AssetIdInput
									value={image.assetId ?? null}
									conflict={null}
									disabled={isAnalyzing}
									onChange={(value) => updateImageOption(index, 'assetId', value)}
								/>
							{/if}

							<!-- Optional instructions -->
							<div class="flex items-center gap-2">
								<input
									type="text"
									placeholder="Optional: describe what's in this photo..."
									value={image.extraInstructions}
									oninput={(e) =>
										updateImageOption(
											index,
											'extraInstructions',
											(e.target as HTMLInputElement).value
										)}
									onpaste={(e) => handlePaste(index, e)}
									class="input flex-1 text-body-sm"
									disabled={isAnalyzing}
								/>
								<InfoTooltip text="You can paste images here to add them as additional photos" />
							</div>

							<!-- Additional images for this item -->
							<input
								type="file"
								accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
								multiple
								bind:this={additionalImageInputs[index]}
								onchange={(e) => handleAdditionalImageSelect(index, e)}
								class="hidden"
							/>
							<input
								type="file"
								accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
								capture="environment"
								multiple
								bind:this={additionalCameraInputs[index]}
								onchange={(e) => handleAdditionalImageSelect(index, e)}
								class="hidden"
							/>

							{#if image.additionalDataUrls && image.additionalDataUrls.length > 0}
								<!-- Has additional photos: show gallery strip -->
								<div class="border-t border-neutral-800/50 pt-3">
									<div class="mb-3 flex items-center gap-2">
										<Image class="text-primary-400" size={16} strokeWidth={1.5} />
										<span class="text-body-sm font-medium text-neutral-200">
											{image.additionalDataUrls.length} additional photo{image.additionalDataUrls
												.length !== 1
												? 's'
												: ''}
										</span>
									</div>

									<!-- Thumbnail gallery -->
									<div class="scrollbar-thin -mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
										{#each image.additionalDataUrls as additionalUrl (additionalUrl)}
											{@const additionalIndex = image.additionalDataUrls.indexOf(additionalUrl)}
											<div
												class="group relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl bg-neutral-800 ring-1 ring-neutral-700"
											>
												<img
													src={additionalUrl}
													alt="Additional {additionalIndex + 1}"
													class="h-full w-full object-cover"
												/>
												<button
													type="button"
													class="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-black/70 opacity-0 transition-all hover:bg-error-600 group-hover:opacity-100"
													aria-label="Remove additional image"
													onclick={() => removeAdditionalImage(index, additionalIndex)}
													disabled={isAnalyzing}
												>
													<X class="text-white" size={14} strokeWidth={2.5} />
												</button>
												<div
													class="absolute bottom-1 left-1 rounded bg-black/70 px-1.5 py-0.5 text-xxs font-medium text-white"
												>
													{additionalIndex + 1}
												</div>
											</div>
										{/each}
									</div>

									<!-- Add more buttons below gallery -->
									<div class="mt-3 flex gap-2">
										<button
											type="button"
											class="flex flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-600 px-3 py-2.5 transition-all hover:border-primary-500/50 hover:bg-primary-500/5"
											onclick={() => additionalCameraInputs[index]?.click()}
											disabled={isAnalyzing}
										>
											<Camera class="text-neutral-400" size={16} strokeWidth={1.5} />
											<span class="text-caption font-medium text-neutral-400">Camera</span>
										</button>
										<button
											type="button"
											class="flex flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-600 px-3 py-2.5 transition-all hover:border-primary-500/50 hover:bg-primary-500/5"
											onclick={() => additionalImageInputs[index]?.click()}
											disabled={isAnalyzing}
										>
											<Upload class="text-neutral-400" size={16} strokeWidth={1.5} />
											<span class="text-caption font-medium text-neutral-400">Upload</span>
										</button>
									</div>
								</div>
							{:else}
								<!-- Empty state: compact add buttons (same style as when photos exist) -->
								<div class="border-t border-neutral-800/50 pt-3">
									<p class="mb-2 text-caption text-neutral-500">
										Add close-ups, labels, serial numbers, different angles
									</p>
									<div class="flex gap-2">
										<button
											type="button"
											class="flex flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-600 px-3 py-2.5 transition-all hover:border-primary-500/50 hover:bg-primary-500/5"
											onclick={() => additionalCameraInputs[index]?.click()}
											disabled={isAnalyzing}
										>
											<Camera class="text-neutral-400" size={16} strokeWidth={1.5} />
											<span class="text-caption font-medium text-neutral-400">Camera</span>
										</button>
										<button
											type="button"
											class="flex flex-1 items-center justify-center gap-2 rounded-lg border border-dashed border-neutral-600 px-3 py-2.5 transition-all hover:border-primary-500/50 hover:bg-primary-500/5"
											onclick={() => additionalImageInputs[index]?.click()}
											disabled={isAnalyzing}
										>
											<Upload class="text-neutral-400" size={16} strokeWidth={1.5} />
											<span class="text-caption font-medium text-neutral-400">Upload</span>
										</button>
									</div>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}

			<!-- Add more images button -->
			{#if totalImageCount < maxImages && !showAnalyzingUI}
				<div class="flex gap-3">
					<button
						type="button"
						class="group flex-1 rounded-xl border border-dashed border-neutral-600 p-4 transition-all hover:border-primary-500/50 hover:bg-primary-500/5"
						onclick={() => cameraInput.click()}
					>
						<div class="flex flex-col items-center gap-2">
							<div
								class="flex h-12 w-12 items-center justify-center rounded-xl bg-neutral-800 transition-colors group-hover:bg-primary-500/10"
							>
								<Camera
									class="text-neutral-400 transition-colors group-hover:text-primary-400"
									size={24}
									strokeWidth={1.5}
								/>
							</div>
							<span
								class="text-body-sm font-medium text-neutral-400 transition-colors group-hover:text-primary-400"
								>Camera</span
							>
						</div>
					</button>
					<button
						type="button"
						class="group flex-1 rounded-xl border border-dashed border-neutral-600 p-4 transition-all hover:border-primary-500/50 hover:bg-primary-500/5"
						onclick={() => fileInput.click()}
					>
						<div class="flex flex-col items-center gap-2">
							<div
								class="flex h-12 w-12 items-center justify-center rounded-xl bg-neutral-800 transition-colors group-hover:bg-primary-500/10"
							>
								<Upload
									class="text-neutral-400 transition-colors group-hover:text-primary-400"
									size={24}
									strokeWidth={1.5}
								/>
							</div>
							<span
								class="text-body-sm font-medium text-neutral-400 transition-colors group-hover:text-primary-400"
								>Upload</span
							>
						</div>
					</button>
				</div>
			{/if}
		</div>
	{:else}
		<!-- Enhanced empty state -->
		<div class="mb-6 flex flex-col items-center px-4 py-12">
			<div class="mb-6 flex h-24 w-24 items-center justify-center rounded-2xl bg-primary-500/10">
				<Camera class="text-primary-400" size={48} strokeWidth={1.5} />
			</div>
			<h3 class="mb-2 text-center text-h3 text-neutral-100">Capture your items</h3>
			<p class="mb-8 max-w-xs text-center text-body-sm text-neutral-400">
				Take photos or upload images of items you want to add to your inventory
			</p>

			<!-- Capture buttons -->
			<div class="flex w-full max-w-sm gap-3">
				<button
					type="button"
					class="group flex-1 rounded-xl border border-neutral-700 bg-neutral-900 p-4 shadow-sm transition-all hover:border-primary-500/50 hover:bg-neutral-800"
					onclick={() => cameraInput.click()}
				>
					<div class="flex flex-col items-center gap-2">
						<div
							class="flex h-12 w-12 items-center justify-center rounded-xl bg-neutral-800 transition-colors group-hover:bg-primary-500/10"
						>
							<Camera
								class="text-neutral-300 transition-colors group-hover:text-primary-400"
								size={24}
								strokeWidth={1.5}
							/>
						</div>
						<span
							class="text-body-sm font-medium text-neutral-200 transition-colors group-hover:text-primary-400"
							>Camera</span
						>
					</div>
				</button>
				<button
					type="button"
					class="group flex-1 rounded-xl border border-neutral-700 bg-neutral-900 p-4 shadow-sm transition-all hover:border-primary-500/50 hover:bg-neutral-800"
					onclick={() => fileInput.click()}
				>
					<div class="flex flex-col items-center gap-2">
						<div
							class="flex h-12 w-12 items-center justify-center rounded-xl bg-neutral-800 transition-colors group-hover:bg-primary-500/10"
						>
							<Upload
								class="text-neutral-300 transition-colors group-hover:text-primary-400"
								size={24}
								strokeWidth={1.5}
							/>
						</div>
						<span
							class="text-body-sm font-medium text-neutral-200 transition-colors group-hover:text-primary-400"
							>Upload</span
						>
					</div>
				</button>
			</div>

			<p class="mt-6 text-caption text-neutral-500">
				{totalImageCount} / {maxImages} images · {maxFileSizeMb}MB per file
			</p>
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
</div>

<!-- Sticky Analyze button at bottom - above navigation bar -->
<div
	class="bottom-nav-offset fixed left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-950/95 p-4 backdrop-blur-lg"
>
	<AppContainer>
		{#if showAnalyzingUI && isAnalyzing}
			<Button variant="secondary" full onclick={cancelAnalysis}>
				<X size={20} strokeWidth={1.5} />
				<span>Cancel Analysis</span>
			</Button>
		{:else if !showAnalyzingUI}
			<Button
				variant="primary"
				full
				disabled={images.length === 0 || isStartingAnalysis}
				onclick={startAnalysis}
			>
				{#if isStartingAnalysis}
					<span>Starting...</span>
				{:else}
					<span>Analyze with AI</span>
				{/if}
				<Lightbulb size={20} strokeWidth={1.5} />
			</Button>
			{#if images.length === 0}
				<p class="mt-2 text-center text-caption text-neutral-500">Add photos to continue</p>
			{/if}
		{/if}
	</AppContainer>
</div>
