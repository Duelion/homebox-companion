<script lang="ts">
	import { onMount } from 'svelte';
	import Button from './Button.svelte';

	interface Props {
		images: { file: File; dataUrl: string }[];
		currentThumbnail?: string;
		onSave: (dataUrl: string) => void;
		onClose: () => void;
	}

	let { images, currentThumbnail, onSave, onClose }: Props = $props();

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

	// Crop area (square, centered)
	const CROP_SIZE = 280;
	let cropCenterX = 0;
	let cropCenterY = 0;

	// Touch/mouse state
	let isDragging = false;
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

	onMount(() => {
		ctx = canvas.getContext('2d');
		cropCenterX = canvas.width / 2;
		cropCenterY = canvas.height / 2;
		loadImage(selectedImageIndex);
	});

	function loadImage(index: number) {
		if (index < 0 || index >= images.length) return;
		
		const img = new Image();
		img.onload = () => {
			loadedImage = img;
			resetTransform();
			render();
		};
		img.src = images[index].dataUrl;
		selectedImageIndex = index;
	}

	function resetTransform() {
		if (!loadedImage) return;
		
		// Calculate minimum scale based on width only
		// This ensures the image fills the crop area horizontally
		// For portrait images, the top/bottom will extend beyond the crop area
		minScale = CROP_SIZE / loadedImage.width;
		
		// Start at minimum scale (image width matches crop width)
		scale = minScale;
		rotation = 0;
		offsetX = 0;
		offsetY = 0;
		render();
	}

	function render() {
		if (!ctx || !loadedImage) return;

		const w = canvas.width;
		const h = canvas.height;

		// Clear canvas
		ctx.fillStyle = '#1a1a2e';
		ctx.fillRect(0, 0, w, h);

		// Save context state
		ctx.save();

		// Transform order for rotation around crop center:
		// 1. Move to crop center
		ctx.translate(cropCenterX, cropCenterY);
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
			loadedImage.height
		);

		ctx.restore();

		// Draw dark overlay with transparent crop area
		ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
		ctx.fillRect(0, 0, w, cropCenterY - CROP_SIZE / 2);
		ctx.fillRect(0, cropCenterY + CROP_SIZE / 2, w, h - (cropCenterY + CROP_SIZE / 2));
		ctx.fillRect(0, cropCenterY - CROP_SIZE / 2, cropCenterX - CROP_SIZE / 2, CROP_SIZE);
		ctx.fillRect(cropCenterX + CROP_SIZE / 2, cropCenterY - CROP_SIZE / 2, w - (cropCenterX + CROP_SIZE / 2), CROP_SIZE);

		// Draw crop border
		ctx.strokeStyle = 'rgba(99, 102, 241, 0.8)';
		ctx.lineWidth = 2;
		ctx.strokeRect(cropCenterX - CROP_SIZE / 2, cropCenterY - CROP_SIZE / 2, CROP_SIZE, CROP_SIZE);

		// Draw corner handles
		const handleSize = 20;
		ctx.strokeStyle = '#6366f1';
		ctx.lineWidth = 3;
		
		// Top-left
		ctx.beginPath();
		ctx.moveTo(cropCenterX - CROP_SIZE / 2, cropCenterY - CROP_SIZE / 2 + handleSize);
		ctx.lineTo(cropCenterX - CROP_SIZE / 2, cropCenterY - CROP_SIZE / 2);
		ctx.lineTo(cropCenterX - CROP_SIZE / 2 + handleSize, cropCenterY - CROP_SIZE / 2);
		ctx.stroke();
		
		// Top-right
		ctx.beginPath();
		ctx.moveTo(cropCenterX + CROP_SIZE / 2 - handleSize, cropCenterY - CROP_SIZE / 2);
		ctx.lineTo(cropCenterX + CROP_SIZE / 2, cropCenterY - CROP_SIZE / 2);
		ctx.lineTo(cropCenterX + CROP_SIZE / 2, cropCenterY - CROP_SIZE / 2 + handleSize);
		ctx.stroke();
		
		// Bottom-left
		ctx.beginPath();
		ctx.moveTo(cropCenterX - CROP_SIZE / 2, cropCenterY + CROP_SIZE / 2 - handleSize);
		ctx.lineTo(cropCenterX - CROP_SIZE / 2, cropCenterY + CROP_SIZE / 2);
		ctx.lineTo(cropCenterX - CROP_SIZE / 2 + handleSize, cropCenterY + CROP_SIZE / 2);
		ctx.stroke();
		
		// Bottom-right
		ctx.beginPath();
		ctx.moveTo(cropCenterX + CROP_SIZE / 2 - handleSize, cropCenterY + CROP_SIZE / 2);
		ctx.lineTo(cropCenterX + CROP_SIZE / 2, cropCenterY + CROP_SIZE / 2);
		ctx.lineTo(cropCenterX + CROP_SIZE / 2, cropCenterY + CROP_SIZE / 2 - handleSize);
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
		const rad = (-rotation * Math.PI) / 180;
		const rotatedDx = dx * Math.cos(rad) - dy * Math.sin(rad);
		const rotatedDy = dx * Math.sin(rad) + dy * Math.cos(rad);
		
		offsetX += rotatedDx;
		offsetY += rotatedDy;
		
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
			
			// Convert to rotated space
			const rad = (-rotation * Math.PI) / 180;
			const rotatedDx = dx * Math.cos(rad) - dy * Math.sin(rad);
			const rotatedDy = dx * Math.sin(rad) + dy * Math.cos(rad);
			
			offsetX += rotatedDx;
			offsetY += rotatedDy;
			
			lastX = e.touches[0].clientX;
			lastY = e.touches[0].clientY;
		} else if (e.touches.length === 2) {
			// Pinch zoom
			const newDistance = getTouchDistance(e.touches);
			const scaleChange = newDistance / lastTouchDistance;
			scale = Math.max(minScale, Math.min(MAX_SCALE, scale * scaleChange));
			lastTouchDistance = newDistance;
			
			// Two-finger rotation
			const newAngle = getTouchAngle(e.touches);
			const angleDelta = (newAngle - lastTouchAngle) * (180 / Math.PI);
			rotation = Math.max(MIN_ROTATION, Math.min(MAX_ROTATION, rotation + angleDelta));
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
		const outputCanvas = document.createElement('canvas');
		outputCanvas.width = outputSize;
		outputCanvas.height = outputSize;
		const outputCtx = outputCanvas.getContext('2d');
		
		if (!outputCtx) return;

		const outputScale = outputSize / CROP_SIZE;
		
		outputCtx.fillStyle = '#1a1a2e';
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
			loadedImage.height
		);

		const dataUrl = outputCanvas.toDataURL('image/jpeg', 0.9);
		onSave(dataUrl);
	}
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
	<div class="bg-surface rounded-2xl border border-border max-w-lg w-full max-h-[90vh] overflow-hidden flex flex-col">
		<!-- Header -->
		<div class="flex items-center justify-between p-4 border-b border-border">
			<h3 class="text-lg font-semibold text-text">Edit Thumbnail</h3>
			<button
				type="button"
				class="p-2 text-text-muted hover:text-text transition-colors"
				onclick={onClose}
				aria-label="Close"
			>
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<line x1="18" y1="6" x2="6" y2="18" />
					<line x1="6" y1="6" x2="18" y2="18" />
				</svg>
			</button>
		</div>

		<!-- Image selector -->
		{#if images.length > 1}
			<div class="px-4 py-2 border-b border-border/50">
				<span class="text-xs text-text-muted mb-2 block">Select source image:</span>
				<div class="flex gap-2 overflow-x-auto pb-2">
					{#each images as img, index}
						<button
							type="button"
							class="w-12 h-12 rounded-lg overflow-hidden flex-shrink-0 border-2 transition-colors {selectedImageIndex === index ? 'border-primary' : 'border-transparent hover:border-border'}"
							onclick={() => loadImage(index)}
						>
							<img src={img.dataUrl} alt="Option {index + 1}" class="w-full h-full object-cover" />
						</button>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Canvas area -->
		<div class="flex-1 flex items-center justify-center p-4 overflow-hidden touch-none">
			<canvas
				bind:this={canvas}
				width="360"
				height="360"
				class="rounded-lg cursor-move"
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
		<div class="px-4 py-3 border-t border-border/50 space-y-4">
			<!-- Zoom slider -->
			<div>
				<div class="flex items-center justify-between mb-1">
					<label for="zoomSlider" class="text-xs text-text-muted flex items-center gap-1">
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<circle cx="11" cy="11" r="8" />
							<path d="m21 21-4.35-4.35" />
						</svg>
						Zoom
					</label>
					<span class="text-xs text-text-muted">{zoomPercent}%</span>
				</div>
				<input
					id="zoomSlider"
					type="range"
					min="0"
					max="1"
					step="0.005"
					value={zoomSliderValue}
					oninput={handleZoomSlider}
					class="w-full h-2 bg-surface-elevated rounded-lg appearance-none cursor-pointer accent-primary"
				/>
			</div>

			<!-- Rotation slider -->
			<div>
				<div class="flex items-center justify-between mb-1">
					<label for="rotationSlider" class="text-xs text-text-muted flex items-center gap-1">
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path d="M21.5 2v6h-6" />
							<path d="M21.5 8a10 10 0 1 0-3 7" />
						</svg>
						Rotation
					</label>
					<span class="text-xs text-text-muted">{Math.round(rotation)}°</span>
				</div>
				<div class="flex items-center gap-2">
					<button
						type="button"
						class="p-1.5 rounded bg-surface-elevated text-text-muted hover:text-text transition-colors"
						onclick={rotateLeft90}
						aria-label="Rotate 90° left"
						title="-90°"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path d="M2.5 2v6h6" />
							<path d="M2.5 8a10 10 0 1 1 3 7" />
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
						class="flex-1 h-2 bg-surface-elevated rounded-lg appearance-none cursor-pointer accent-primary"
					/>
					<button
						type="button"
						class="p-1.5 rounded bg-surface-elevated text-text-muted hover:text-text transition-colors"
						onclick={rotateRight90}
						aria-label="Rotate 90° right"
						title="+90°"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path d="M21.5 2v6h-6" />
							<path d="M21.5 8a10 10 0 1 0-3 7" />
						</svg>
					</button>
				</div>
			</div>

			<!-- Reset button -->
			<div class="flex justify-center">
				<button
					type="button"
					class="px-4 py-1.5 rounded-lg bg-surface-elevated text-text-muted hover:text-text text-sm transition-colors"
					onclick={resetTransform}
				>
					Reset
				</button>
			</div>

			<p class="text-xs text-text-dim text-center">
				Drag to pan • Scroll to zoom • On mobile: pinch to zoom, two fingers to rotate
			</p>
		</div>

		<!-- Actions -->
		<div class="flex gap-3 p-4 border-t border-border">
			<Button variant="secondary" onclick={onClose}>
				Cancel
			</Button>
			<Button variant="primary" onclick={saveCrop}>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<polyline points="20 6 9 17 4 12" />
				</svg>
				<span>Save Thumbnail</span>
			</Button>
		</div>
	</div>
</div>

<style>
	/* Custom slider styling */
	input[type="range"] {
		-webkit-appearance: none;
		appearance: none;
		background: transparent;
	}

	input[type="range"]::-webkit-slider-runnable-track {
		width: 100%;
		height: 8px;
		background: #2a2a3e;
		border-radius: 4px;
	}

	input[type="range"]::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 18px;
		height: 18px;
		background: #6366f1;
		border-radius: 50%;
		cursor: pointer;
		margin-top: -5px;
		transition: transform 0.1s;
	}

	input[type="range"]::-webkit-slider-thumb:hover {
		transform: scale(1.1);
	}

	input[type="range"]::-moz-range-track {
		width: 100%;
		height: 8px;
		background: #2a2a3e;
		border-radius: 4px;
	}

	input[type="range"]::-moz-range-thumb {
		width: 18px;
		height: 18px;
		background: #6366f1;
		border-radius: 50%;
		cursor: pointer;
		border: none;
	}
</style>
