<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import QrScanner from 'qr-scanner';
	import heic2any from 'heic2any';
	import { qrLogger as log } from '$lib/utils/logger';

	interface Props {
		onScan: (decodedText: string) => void;
		onClose: () => void;
		onError?: (error: string) => void;
	}

	let { onScan, onClose, onError }: Props = $props();

	let videoElement = $state<HTMLVideoElement>();
	let fileInput: HTMLInputElement;
	let qrScanner: QrScanner | null = null;
	let error = $state<string | null>(null);
	let isStarting = $state(true);
	let hasScanned = $state(false);
	let cameraFailed = $state(false);
	let isInsecureContext = $state(false);
	let isProcessingFile = $state(false);

	async function startCamera() {
		error = null;
		isStarting = true;
		cameraFailed = false;
		hasScanned = false;

		try {
			// Check for secure context - camera APIs require HTTPS
			if (!window.isSecureContext) {
				isInsecureContext = true;
				error = 'Camera requires HTTPS. Use the upload option below.';
				isStarting = false;
				cameraFailed = true;
				onError?.(error);
				return;
			}

			if (!videoElement) {
				error = 'Video element not ready. Please try again.';
				isStarting = false;
				cameraFailed = true;
				onError?.(error);
				return;
			}

			qrScanner = new QrScanner(
				videoElement,
				(result: QrScanner.ScanResult) => {
					if (hasScanned) return; // Prevent multiple scans
					hasScanned = true;

					// Stop scanning before calling callback
					stopScanner().then(() => {
						onScan(result.data);
					});
				},
				{
					preferredCamera: 'environment',
					highlightScanRegion: true,
					highlightCodeOutline: true,
					returnDetailedScanResult: true,
				}
			);

			await qrScanner.start();
			isStarting = false;
		} catch (err) {
			log.error('Camera initialization failed:', err);
			isStarting = false;
			cameraFailed = true;

			if (err instanceof Error) {
				const msg = err.message || '';
				const name = err.name || '';

				if (
					name === 'NotAllowedError' ||
					msg.includes('Permission') ||
					msg.includes('NotAllowed')
				) {
					error =
						'Camera permission denied. Check your browser settings, or use the upload option below.';
				} else if (
					name === 'NotFoundError' ||
					msg.includes('NotFound') ||
					msg.includes('DevicesNotFound')
				) {
					error = 'No camera detected. Use the upload option below.';
				} else if (name === 'NotReadableError' || msg.includes('NotReadable')) {
					error =
						'Camera is in use by another app. Close other apps or use the upload option below.';
				} else if (name === 'OverconstrainedError' || msg.includes('Overconstrained')) {
					error = 'Camera settings not supported. Use the upload option below.';
				} else if (name === 'NotSupportedError' || msg.includes('NotSupported')) {
					error = 'Camera not supported in this browser. Use the upload option below.';
				} else {
					error = `Camera error: ${msg || 'Unknown error'}. Use the upload option below.`;
				}
			} else {
				error = 'Failed to start camera. Use the upload option below.';
			}

			onError?.(error);
		}
	}

	onMount(() => {
		startCamera();
	});

	async function stopScanner() {
		if (qrScanner) {
			try {
				qrScanner.stop();
				qrScanner.destroy();
				qrScanner = null;
			} catch (err) {
				log.debug('Error stopping scanner:', err);
			}
		}
	}

	onDestroy(() => {
		stopScanner();
	});

	function handleClose() {
		stopScanner().then(() => {
			onClose();
		});
	}

	async function handleRetryCamera() {
		await stopScanner();
		startCamera();
	}

	function triggerFileUpload() {
		fileInput?.click();
	}

	// Convert HEIC images to JPEG (iOS may send HEIC format)
	async function convertHeicIfNeeded(file: File): Promise<Blob> {
		const isHeic =
			file.type === 'image/heic' ||
			file.type === 'image/heif' ||
			file.name.toLowerCase().endsWith('.heic') ||
			file.name.toLowerCase().endsWith('.heif');

		if (isHeic) {
			const blob = await heic2any({
				blob: file,
				toType: 'image/jpeg',
				quality: 0.92,
			});
			return Array.isArray(blob) ? blob[0] : blob;
		}
		return file;
	}

	// Scale down large images - qr-scanner fails on images > ~2MP
	const MAX_IMAGE_DIMENSION = 1280;

	async function scaleDownImage(blob: Blob): Promise<Blob> {
		return new Promise((resolve, reject) => {
			const img = new Image();
			const url = URL.createObjectURL(blob);

			img.onload = () => {
				let width = img.naturalWidth;
				let height = img.naturalHeight;

				// Scale down if image is too large
				if (width > MAX_IMAGE_DIMENSION || height > MAX_IMAGE_DIMENSION) {
					const scale = MAX_IMAGE_DIMENSION / Math.max(width, height);
					width = Math.round(width * scale);
					height = Math.round(height * scale);
				}

				const canvas = document.createElement('canvas');
				canvas.width = width;
				canvas.height = height;
				const ctx = canvas.getContext('2d');
				if (!ctx) {
					URL.revokeObjectURL(url);
					reject(new Error('Canvas context not available'));
					return;
				}

				ctx.drawImage(img, 0, 0, width, height);

				canvas.toBlob(
					(resultBlob) => {
						URL.revokeObjectURL(url);
						if (resultBlob) {
							resolve(resultBlob);
						} else {
							reject(new Error('Canvas conversion failed'));
						}
					},
					'image/jpeg',
					0.92
				);
			};
			img.onerror = () => {
				URL.revokeObjectURL(url);
				reject(new Error('Failed to load image'));
			};
			img.src = url;
		});
	}

	async function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		isProcessingFile = true;
		error = null;

		try {
			// Convert HEIC to JPEG if needed (iOS camera photos)
			const converted = await convertHeicIfNeeded(file);

			// Scale down image (qr-scanner fails on large images)
			const scaled = await scaleDownImage(converted);

			// Scan for QR code
			const result = await QrScanner.scanImage(scaled, {
				returnDetailedScanResult: true,
			});

			hasScanned = true;
			await stopScanner();
			onScan(result.data);
		} catch (err) {
			if (err instanceof Error && err.message.includes('No QR code found')) {
				error = 'No QR code found in image. Try a clearer photo.';
			} else {
				error = 'Could not read QR code from image. Try again.';
			}
			onError?.(error);
		} finally {
			isProcessingFile = false;
			// Reset file input so the same file can be selected again
			input.value = '';
		}
	}
