<script lang="ts">
	import { onMount } from "svelte";
	import Button from "./Button.svelte";
	import type { ThumbnailTransform } from "$lib/types";

	interface Props {
		images: { file: File; dataUrl: string }[];
		currentThumbnail?: string;
		initialTransform?: ThumbnailTransform;
		onSave: (
			dataUrl: string,
			sourceImageIndex: number,
			transform: ThumbnailTransform,
		) => void;
		onClose: () => void;
	}

	let { images, currentThumbnail, initialTransform, onSave, onClose }: Props =
		$props();

	// Track if we should apply initial transform on first load
	let shouldApplyInitialTransform = $state(!!initialTransform);

	let canvas: HTMLCanvasElement;
	let ctx: CanvasRenderingContext2D | null = null;

	// Selected image
	let selectedImageIndex = $state(0);
	let loadedImage: HTMLImageElement | null = null;

	// Transform state
	// Offset is in the ROTATED coordinate space (relative to crop center after rotation)
	let scale = $state(1);
	let rotation = $state(0); // in degrees
	let offsetX = $state(0);
	let offsetY = $state(0);

	// Responsive canvas size (340-480px based on viewport)
	let canvasSize = $state(340);

	// Crop area (square, centered) - scales with canvas
	let CROP_SIZE = $derived(Math.round(canvasSize * 0.706)); // ~240/340 ratio
	let cropCenterX = $derived(canvasSize / 2);
	let cropCenterY = $derived(canvasSize / 2);

	// Touch/mouse state
	let isDragging = $state(false);
	let lastX = 0;
	let lastY = 0;
	let lastTouchDistance = 0;
	let lastTouchAngle = 0;

	// Scale limits
	// minScale is dynamic - calculated per image so crop square touches image edges at slider=0
	let minScale = $state(0.1);
	const MAX_SCALE = 5; // 500% max zoom
	const MIN_ROTATION = -180;
	const MAX_ROTATION = 180;

	// Logarithmic slider conversion functions
	// This makes zoom feel linear to users (same slider distance = same perceived zoom change)
	// Formula: scale = minScale * (MAX_SCALE/minScale)^sliderPosition
	function scaleToSlider(s: number): number {
		// Convert actual scale to slider position (0-1)
		const logBase = MAX_SCALE / minScale;
		return Math.log(s / minScale) / Math.log(logBase);
	}

	function sliderToScale(sliderValue: number): number {
		// Convert slider position (0-1) to actual scale
		const logBase = MAX_SCALE / minScale;
		return minScale * Math.pow(logBase, sliderValue);
	}

	// For slider display
	let zoomPercent = $derived(Math.round(scale * 100));
	let zoomSliderValue = $derived(scaleToSlider(scale));

	// Convert screen-space delta to rotated-space delta (for panning)
	function screenToRotatedSpace(
		dx: number,
		dy: number,
	): { rdx: number; rdy: number } {
		const rad = (-rotation * Math.PI) / 180;
		return {
			rdx: dx * Math.cos(rad) - dy * Math.sin(rad),
			rdy: dx * Math.sin(rad) + dy * Math.cos(rad),
		};
	}

	onMount(() => {
		// Calculate responsive canvas size based on viewport width
		// Use most of the available width for a larger working area
		const viewportWidth = window.innerWidth;
		if (viewportWidth >= 640) {
			canvasSize = Math.min(480, viewportWidth - 80);
		} else {
			// On small screens, use more width for a bigger canvas
			canvasSize = Math.min(440, viewportWidth - 32);
		}

		// Wait for next tick to ensure canvas dimensions are set
		requestAnimationFrame(() => {
			ctx = canvas.getContext("2d");
			// Load from initial transform's image index if available, otherwise first image
			const startIndex = initialTransform?.sourceImageIndex ?? 0;
			loadImage(startIndex);
		});
	});

	function loadImage(index: number) {
		if (index < 0 || index >= images.length) return;

		const img = new Image();
		img.onload = () => {
			loadedImage = img;

			// Calculate minScale first (needed for both paths)
			const cropSize = CROP_SIZE;
			minScale = cropSize / img.width;

			// Apply initial transform if available and this is the first load
			if (
				shouldApplyInitialTransform &&
				initialTransform &&
				index === initialTransform.sourceImageIndex
			) {
				scale = initialTransform.scale;
				rotation = initialTransform.rotation;
				offsetX = initialTransform.offsetX;
				offsetY = initialTransform.offsetY;
				shouldApplyInitialTransform = false; // Only apply once
			} else {
				// Reset to default using shared function
				scale = minScale;
				rotation = 0;
				offsetX = 0;
				offsetY = 0;
			}

			requestAnimationFrame(() => render());
		};
		img.src = images[index].dataUrl;
		selectedImageIndex = index;
	}

	function resetTransform() {
		if (!loadedImage) return;

		// Calculate minimum scale so image width fits the crop area
		// For portrait images, height extends beyond crop - user can pan vertically
		// For landscape images, this naturally fills the crop area
		const cropSize = CROP_SIZE;
		minScale = cropSize / loadedImage.width;

		// Start at minimum scale (image width matches crop width)
		scale = minScale;
		rotation = 0;
		offsetX = 0;
		offsetY = 0;
		render();
	}

	function render() {
		if (!ctx || !loadedImage) return;

		const w = canvasSize;
		const h = canvasSize;
		const cropSize = CROP_SIZE;
		const centerX = cropCenterX;
		const centerY = cropCenterY;

		// Clear canvas
		ctx.fillStyle = "#0a0a0f"; // neutral-950
		ctx.fillRect(0, 0, w, h);

		// Save context state
		ctx.save();

		// Transform order for rotation around crop center:
		// 1. Move to crop center
		ctx.translate(centerX, centerY);
		// 2. Rotate around crop center
		ctx.rotate((rotation * Math.PI) / 180);
		// 3. Apply offset (in rotated space)
		ctx.translate(offsetX, offsetY);
		// 4. Scale
		ctx.scale(scale, scale);
		// 5. Draw image centered at this point
		ctx.drawImage(
			loadedImage,
			-loadedImage.width / 2,
			-loadedImage.height / 2,
			loadedImage.width,
			loadedImage.height,
		);

		ctx.restore();

		// Draw dark overlay with transparent crop area
		ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
		ctx.fillRect(0, 0, w, centerY - cropSize / 2);
		ctx.fillRect(
			0,
			centerY + cropSize / 2,
			w,
			h - (centerY + cropSize / 2),
		);
		ctx.fillRect(
			0,
			centerY - cropSize / 2,
			centerX - cropSize / 2,
			cropSize,
		);
		ctx.fillRect(
			centerX + cropSize / 2,
			centerY - cropSize / 2,
			w - (centerX + cropSize / 2),
			cropSize,
		);

		// Draw crop border
		ctx.strokeStyle = "rgba(99, 102, 241, 0.8)"; // primary-500
		ctx.lineWidth = 2;
		ctx.strokeRect(
			centerX - cropSize / 2,
			centerY - cropSize / 2,
			cropSize,
			cropSize,
		);

		// Draw corner handles
		const handleSize = 20;
		ctx.strokeStyle = "#6366f1"; // primary-500
		ctx.lineWidth = 3;

		// Top-left
		ctx.beginPath();
		ctx.moveTo(centerX - cropSize / 2, centerY - cropSize / 2 + handleSize);
		ctx.lineTo(centerX - cropSize / 2, centerY - cropSize / 2);
		ctx.lineTo(centerX - cropSize / 2 + handleSize, centerY - cropSize / 2);
		ctx.stroke();

		// Top-right
		ctx.beginPath();
		ctx.moveTo(centerX + cropSize / 2 - handleSize, centerY - cropSize / 2);
		ctx.lineTo(centerX + cropSize / 2, centerY - cropSize / 2);
		ctx.lineTo(centerX + cropSize / 2, centerY - cropSize / 2 + handleSize);
		ctx.stroke();

		// Bottom-left
		ctx.beginPath();
		ctx.moveTo(centerX - cropSize / 2, centerY + cropSize / 2 - handleSize);
		ctx.lineTo(centerX - cropSize / 2, centerY + cropSize / 2);
		ctx.lineTo(centerX - cropSize / 2 + handleSize, centerY + cropSize / 2);
		ctx.stroke();

		// Bottom-right
		ctx.beginPath();
		ctx.moveTo(centerX + cropSize / 2 - handleSize, centerY + cropSize / 2);
		ctx.lineTo(centerX + cropSize / 2, centerY + cropSize / 2);
		ctx.lineTo(centerX + cropSize / 2, centerY + cropSize / 2 - handleSize);
		ctx.stroke();
	}

	// Mouse drag for panning
	function handleMouseDown(e: MouseEvent) {
		isDragging = true;
		lastX = e.clientX;
		lastY = e.clientY;
	}

	function handleMouseMove(e: MouseEvent) {
		if (!isDragging) return;

		const dx = e.clientX - lastX;
		const dy = e.clientY - lastY;

		// Convert screen delta to rotated space
		const { rdx, rdy } = screenToRotatedSpace(dx, dy);
		offsetX += rdx;
		offsetY += rdy;

		lastX = e.clientX;
		lastY = e.clientY;
		render();
	}

	function handleMouseUp() {
		isDragging = false;
	}

	// Mouse wheel for zoom (keep for convenience)
	function handleWheel(e: WheelEvent) {
		e.preventDefault();
		const delta = e.deltaY > 0 ? 0.95 : 1.05;
		scale = Math.max(minScale, Math.min(MAX_SCALE, scale * delta));
		render();
	}

	// Touch events
	function handleTouchStart(e: TouchEvent) {
		e.preventDefault();

		if (e.touches.length === 1) {
			isDragging = true;
			lastX = e.touches[0].clientX;
			lastY = e.touches[0].clientY;
		} else if (e.touches.length === 2) {
			isDragging = false;
			lastTouchDistance = getTouchDistance(e.touches);
			lastTouchAngle = getTouchAngle(e.touches);
		}
	}

	function handleTouchMove(e: TouchEvent) {
		e.preventDefault();

		if (e.touches.length === 1 && isDragging) {
			const dx = e.touches[0].clientX - lastX;
			const dy = e.touches[0].clientY - lastY;

			// Convert to rotated space using shared helper
			const { rdx, rdy } = screenToRotatedSpace(dx, dy);
			offsetX += rdx;
			offsetY += rdy;

			lastX = e.touches[0].clientX;
			lastY = e.touches[0].clientY;
		} else if (e.touches.length === 2) {
			// Pinch zoom
			const newDistance = getTouchDistance(e.touches);
			const scaleChange = newDistance / lastTouchDistance;
			scale = Math.max(
				minScale,
				Math.min(MAX_SCALE, scale * scaleChange),
			);
			lastTouchDistance = newDistance;

			// Two-finger rotation
			const newAngle = getTouchAngle(e.touches);
			const angleDelta = (newAngle - lastTouchAngle) * (180 / Math.PI);
			rotation = Math.max(
				MIN_ROTATION,
				Math.min(MAX_ROTATION, rotation + angleDelta),
			);
			lastTouchAngle = newAngle;
		}

		render();
	}

	function handleTouchEnd(e: TouchEvent) {
		if (e.touches.length === 0) {
			isDragging = false;
		} else if (e.touches.length === 1) {
			isDragging = true;
			lastX = e.touches[0].clientX;
			lastY = e.touches[0].clientY;
		}
	}

	function getTouchDistance(touches: TouchList): number {
		const dx = touches[0].clientX - touches[1].clientX;
		const dy = touches[0].clientY - touches[1].clientY;
		return Math.sqrt(dx * dx + dy * dy);
	}

	function getTouchAngle(touches: TouchList): number {
		const dx = touches[1].clientX - touches[0].clientX;
		const dy = touches[1].clientY - touches[0].clientY;
		return Math.atan2(dy, dx);
	}

	// Slider handlers
	function handleZoomSlider(e: Event) {
		const input = e.target as HTMLInputElement;
		// Convert linear slider position to logarithmic scale
		scale = sliderToScale(parseFloat(input.value));
		render();
	}

	function handleRotationSlider(e: Event) {
		const input = e.target as HTMLInputElement;
		rotation = parseFloat(input.value);
		render();
	}

	// Quick rotation buttons
	function rotateLeft90() {
		rotation = Math.max(MIN_ROTATION, rotation - 90);
		render();
	}

	function rotateRight90() {
		rotation = Math.min(MAX_ROTATION, rotation + 90);
		render();
	}

	// Save cropped image
	function saveCrop() {
		if (!loadedImage) return;

		const outputSize = 400;
		const outputCanvas = document.createElement("canvas");
		outputCanvas.width = outputSize;
		outputCanvas.height = outputSize;
		const outputCtx = outputCanvas.getContext("2d");

		if (!outputCtx) return;

		const cropSize = CROP_SIZE;
		const outputScale = outputSize / cropSize;

		outputCtx.fillStyle = "#0a0a0f"; // neutral-950
		outputCtx.fillRect(0, 0, outputSize, outputSize);

		// Same transform order as render, but scaled for output
		outputCtx.translate(outputSize / 2, outputSize / 2);
		outputCtx.rotate((rotation * Math.PI) / 180);
		outputCtx.translate(offsetX * outputScale, offsetY * outputScale);
		outputCtx.scale(scale * outputScale, scale * outputScale);

		outputCtx.drawImage(
			loadedImage,
			-loadedImage.width / 2,
			-loadedImage.height / 2,
			loadedImage.width,
			loadedImage.height,
		);

		const dataUrl = outputCanvas.toDataURL("image/jpeg", 0.9);

		// Build transform state so it can be restored later
		const transform: ThumbnailTransform = {
			scale,
			rotation,
			offsetX,
			offsetY,
			sourceImageIndex: selectedImageIndex,
			dataUrl,
		};

		onSave(dataUrl, selectedImageIndex, transform);
	}
