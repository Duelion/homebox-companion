<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";
	import { slide } from "svelte/transition";
	import { resetLocationState } from "$lib/stores/locations.svelte";
	import { showToast } from "$lib/stores/ui";
	import { markSessionExpired } from "$lib/stores/auth";
	import { scanWorkflow } from "$lib/workflows/scan.svelte";
	import { checkAuth } from "$lib/utils/token";
	import { routeGuards } from "$lib/utils/routeGuard";
	import { createLogger } from "$lib/utils/logger";
	import { getConfig } from "$lib/api/settings";
	import Button from "$lib/components/Button.svelte";
	import StepIndicator from "$lib/components/StepIndicator.svelte";
	import BackLink from "$lib/components/BackLink.svelte";
	import AnalysisProgressBar from "$lib/components/AnalysisProgressBar.svelte";
	import StatusIcon from "$lib/components/StatusIcon.svelte";

	const log = createLogger({ prefix: "Capture" });

	// Capture limits (loaded from config, with safe defaults)
	let maxImages = $state(30);
	let maxFileSizeMb = $state(10);
	let configLoaded = $state(false);

	let fileInput: HTMLInputElement;
	let cameraInput: HTMLInputElement;

	// Local UI state (not workflow state)
	let expandedImages = $state<Set<number>>(new Set());
	let additionalImageInputs: { [key: number]: HTMLInputElement } = {};
	let additionalCameraInputs: { [key: number]: HTMLInputElement } = {};
	let analysisAnimationComplete = $state(false);
	let isStartingAnalysis = $state(false);
	let progressBarRef = $state<HTMLDivElement | null>(null);

	// Track object URLs for cleanup (prevents memory leaks)
	// Note: We only revoke URLs when images are explicitly removed, NOT on component
	// destroy. This is because the workflow state persists across navigation, and
	// we need the URLs to remain valid if the user navigates back to this page.
	// The browser automatically cleans up Object URLs when the page/tab is closed.
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
	let isAnalyzing = $derived(status === "analyzing");
	let progress = $derived(workflow.state.analysisProgress);
	let imageStatuses = $derived(workflow.state.imageStatuses);
	let locationName = $derived(workflow.state.locationName);
	let locationPath = $derived(workflow.state.locationPath);
	let parentItemName = $derived(workflow.state.parentItemName);

	// Analysis status counts (computed once for efficiency)
	let failedImageCount = $derived(
		Object.values(imageStatuses).filter((s) => s === "failed").length,
	);
	let succeededImageCount = $derived(
		Object.values(imageStatuses).filter((s) => s === "success").length,
	);
	let detectedItemCount = $derived(workflow.state.detectedItems.length);

	// Total image count including additional images (for limit enforcement)
	let totalImageCount = $derived(
		images.reduce(
			(count, img) => count + 1 + (img.additionalFiles?.length || 0),
			0,
		),
	);

	// True while analyzing OR while the completion animation is playing
	// This prevents UI elements from appearing/disappearing during animation
	let showAnalyzingUI = $derived(
		isAnalyzing || (status === "reviewing" && !analysisAnimationComplete),
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
		if (!routeGuards.capture()) return;

		// Load capture limits from config
		try {
			const config = await getConfig();
			maxImages = config.capture_max_images;
			maxFileSizeMb = config.capture_max_file_size_mb;
		} catch (error) {
			log.warn("Failed to load capture config, using defaults", error);
		} finally {
			configLoaded = true;
		}

		// If workflow is complete (just finished submission), reset for a new scan session
		if (workflow.state.status === "complete") {
			log.info("Workflow complete, resetting for new scan session");
			workflow.startNew();
		}
	});

	// Watch for workflow errors
	$effect(() => {
		if (workflow.state.error) {
			showToast(workflow.state.error, "error");
			workflow.clearError();
		}
	});

	// Handle analysis animation completion - navigate directly to avoid CaptureButtons appearing
	function handleAnalysisComplete() {
		analysisAnimationComplete = true;
		// Clear progress after animation finishes
		workflow.state.analysisProgress = null;

		// Navigate immediately to prevent UI shift from buttons reappearing
		if (workflow.state.status === "reviewing") {
			goto("/review");
		}
	}

	// ==========================================================================
	// FILE HANDLING
	// ==========================================================================

	/** Check if file exceeds size limit and show toast if so */
	function isFileTooLarge(file: File): boolean {
		if (file.size > maxFileSizeMb * 1024 * 1024) {
			showToast(
				`File ${file.name} is too large (max ${maxFileSizeMb}MB)`,
				"warning",
			);
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
				showToast(`Maximum ${maxImages} images allowed`, "warning");
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
				extraInstructions: "",
			});
			// Collapse all expanded accordions when a new image is added
			expandedImages = new Set();
		}

		input.value = "";
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
				showToast(`Maximum ${maxImages} images allowed`, "warning");
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

		input.value = "";
	}

	// ==========================================================================
	// IMAGE ACTIONS
	// ==========================================================================

	function toggleImageExpanded(index: number) {
		if (expandedImages.has(index)) {
			// Collapse if already expanded
			expandedImages = new Set();
		} else {
			// Expand this one and collapse all others
			expandedImages = new Set([index]);
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
		expandedImages = new Set(
			[...expandedImages]
				.filter((i) => i !== index)
				.map((i) => (i > index ? i - 1 : i)),
		);
	}

	function updateImageOption(
		index: number,
		field: "separateItems" | "extraInstructions",
		value: boolean | string,
	) {
		workflow.updateImageOptions(index, { [field]: value });
	}

	function removeAdditionalImage(
		imageIndex: number,
		additionalIndex: number,
	) {
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
		if (bytes < 1024) return bytes + " B";
		if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
		return (bytes / (1024 * 1024)).toFixed(1) + " MB";
	}

	function goBack() {
		resetLocationState();
		workflow.clearLocation();
		goto("/location");
	}

	// ==========================================================================
	// ANALYSIS - delegate to workflow
	// ==========================================================================

	async function startAnalysis() {
		// Entry logging
		log.info("Analyze button clicked");

		// Prevent double-clicks
		if (isStartingAnalysis || isAnalyzing) {
			log.debug(
				"Analysis already starting or in progress, ignoring click",
			);
			return;
		}

		isStartingAnalysis = true;
		log.debug("Starting analysis flow...");

		try {
			// Check token validity before starting analysis
			log.debug("Checking authentication...");
			const isValid = await checkAuth();
			if (!isValid) {
				// Token missing - trigger re-auth modal
				log.warn("Auth check failed, marking session expired");
				markSessionExpired();
				return;
			}
			log.debug("Auth check passed");

			// Before workflow call
			log.info(
				`Starting workflow analysis for ${workflow.state.images.length} image(s)`,
			);
			analysisAnimationComplete = false;
			// Collapse all expanded cards when analysis starts
			expandedImages = new Set();
			// Scroll to top of app after analysis starts
			setTimeout(() => {
				window.scrollTo({ top: 0, behavior: "smooth" });
			}, 100);
			await workflow.startAnalysis();
			log.debug("Workflow.startAnalysis() completed");
		} catch (error) {
			// Error logging
			log.error("Analysis failed with exception", error);
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

	<h2 class="text-h2 text-neutral-100 mb-1">Capture Items</h2>
	<p class="text-body-sm text-neutral-400 mb-6">
		Add photos and configure detection options
	</p>

	<!-- Current location display -->
	{#if locationPath}
		<BackLink
			href="/location"
			label="Change Location"
			onclick={goBack}
			disabled={isAnalyzing}
		/>

		<div
			class="flex flex-col gap-2 text-body-sm text-neutral-400 mb-3 mt-2"
		>
			<!-- Location block -->
			<div class="flex flex-col gap-1">
				<div class="flex items-center gap-2">
					<svg
						class="w-4 h-4 shrink-0"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="1.5"
					>
						<path
							d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"
						/>
						<circle cx="12" cy="10" r="3" />
					</svg>
					<span>Items will be added to:</span>
				</div>
				<span class="font-semibold text-neutral-200 pl-6"
					>{locationPath}</span
				>
			</div>

			<!-- Parent item block (if present) -->
			{#if parentItemName}
				<div class="flex items-center gap-2 pl-6 sm:pl-0">
					<span class="text-neutral-500">Inside:</span>
					<span class="font-semibold text-primary-400"
						>{parentItemName}</span
					>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Analysis progress bar (above images for context) -->
	{#if progress && showAnalyzingUI}
		<div class="mb-4" bind:this={progressBarRef}>
			<AnalysisProgressBar
				current={progress.current}
				total={progress.total}
				message={status === "reviewing"
					? "Analysis complete!"
					: progress.message || "Analyzing..."}
				onComplete={handleAnalysisComplete}
			/>
		</div>
	{/if}

	<!-- Partial failure panel (when some images failed analysis) -->
	{#if status === "partial_analysis"}
		<div
			class="bg-warning-500/10 border border-warning-500/30 rounded-xl p-4 mb-4"
			transition:slide={{ duration: 200 }}
		>
			<div class="flex items-start gap-3 mb-4">
				<!-- Warning icon -->
				<svg
					class="w-6 h-6 text-warning-400 shrink-0 mt-0.5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
					/>
				</svg>

				<div class="flex-1">
					<h3 class="text-body font-semibold text-warning-100 mb-1">
						Some Images Failed to Analyze
					</h3>
					<p class="text-body-sm text-warning-200/80 mb-3">
						{failedImageCount} of {images.length} image(s)
						could not be processed. You can retry the failed images, continue
						with the successful ones, or remove the failed images.
					</p>

					<!-- Stats -->
					<div class="flex gap-4 text-caption mb-4">
						<div class="flex items-center gap-1.5">
							<div
								class="w-2 h-2 rounded-full bg-success-400"
							></div>
							<span class="text-neutral-300"
								>{succeededImageCount} succeeded</span
							>
						</div>
						<div class="flex items-center gap-1.5">
							<div class="w-2 h-2 rounded-full bg-error-400"></div>
							<span class="text-neutral-300"
								>{failedImageCount} failed</span
							>
						</div>
						<div class="flex items-center gap-1.5">
							<div
								class="w-2 h-2 rounded-full bg-primary-400"
							></div>
							<span class="text-neutral-300"
								>{detectedItemCount} items detected</span
							>
						</div>
					</div>

					<!-- Action buttons -->
					<div class="flex flex-col sm:flex-row gap-2">
						<Button
							variant="warning"
							onclick={async () => {
								// Reset animation flag so progress bar works correctly
								analysisAnimationComplete = false;
								await workflow.retryFailedAnalysis();
							}}
							disabled={isStartingAnalysis}
						>
							<svg
								class="w-4 h-4"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
								/>
							</svg>
							<span>Retry Failed Images</span>
						</Button>
						<Button
							variant="primary"
							onclick={() => {
								workflow.continueWithSuccessful();
								goto("/review");
							}}
							disabled={isStartingAnalysis}
						>
							<span>Continue with Successful</span>
							<svg
								class="w-4 h-4"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<polyline points="9 18 15 12 9 6" />
							</svg>
						</Button>
						<Button
							variant="secondary"
							onclick={() => {
								workflow.removeFailedImages();
								goto("/review");
							}}
							disabled={isStartingAnalysis}
						>
							<svg
								class="w-4 h-4"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
								/>
							</svg>
							<span>Remove Failed</span>
						</Button>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<!-- Image list with collapsible cards -->
	{#if images.length > 0}
		<div class="space-y-3 mb-4">
			{#each images as image, index}
				<div
					class="bg-neutral-900 rounded-xl border border-neutral-700 shadow-sm overflow-hidden transition-all hover:border-neutral-600"
				>
					<!-- Header (always visible) -->
					<div class="flex items-center gap-3 p-3">
						<!-- Thumbnail -->
						<div
							class="w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden bg-neutral-800 relative"
						>
							<img
								src={image.dataUrl}
								alt="Captured {index + 1}"
								class="w-full h-full object-cover"
							/>
							<div
								class="absolute bottom-0.5 right-0.5 bg-black/70 text-white text-xs px-1.5 py-0.5 rounded font-medium"
							>
								{index + 1}
							</div>
						</div>

						<!-- File info -->
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2">
								<p
									class="text-body-sm font-medium text-neutral-200 truncate"
								>
									{image.file.name}
								</p>
								{#if image.additionalFiles && image.additionalFiles.length > 0}
									<span
										class="px-1.5 py-0.5 bg-primary-500/20 text-primary-300 rounded text-caption font-medium"
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
								<StatusIcon
									status={imageStatuses[index]}
									size="sm"
								/>
							{:else}
								<button
									type="button"
									class="p-2 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded-lg transition-colors"
									aria-label={expandedImages.has(index)
										? "Collapse options"
										: "Expand options"}
									onclick={() => toggleImageExpanded(index)}
									disabled={isAnalyzing}
								>
									<svg
										class="w-5 h-5 transition-transform duration-200 {expandedImages.has(
											index,
										)
											? 'rotate-180'
											: ''}"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										stroke-width="1.5"
									>
										<polyline points="6 9 12 15 18 9" />
									</svg>
								</button>
								<button
									type="button"
									class="p-2 text-neutral-400 hover:text-error-400 hover:bg-error-500/10 rounded-lg transition-colors"
									aria-label="Remove image"
									onclick={() => removeImage(index)}
									disabled={isAnalyzing}
								>
									<svg
										class="w-5 h-5"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
										stroke-width="1.5"
									>
										<line x1="18" y1="6" x2="6" y2="18" />
										<line x1="6" y1="6" x2="18" y2="18" />
									</svg>
								</button>
							{/if}
						</div>
					</div>

					<!-- Expandable options -->
					{#if expandedImages.has(index)}
						<div
							class="px-3 pb-3 pt-0 space-y-3 border-t border-neutral-800 mt-0"
							transition:slide={{ duration: 200 }}
						>
							<!-- Separate into multiple items toggle -->
							<label
								class="flex items-center gap-3 pt-3 cursor-pointer"
							>
								<div class="relative">
									<input
										type="checkbox"
										checked={image.separateItems}
										onchange={(e) =>
											updateImageOption(
												index,
												"separateItems",
												(e.target as HTMLInputElement)
													.checked,
											)}
										class="sr-only peer"
										disabled={isAnalyzing}
									/>
									<div
										class="w-10 h-6 bg-neutral-700 rounded-full peer-checked:bg-primary-600 transition-colors"
									></div>
									<div
										class="absolute left-1 top-1 w-4 h-4 bg-neutral-400 rounded-full peer-checked:translate-x-4 peer-checked:bg-white transition-all"
									></div>
								</div>
								<span class="text-body-sm text-neutral-200"
									>Separate into multiple items</span
								>
							</label>

							<!-- Optional instructions -->
							<div>
								<input
									type="text"
									placeholder="Optional: describe what's in this photo..."
									value={image.extraInstructions}
									oninput={(e) =>
										updateImageOption(
											index,
											"extraInstructions",
											(e.target as HTMLInputElement)
												.value,
										)}
									class="input text-body-sm"
									disabled={isAnalyzing}
								/>
							</div>

							<!-- Additional images for this item -->
							<input
								type="file"
								accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
								multiple
								bind:this={additionalImageInputs[index]}
								onchange={(e) =>
									handleAdditionalImageSelect(index, e)}
								class="hidden"
							/>
							<input
								type="file"
								accept="image/jpeg,image/png,image/jpg,image/webp,image/heic,image/heif"
								capture="environment"
								multiple
								bind:this={additionalCameraInputs[index]}
								onchange={(e) =>
									handleAdditionalImageSelect(index, e)}
								class="hidden"
							/>

							{#if image.additionalDataUrls && image.additionalDataUrls.length > 0}
								<!-- Has additional photos: show gallery strip -->
								<div
									class="pt-3 border-t border-neutral-800/50"
								>
									<div class="flex items-center gap-2 mb-3">
										<svg
											class="w-4 h-4 text-primary-400"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
											stroke-width="1.5"
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
											<polyline
												points="21 15 16 10 5 21"
											/>
										</svg>
										<span
											class="text-body-sm font-medium text-neutral-200"
										>
											{image.additionalDataUrls.length} additional
											photo{image.additionalDataUrls
												.length !== 1
												? "s"
												: ""}
										</span>
									</div>

									<!-- Thumbnail gallery -->
									<div
										class="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-thin"
									>
										{#each image.additionalDataUrls as additionalUrl, additionalIndex}
											<div
												class="relative flex-shrink-0 w-20 h-20 rounded-xl overflow-hidden bg-neutral-800 group ring-1 ring-neutral-700"
											>
												<img
													src={additionalUrl}
													alt="Additional {additionalIndex +
														1}"
													class="w-full h-full object-cover"
												/>
												<button
													type="button"
													class="absolute top-1 right-1 w-6 h-6 bg-black/70 hover:bg-error-600 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"
													aria-label="Remove additional image"
													onclick={() =>
														removeAdditionalImage(
															index,
															additionalIndex,
														)}
													disabled={isAnalyzing}
												>
													<svg
														class="w-3.5 h-3.5 text-white"
														fill="none"
														stroke="currentColor"
														stroke-width="2.5"
														viewBox="0 0 24 24"
													>
														<line
															x1="18"
															y1="6"
															x2="6"
															y2="18"
														/>
														<line
															x1="6"
															y1="6"
															x2="18"
															y2="18"
														/>
													</svg>
												</button>
												<div
													class="absolute bottom-1 left-1 bg-black/70 text-white text-[10px] font-medium px-1.5 py-0.5 rounded"
												>
													{additionalIndex + 1}
												</div>
											</div>
										{/each}
									</div>

									<!-- Add more buttons below gallery -->
									<div class="flex gap-2 mt-3">
										<button
											type="button"
											class="flex-1 py-2.5 px-3 rounded-lg border border-dashed border-neutral-600 hover:border-primary-500/50 hover:bg-primary-500/5 flex items-center justify-center gap-2 transition-all"
											onclick={() =>
												additionalCameraInputs[
													index
												]?.click()}
											disabled={isAnalyzing}
										>
											<svg
												class="w-4 h-4 text-neutral-400"
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
											<span
												class="text-caption text-neutral-400 font-medium"
												>Camera</span
											>
										</button>
										<button
											type="button"
											class="flex-1 py-2.5 px-3 rounded-lg border border-dashed border-neutral-600 hover:border-primary-500/50 hover:bg-primary-500/5 flex items-center justify-center gap-2 transition-all"
											onclick={() =>
												additionalImageInputs[
													index
												]?.click()}
											disabled={isAnalyzing}
										>
											<svg
												class="w-4 h-4 text-neutral-400"
												fill="none"
												stroke="currentColor"
												stroke-width="1.5"
												viewBox="0 0 24 24"
											>
												<path
													d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
												/>
												<polyline
													points="17 8 12 3 7 8"
												/>
												<line
													x1="12"
													y1="3"
													x2="12"
													y2="15"
												/>
											</svg>
											<span
												class="text-caption text-neutral-400 font-medium"
												>Upload</span
											>
										</button>
									</div>
								</div>
							{:else}
								<!-- Empty state: compact add buttons (same style as when photos exist) -->
								<div
									class="pt-3 border-t border-neutral-800/50"
								>
									<p
										class="text-caption text-neutral-500 mb-2"
									>
										Add close-ups, labels, serial numbers,
										different angles
									</p>
									<div class="flex gap-2">
										<button
											type="button"
											class="flex-1 py-2.5 px-3 rounded-lg border border-dashed border-neutral-600 hover:border-primary-500/50 hover:bg-primary-500/5 flex items-center justify-center gap-2 transition-all"
											onclick={() =>
												additionalCameraInputs[
													index
												]?.click()}
											disabled={isAnalyzing}
										>
											<svg
												class="w-4 h-4 text-neutral-400"
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
											<span
												class="text-caption text-neutral-400 font-medium"
												>Camera</span
											>
										</button>
										<button
											type="button"
											class="flex-1 py-2.5 px-3 rounded-lg border border-dashed border-neutral-600 hover:border-primary-500/50 hover:bg-primary-500/5 flex items-center justify-center gap-2 transition-all"
											onclick={() =>
												additionalImageInputs[
													index
												]?.click()}
											disabled={isAnalyzing}
										>
											<svg
												class="w-4 h-4 text-neutral-400"
												fill="none"
												stroke="currentColor"
												stroke-width="1.5"
												viewBox="0 0 24 24"
											>
												<path
													d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
												/>
												<polyline
													points="17 8 12 3 7 8"
												/>
												<line
													x1="12"
													y1="3"
													x2="12"
													y2="15"
												/>
											</svg>
											<span
												class="text-caption text-neutral-400 font-medium"
												>Upload</span
											>
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
						class="flex-1 p-4 rounded-xl border border-dashed border-neutral-600 hover:border-primary-500/50 hover:bg-primary-500/5 transition-all group"
						onclick={() => cameraInput.click()}
					>
						<div class="flex flex-col items-center gap-2">
							<div
								class="w-12 h-12 rounded-xl bg-neutral-800 flex items-center justify-center group-hover:bg-primary-500/10 transition-colors"
							>
								<svg
									class="w-6 h-6 text-neutral-400 group-hover:text-primary-400 transition-colors"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									stroke-width="1.5"
								>
									<path
										d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
									/>
									<circle cx="12" cy="13" r="4" />
								</svg>
							</div>
							<span
								class="text-body-sm font-medium text-neutral-400 group-hover:text-primary-400 transition-colors"
								>Camera</span
							>
						</div>
					</button>
					<button
						type="button"
						class="flex-1 p-4 rounded-xl border border-dashed border-neutral-600 hover:border-primary-500/50 hover:bg-primary-500/5 transition-all group"
						onclick={() => fileInput.click()}
					>
						<div class="flex flex-col items-center gap-2">
							<div
								class="w-12 h-12 rounded-xl bg-neutral-800 flex items-center justify-center group-hover:bg-primary-500/10 transition-colors"
							>
								<svg
									class="w-6 h-6 text-neutral-400 group-hover:text-primary-400 transition-colors"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
									stroke-width="1.5"
								>
									<path
										d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
									/>
									<polyline points="17 8 12 3 7 8" />
									<line x1="12" y1="3" x2="12" y2="15" />
								</svg>
							</div>
							<span
								class="text-body-sm font-medium text-neutral-400 group-hover:text-primary-400 transition-colors"
								>Upload</span
							>
						</div>
					</button>
				</div>
			{/if}
		</div>
	{:else}
		<!-- Enhanced empty state -->
		<div class="flex flex-col items-center py-12 px-4 mb-6">
			<div
				class="w-24 h-24 rounded-2xl bg-primary-500/10 flex items-center justify-center mb-6"
			>
				<svg
					class="w-12 h-12 text-primary-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
					/>
					<circle cx="12" cy="13" r="4" />
				</svg>
			</div>
			<h3 class="text-h3 text-neutral-100 mb-2 text-center">
				Capture your items
			</h3>
			<p class="text-body-sm text-neutral-400 text-center max-w-xs mb-8">
				Take photos or upload images of items you want to add to your
				inventory
			</p>

			<!-- Capture buttons -->
			<div class="flex gap-3 w-full max-w-sm">
				<button
					type="button"
					class="flex-1 p-4 rounded-xl bg-neutral-900 border border-neutral-700 hover:border-primary-500/50 hover:bg-neutral-800 transition-all group shadow-sm"
					onclick={() => cameraInput.click()}
				>
					<div class="flex flex-col items-center gap-2">
						<div
							class="w-12 h-12 rounded-xl bg-neutral-800 flex items-center justify-center group-hover:bg-primary-500/10 transition-colors"
						>
							<svg
								class="w-6 h-6 text-neutral-300 group-hover:text-primary-400 transition-colors"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
								/>
								<circle cx="12" cy="13" r="4" />
							</svg>
						</div>
						<span
							class="text-body-sm font-medium text-neutral-200 group-hover:text-primary-400 transition-colors"
							>Camera</span
						>
					</div>
				</button>
				<button
					type="button"
					class="flex-1 p-4 rounded-xl bg-neutral-900 border border-neutral-700 hover:border-primary-500/50 hover:bg-neutral-800 transition-all group shadow-sm"
					onclick={() => fileInput.click()}
				>
					<div class="flex flex-col items-center gap-2">
						<div
							class="w-12 h-12 rounded-xl bg-neutral-800 flex items-center justify-center group-hover:bg-primary-500/10 transition-colors"
						>
							<svg
								class="w-6 h-6 text-neutral-300 group-hover:text-primary-400 transition-colors"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="1.5"
							>
								<path
									d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
								/>
								<polyline points="17 8 12 3 7 8" />
								<line x1="12" y1="3" x2="12" y2="15" />
							</svg>
						</div>
						<span
							class="text-body-sm font-medium text-neutral-200 group-hover:text-primary-400 transition-colors"
							>Upload</span
						>
					</div>
				</button>
			</div>

			<p class="text-caption text-neutral-500 mt-6">
				{totalImageCount} / {maxImages} images · {maxFileSizeMb}MB per
				file
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
	class="fixed bottom-nav-offset left-0 right-0 bg-neutral-950/95 backdrop-blur-lg border-t border-neutral-800 p-4 z-40"
>
	<div class="max-w-lg mx-auto">
		{#if showAnalyzingUI && isAnalyzing}
			<Button variant="secondary" full onclick={cancelAnalysis}>
				<svg
					class="w-5 h-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
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
				<svg
					class="w-5 h-5"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<path
						d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
					/>
				</svg>
			</Button>
			{#if images.length === 0}
				<p class="text-center text-caption text-neutral-500 mt-2">
					Add photos to continue
				</p>
			{/if}
		{/if}
	</div>
</div>