</script>

<!-- Hidden file input for camera capture fallback -->
<input
	bind:this={fileInput}
	type="file"
	accept="image/*"
	capture="environment"
	onchange={handleFileSelect}
	class="hidden"
/>

<!-- Full-screen modal overlay -->
<div class="z-overlay fixed inset-0 flex flex-col bg-neutral-950">
	<!-- Header -->
	<div class="flex items-center justify-between bg-neutral-950/80 p-4">
		<h2 class="font-semibold text-neutral-100">Scan Location QR Code</h2>
		<button
			type="button"
			onclick={handleClose}
			class="p-2 text-neutral-400 transition-colors hover:text-neutral-100"
			aria-label="Close scanner"
		>
			<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	</div>

	<!-- Scanner area -->
	<div class="flex flex-1 items-center justify-center p-4">
		{#if cameraFailed}
			<div class="max-w-sm p-6 text-center">
				<div
					class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-500/20"
				>
					<svg
						class="h-8 w-8 text-amber-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path
							d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
						/>
					</svg>
				</div>
				<p class="mb-6 text-neutral-300">{error}</p>

				<!-- Action buttons -->
				<div class="flex flex-col gap-3">
					<!-- File upload button (always available as fallback) -->
					<button
						type="button"
						onclick={triggerFileUpload}
						disabled={isProcessingFile}
						class="bg-primary-600 hover:bg-primary-500 flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-neutral-100 transition-colors disabled:opacity-50"
					>
						{#if isProcessingFile}
							<div
								class="h-5 w-5 animate-spin rounded-full border-2 border-neutral-100 border-t-transparent"
							></div>
							<span>Processing...</span>
						{:else}
							<svg
								class="h-5 w-5"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<path
									d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
								/>
								<path d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
							</svg>
							<span>Take Photo</span>
						{/if}
					</button>

					<!-- Retry camera button (not shown for HTTPS issues) -->
					{#if !isInsecureContext}
						<button
							type="button"
							onclick={handleRetryCamera}
							class="rounded-lg bg-neutral-800 px-4 py-2 text-neutral-100 transition-colors hover:bg-neutral-700"
						>
							Try Camera Again
						</button>
					{/if}

					<button
						type="button"
						onclick={handleClose}
						class="px-4 py-2 text-neutral-500 transition-colors hover:text-neutral-100"
					>
						Cancel
					</button>
				</div>
			</div>
		{:else}
			<div class="relative">
				<!-- Video element for QR scanner -->
				<video
					bind:this={videoElement}
					class="rounded-xl bg-neutral-950"
					style="width: min(90vw, 400px); height: min(90vw, 400px); object-fit: cover;"
				>
					<track kind="captions" label="No captions available" />
				</video>

				<!-- Scanning overlay -->
				{#if isStarting}
					<div
						class="absolute inset-0 flex items-center justify-center rounded-xl bg-neutral-950/50"
					>
						<div class="text-center">
							<div
								class="mx-auto mb-2 h-8 w-8 animate-spin rounded-full border-2 border-neutral-100 border-t-transparent"
							></div>
							<p class="text-body-sm text-neutral-300">Starting camera...</p>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Footer with instructions -->
	<div class="bg-neutral-950/80 p-4 text-center">
		{#if cameraFailed}
			<p class="text-body-sm text-neutral-500">Take a photo of the QR code</p>
		{:else}
			<p class="text-body-sm text-neutral-500">Point your camera at a Homebox location QR code</p>
		{/if}
	</div>
</div>

<style>
	/* Style the qr-scanner overlay - uses CSS custom property for primary color */
	:global(.scan-region-highlight) {
		border: 2px solid theme('colors.primary.500') !important;
		border-radius: 0.5rem;
	}

	:global(.scan-region-highlight-svg) {
		stroke: theme('colors.primary.500') !important;
	}

	:global(.code-outline-highlight) {
		stroke: theme('colors.primary.500') !important;
		stroke-width: 3px;
	}
</style>