</script>

<div
	class="fixed inset-0 z-[60] flex items-start justify-center bg-black/80 p-4 sm:p-8 overflow-y-auto"
>
	<div
		class="bg-neutral-900 rounded-2xl border border-neutral-700 max-w-lg w-full shadow-xl my-auto sm:my-8"
	>
		<!-- Header -->
		<div
			class="flex items-center justify-between p-4 border-b border-neutral-700"
		>
			<h3 class="text-body-lg font-semibold text-neutral-100">
				Edit Thumbnail
			</h3>
			<button
				type="button"
				class="p-2 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 rounded-lg transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
				onclick={onClose}
				aria-label="Close"
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
		</div>

		<!-- Instructions at top for better discovery -->
		<div class="px-4 py-2 bg-neutral-800/50 border-b border-neutral-700/50">
			<p class="text-xs text-neutral-400 text-center">
				Drag to pan • Scroll to zoom • On mobile: pinch to zoom, two
				fingers to rotate
			</p>
		</div>

		<!-- Image selector with larger thumbnails and labels -->
		{#if images.length > 1}
			<div class="px-4 py-3 border-b border-neutral-700/50">
				<span class="text-xs text-neutral-400 mb-2 block font-medium"
					>Select source image:</span
				>
				<div class="flex gap-3 overflow-x-auto pb-2">
					{#each images as img, index}
						<button
							type="button"
							class="flex flex-col items-center gap-1 flex-shrink-0"
							onclick={() => loadImage(index)}
						>
							<div
								class="w-16 h-16 rounded-lg overflow-hidden border-2 transition-all {selectedImageIndex ===
								index
									? 'border-primary-500 ring-2 ring-primary-500/30'
									: 'border-neutral-700 hover:border-neutral-600'}"
							>
								<img
									src={img.dataUrl}
									alt="Image {index + 1}"
									class="w-full h-full object-cover"
								/>
							</div>
							<span
								class="text-xs {selectedImageIndex === index
									? 'text-primary-400 font-medium'
									: 'text-neutral-500'}"
							>
								Image {index + 1}
							</span>
						</button>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Canvas area with cursor states -->
		<div class="flex items-center justify-center p-4 touch-none">
			<canvas
				bind:this={canvas}
				width={canvasSize}
				height={canvasSize}
				class="rounded-lg {isDragging
					? 'cursor-grabbing'
					: 'cursor-grab'}"
				onmousedown={handleMouseDown}
				onmousemove={handleMouseMove}
				onmouseup={handleMouseUp}
				onmouseleave={handleMouseUp}
				onwheel={handleWheel}
				ontouchstart={handleTouchStart}
				ontouchmove={handleTouchMove}
				ontouchend={handleTouchEnd}
			></canvas>
		</div>

		<!-- Slider Controls -->
		<div class="px-4 py-4 border-t border-neutral-700/50 space-y-5">
			<!-- Zoom slider with tick marks -->
			<div>
				<div class="flex items-center justify-between mb-2">
					<label
						for="zoomSlider"
						class="text-xs text-neutral-300 flex items-center gap-1.5 font-medium"
					>
						<svg
							class="w-4 h-4 text-primary-400"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="1.5"
						>
							<circle cx="11" cy="11" r="8" />
							<path d="m21 21-4.35-4.35" />
						</svg>
						Zoom
					</label>
					<span
						class="text-xs text-neutral-400 font-mono bg-neutral-800 px-2 py-0.5 rounded"
						>{zoomPercent}%</span
					>
				</div>
				<!-- Tick marks for zoom -->
				<div class="relative mb-1">
					<div
						class="flex justify-between text-[10px] text-neutral-600 px-0.5"
					>
						<span>Min</span>
						<span>100%</span>
						<span>500%</span>
					</div>
				</div>
				<input
					id="zoomSlider"
					type="range"
					min="0"
					max="1"
					step="0.005"
					value={zoomSliderValue}
					oninput={handleZoomSlider}
					class="w-full h-2 bg-neutral-800 rounded-lg appearance-none cursor-pointer"
				/>
			</div>

			<!-- Rotation slider with tick marks -->
			<div>
				<div class="flex items-center justify-between mb-2">
					<label
						for="rotationSlider"
						class="text-xs text-neutral-300 flex items-center gap-1.5 font-medium"
					>
						<svg
							class="w-4 h-4 text-primary-400"
							fill="none"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
							viewBox="0 0 24 24"
						>
							<path
								d="M3 2V8M3 8H9M3 8L5.64033 5.63067C7.02134 4.25209 8.81301 3.35964 10.7454 3.08779C12.6777 2.81593 14.6461 3.17941 16.3539 4.12343C18.0617 5.06746 19.4165 6.54091 20.214 8.32177C21.0115 10.1026 21.2086 12.0944 20.7756 13.997C20.3426 15.8996 19.303 17.61 17.8133 18.8704C16.3237 20.1308 14.4647 20.873 12.5165 20.9851C10.5684 21.0972 8.63652 20.5732 7.01208 19.492C5.38765 18.4108 4.15862 16.831 3.51018 14.9907"
							/>
						</svg>
						Rotation
					</label>
					<span
						class="text-xs text-neutral-400 font-mono bg-neutral-800 px-2 py-0.5 rounded"
						>{Math.round(rotation)}°</span
					>
				</div>
				<!-- Tick marks for rotation -->
				<div class="relative mb-1 px-11">
					<div
						class="flex justify-between text-[10px] text-neutral-600"
					>
						<span>-180°</span>
						<span>-90°</span>
						<span>0°</span>
						<span>90°</span>
						<span>180°</span>
					</div>
				</div>
				<div class="flex items-center gap-2">
					<button
						type="button"
						class="p-2 rounded-lg bg-neutral-800 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 transition-colors relative z-10 flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={rotateLeft90}
						aria-label="Rotate 90° left"
						title="-90°"
					>
						<svg
							class="w-5 h-5"
							fill="none"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
							viewBox="0 0 24 24"
						>
							<path
								d="M3 2V8M3 8H9M3 8L5.64033 5.63067C7.02134 4.25209 8.81301 3.35964 10.7454 3.08779C12.6777 2.81593 14.6461 3.17941 16.3539 4.12343C18.0617 5.06746 19.4165 6.54091 20.214 8.32177C21.0115 10.1026 21.2086 12.0944 20.7756 13.997C20.3426 15.8996 19.303 17.61 17.8133 18.8704C16.3237 20.1308 14.4647 20.873 12.5165 20.9851C10.5684 21.0972 8.63652 20.5732 7.01208 19.492C5.38765 18.4108 4.15862 16.831 3.51018 14.9907"
							/>
						</svg>
					</button>
					<input
						id="rotationSlider"
						type="range"
						min={MIN_ROTATION}
						max={MAX_ROTATION}
						step="1"
						value={rotation}
						oninput={handleRotationSlider}
						class="flex-1 h-2 bg-neutral-800 rounded-lg appearance-none cursor-pointer relative z-0"
					/>
					<button
						type="button"
						class="p-2 rounded-lg bg-neutral-800 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 transition-colors relative z-10 flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center"
						onclick={rotateRight90}
						aria-label="Rotate 90° right"
						title="+90°"
					>
						<svg
							class="w-5 h-5"
							fill="none"
							stroke="currentColor"
							stroke-width="1.5"
							stroke-linecap="round"
							stroke-linejoin="round"
							viewBox="0 0 24 24"
						>
							<path
								d="M21 2V8M21 8H15M21 8L18.3597 5.63067C16.9787 4.25209 15.187 3.35964 13.2546 3.08779C11.3223 2.81593 9.3539 3.17941 7.6461 4.12343C5.9383 5.06746 4.5835 6.54091 3.786 8.32177C2.9885 10.1026 2.7914 12.0944 3.2244 13.997C3.6574 15.8996 4.697 17.61 6.1867 18.8704C7.6763 20.1308 9.5353 20.873 11.4835 20.9851C13.4316 21.0972 15.3635 20.5732 16.9879 19.492C18.6124 18.4108 19.8414 16.831 20.4898 14.9907"
							/>
						</svg>
					</button>
				</div>
			</div>

			<!-- Reset button -->
			<div class="flex justify-center">
				<button
					type="button"
					class="px-4 py-2 rounded-lg bg-neutral-800 text-neutral-400 hover:text-neutral-100 hover:bg-neutral-700 text-sm transition-colors min-h-[44px]"
					onclick={resetTransform}
				>
					Reset to Default
				</button>
			</div>
		</div>

		<!-- Actions -->
		<div class="flex gap-3 p-4 border-t border-neutral-700">
			<Button variant="secondary" onclick={onClose}>Cancel</Button>
			<Button variant="primary" onclick={saveCrop}>
				<svg
					class="w-4 h-4"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
					stroke-width="1.5"
				>
					<polyline points="20 6 9 17 4 12" />
				</svg>
				<span>Save Thumbnail</span>
			</Button>
		</div>
	</div>
