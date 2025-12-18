<script lang="ts">
	import { onMount } from "svelte";
	import Button from "./Button.svelte";

	interface Props {
		images: { file: File; dataUrl: string }[];
		currentThumbnail?: string;
		onSave: (dataUrl: string, sourceImageIndex: number) => void;
		onClose: () => void;
	}

	let { images, currentThumbnail, onSave, onClose }: Props = $props();

	// Selected image
	let selectedImageIndex = $state(0);
	let imageElement: HTMLImageElement;
	let containerElement: HTMLDivElement;

	// Transform state - all reactive
	let scale = $state(1);
	let rotation = $state(0);
	let offsetX = $state(0);
	let offsetY = $state(0);

	// Responsive sizing
	let containerSize = $state(340);
	let cropSize = $derived(Math.round(containerSize * 0.706));

	// Scale limits - 100% = image width fills crop area
	// displayScale is computed so that at 1.0, the image width equals crop width
	let baseScale = $state(1); // Calculated when image loads
	const MIN_SCALE = 1; // 100% - image width fills crop
	const MAX_SCALE = 5; // 500%
	const MIN_ROTATION = -180;
	const MAX_ROTATION = 180;

	// Gesture state (not reactive - internal tracking only)
	let isDragging = false;
	let lastX = 0;
	let lastY = 0;
	let lastTouchDistance = 0;
	let lastTouchAngle = 0;

	// The actual CSS scale = baseScale * scale
	// Where baseScale is calculated so image width = crop width
	// And scale is the user-controlled 1.0 (100%) to 5.0 (500%)
	let displayScale = $derived(baseScale * scale);

	// CSS transform string - computed reactively
	let transformStyle = $derived(
		`translate(${offsetX}px, ${offsetY}px) rotate(${rotation}deg) scale(${displayScale})`,
	);

	// Linear slider for 100%-500% (no need for logarithmic since range is reasonable)
	let zoomPercent = $derived(Math.round(scale * 100));
	let zoomSliderValue = $derived(
		(scale - MIN_SCALE) / (MAX_SCALE - MIN_SCALE),
	); // 0 to 1

	function sliderToScale(sliderValue: number): number {
		return MIN_SCALE + sliderValue * (MAX_SCALE - MIN_SCALE);
	}

	onMount(() => {
		// Calculate responsive container size
		const viewportWidth = window.innerWidth;
		if (viewportWidth >= 640) {
			containerSize = Math.min(480, viewportWidth - 80);
		} else {
			containerSize = Math.min(440, viewportWidth - 32);
		}
	});

	// Reset transform when image changes
	function selectImage(index: number) {
		if (index < 0 || index >= images.length) return;
		selectedImageIndex = index;
		// Reset transform for new image
		resetTransform();
	}

	function resetTransform() {
		// Calculate base scale so image width = crop width at 100%
		if (imageElement?.naturalWidth) {
			baseScale = cropSize / imageElement.naturalWidth;
		}
		scale = MIN_SCALE; // Start at 100%
		rotation = 0;
		offsetX = 0;
		offsetY = 0;
	}

	function handleImageLoad() {
		// Calculate base scale so image width = crop width at 100%
		baseScale = cropSize / imageElement.naturalWidth;
		scale = MIN_SCALE; // Start at 100%
		offsetX = 0;
		offsetY = 0;
	}

	// Mouse handlers
	function handleMouseDown(e: MouseEvent) {
		isDragging = true;
		lastX = e.clientX;
		lastY = e.clientY;
		e.preventDefault();
	}

	function handleMouseMove(e: MouseEvent) {
		if (!isDragging) return;

		const dx = e.clientX - lastX;
		const dy = e.clientY - lastY;

		// Convert screen delta to rotated space
		const rad = (-rotation * Math.PI) / 180;
		offsetX += dx * Math.cos(rad) - dy * Math.sin(rad);
		offsetY += dx * Math.sin(rad) + dy * Math.cos(rad);

		lastX = e.clientX;
		lastY = e.clientY;
	}

	function handleMouseUp() {
		isDragging = false;
	}

	function handleWheel(e: WheelEvent) {
		e.preventDefault();
		const delta = e.deltaY > 0 ? 0.95 : 1.05;
		scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale * delta));
	}

	// Touch handlers
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

			// Convert to rotated space
			const rad = (-rotation * Math.PI) / 180;
			offsetX += dx * Math.cos(rad) - dy * Math.sin(rad);
			offsetY += dx * Math.sin(rad) + dy * Math.cos(rad);

			lastX = e.touches[0].clientX;
			lastY = e.touches[0].clientY;
		} else if (e.touches.length === 2) {
			// Pinch zoom
			const newDistance = getTouchDistance(e.touches);
			const scaleChange = newDistance / lastTouchDistance;
			scale = Math.max(
				MIN_SCALE,
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
		scale = sliderToScale(parseFloat(input.value));
	}

	function handleRotationSlider(e: Event) {
		const input = e.target as HTMLInputElement;
		rotation = parseFloat(input.value);
	}

	function rotateLeft90() {
		rotation = Math.max(MIN_ROTATION, rotation - 90);
	}

	function rotateRight90() {
		rotation = Math.min(MAX_ROTATION, rotation + 90);
	}

	// Save cropped image - uses offscreen canvas only at save time
	function saveCrop() {
		const outputSize = 400;
		const canvas = document.createElement("canvas");
		canvas.width = outputSize;
		canvas.height = outputSize;
		const ctx = canvas.getContext("2d");

		if (!ctx || !imageElement) return;

		// Scale factor from display crop to output size
		const outputScale = outputSize / cropSize;

		ctx.fillStyle = "#0a0a0f";
		ctx.fillRect(0, 0, outputSize, outputSize);

		// Replicate the exact CSS transform chain:
		// 1. Move origin to center of output
		ctx.translate(outputSize / 2, outputSize / 2);
		// 2. Apply user rotation
		ctx.rotate((rotation * Math.PI) / 180);
		// 3. Apply user offset (scaled to output)
		ctx.translate(offsetX * outputScale, offsetY * outputScale);
		// 4. Apply display scale (baseScale * scale), scaled to output
		ctx.scale(displayScale * outputScale, displayScale * outputScale);

		// Draw image centered at origin (matches CSS translate(-50%, -50%))
		ctx.drawImage(
			imageElement,
			-imageElement.naturalWidth / 2,
			-imageElement.naturalHeight / 2,
			imageElement.naturalWidth,
			imageElement.naturalHeight,
		);

		const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
		onSave(dataUrl, selectedImageIndex);
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

		<!-- Instructions -->
		<div class="px-4 py-2 bg-neutral-800/50 border-b border-neutral-700/50">
			<p class="text-xs text-neutral-400 text-center">
				Drag to pan • Scroll to zoom • On mobile: pinch to zoom, two
				fingers to rotate
			</p>
		</div>

		<!-- Image selector -->
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
							onclick={() => selectImage(index)}
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

		<!-- Image editor area - CSS transforms instead of canvas -->
		<div
			bind:this={containerElement}
			class="flex items-center justify-center p-4 touch-none"
			role="application"
			aria-label="Image editor"
		>
			<div
				class="relative overflow-hidden rounded-lg"
				style:width="{containerSize}px"
				style:height="{containerSize}px"
				style:background="#0a0a0f"
				onmousedown={handleMouseDown}
				onmousemove={handleMouseMove}
				onmouseup={handleMouseUp}
				onmouseleave={handleMouseUp}
				onwheel={handleWheel}
				ontouchstart={handleTouchStart}
				ontouchmove={handleTouchMove}
				ontouchend={handleTouchEnd}
			>
				<!-- The image with CSS transforms -->
				<img
					bind:this={imageElement}
					src={images[selectedImageIndex].dataUrl}
					alt="Edit preview"
					class="absolute pointer-events-none select-none"
					style:left="50%"
					style:top="50%"
					style:transform-origin="center center"
					style:transform="translate(-50%, -50%) {transformStyle}"
					onload={handleImageLoad}
					draggable="false"
				/>

				<!-- Crop overlay - pure CSS -->
				<div class="crop-overlay" style:--crop-size="{cropSize}px">
					<div class="crop-frame"></div>
				</div>
			</div>
		</div>

		<!-- Slider Controls -->
		<div class="px-4 py-4 border-t border-neutral-700/50 space-y-5">
			<!-- Zoom slider -->
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

			<!-- Rotation slider -->
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
	/* Crop overlay using CSS - no canvas drawing needed */
	.crop-overlay {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}

	.crop-overlay::before {
		content: "";
		position: absolute;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		/* Cut out center square using clip-path */
		clip-path: polygon(
			/* Outer rectangle */ 0% 0%,
			0% 100%,
			100% 100%,
			100% 0%,
			0% 0%,
			/* Inner cutout (clockwise) */ calc(50% - var(--crop-size) / 2)
				calc(50% - var(--crop-size) / 2),
			calc(50% + var(--crop-size) / 2) calc(50% - var(--crop-size) / 2),
			calc(50% + var(--crop-size) / 2) calc(50% + var(--crop-size) / 2),
			calc(50% - var(--crop-size) / 2) calc(50% + var(--crop-size) / 2),
			calc(50% - var(--crop-size) / 2) calc(50% - var(--crop-size) / 2)
		);
	}

	.crop-frame {
		position: absolute;
		left: 50%;
		top: 50%;
		width: var(--crop-size);
		height: var(--crop-size);
		transform: translate(-50%, -50%);
		border: 2px solid rgba(99, 102, 241, 0.8);
		box-sizing: border-box;
	}

	/* Corner handles */
	.crop-frame::before,
	.crop-frame::after {
		content: "";
		position: absolute;
		width: 20px;
		height: 20px;
		border: 3px solid #6366f1;
	}

	.crop-frame::before {
		top: -2px;
		left: -2px;
		border-right: none;
		border-bottom: none;
	}

	.crop-frame::after {
		top: -2px;
		right: -2px;
		border-left: none;
		border-bottom: none;
	}

	/* Bottom corners via pseudo-elements on the overlay */
	.crop-overlay::after {
		content: "";
		position: absolute;
		left: 50%;
		top: 50%;
		width: var(--crop-size);
		height: var(--crop-size);
		transform: translate(-50%, -50%);
		pointer-events: none;
		/* Only show bottom corners */
		background:
			/* Bottom-left */
			linear-gradient(to right, #6366f1 3px, transparent 3px) 0 100%,
			linear-gradient(to top, #6366f1 3px, transparent 3px) 0 100%,
			/* Bottom-right */
				linear-gradient(to left, #6366f1 3px, transparent 3px) 100% 100%,
			linear-gradient(to top, #6366f1 3px, transparent 3px) 100% 100%;
		background-repeat: no-repeat;
		background-size: 20px 20px;
	}

	/* Custom slider styling */
	input[type="range"] {
		-webkit-appearance: none;
		appearance: none;
		background: transparent;
	}

	input[type="range"]::-webkit-slider-runnable-track {
		width: 100%;
		height: 8px;
		background: #1e1e2e;
		border-radius: 4px;
	}

	input[type="range"]::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 22px;
		height: 22px;
		background: #6366f1;
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
		background: #1e1e2e;
		border-radius: 4px;
	}

	input[type="range"]::-moz-range-thumb {
		width: 22px;
		height: 22px;
		background: #6366f1;
		border-radius: 50%;
		cursor: pointer;
		border: none;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
	}

	input[type="range"]::-moz-range-thumb:hover {
		box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
	}

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