</div>

<style>
	/* Custom slider styling with larger thumbs (22px) */
	input[type="range"] {
		-webkit-appearance: none;
		appearance: none;
		background: transparent;
	}

	input[type="range"]::-webkit-slider-runnable-track {
		width: 100%;
		height: 8px;
		background: #1e1e2e; /* neutral-800 */
		border-radius: 4px;
	}

	input[type="range"]::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 22px;
		height: 22px;
		background: #6366f1; /* primary-500 */
		border-radius: 50%;
		cursor: pointer;
		margin-top: -7px;
		transition:
			transform 0.15s,
			box-shadow 0.15s;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
	}

	input[type="range"]::-webkit-slider-thumb:hover {
		transform: scale(1.15);
		box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
	}

	input[type="range"]::-webkit-slider-thumb:active {
		transform: scale(1.05);
	}

	input[type="range"]::-moz-range-track {
		width: 100%;
		height: 8px;
		background: #1e1e2e; /* neutral-800 */
		border-radius: 4px;
	}

	input[type="range"]::-moz-range-thumb {
		width: 22px;
		height: 22px;
		background: #6366f1; /* primary-500 */
		border-radius: 50%;
		cursor: pointer;
		border: none;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
	}

	input[type="range"]::-moz-range-thumb:hover {
		box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
	}

	/* Focus states for accessibility */
	input[type="range"]:focus {
		outline: none;
	}

	input[type="range"]:focus::-webkit-slider-thumb {
		box-shadow:
			0 0 0 3px rgba(99, 102, 241, 0.3),
			0 2px 4px rgba(0, 0, 0, 0.3);
	}

	input[type="range"]:focus::-moz-range-thumb {
		box-shadow:
			0 0 0 3px rgba(99, 102, 241, 0.3),
			0 2px 4px rgba(0, 0, 0, 0.3);
	}
</style>
