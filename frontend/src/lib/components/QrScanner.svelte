<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Html5Qrcode, Html5QrcodeScannerState } from 'html5-qrcode';

	interface Props {
		onScan: (decodedText: string) => void;
		onClose: () => void;
		onError?: (error: string) => void;
	}

	let { onScan, onClose, onError }: Props = $props();

	let scannerRef: HTMLDivElement;
	let html5QrCode: Html5Qrcode | null = null;
	let error = $state<string | null>(null);
	let isStarting = $state(true);
	let hasScanned = $state(false);
	let scanBoxSize = $state(250); // Will be calculated dynamically

	onMount(async () => {
		try {
			html5QrCode = new Html5Qrcode('qr-reader');

			const qrCodeSuccessCallback = (decodedText: string) => {
				if (hasScanned) return; // Prevent multiple scans
				hasScanned = true;
				
				// Stop scanning before calling callback
				stopScanner().then(() => {
					onScan(decodedText);
				});
			};

		const config = {
			fps: 15, // Increased for better detection
			qrbox: (viewfinderWidth: number, viewfinderHeight: number) => {
				// Make a square that's 50% of the smaller dimension (tighter focus for small QR codes)
				const size = Math.floor(Math.min(viewfinderWidth, viewfinderHeight) * 0.5);
				scanBoxSize = size; // Update for visual overlay
				return { width: size, height: size };
			},
			aspectRatio: 1.0,
			disableFlip: false,
			// Video constraints for back camera with autofocus and high resolution
			videoConstraints: {
				facingMode: { exact: 'environment' },
				focusMode: 'continuous',
				width: { ideal: 1920 },
				height: { ideal: 1080 }
			}
		};

		await html5QrCode.start(
			{ facingMode: 'environment' },
			config,
			qrCodeSuccessCallback,
			() => {} // Ignore QR not found errors
		);

		// Apply 2x zoom for better small QR code detection
		try {
			const capabilities = html5QrCode.getRunningTrackCameraCapabilities();
			const zoomFeature = capabilities.zoomFeature();
			if (zoomFeature.isSupported()) {
				const maxZoom = zoomFeature.max();
				const targetZoom = Math.min(maxZoom, 2.0); // 2x zoom or max available
				await zoomFeature.apply(targetZoom);
				console.log(`Applied ${targetZoom}x zoom for QR scanning`);
			}
		} catch (zoomErr) {
			console.warn('Zoom not supported on this device:', zoomErr);
		}

		isStarting = false;
		} catch (err) {
			console.error('QR Scanner error:', err);
			isStarting = false;
			
			if (err instanceof Error) {
				if (err.message.includes('Permission') || err.message.includes('NotAllowed')) {
					error = 'Camera permission denied. Please allow camera access and try again.';
				} else if (err.message.includes('NotFound') || err.message.includes('DevicesNotFound')) {
					error = 'No camera found on this device.';
				} else if (err.message.includes('NotSupported') || err.message.includes('NotReadable')) {
					error = 'Camera not supported or in use by another app.';
				} else {
					error = `Camera error: ${err.message}`;
				}
			} else {
				error = 'Failed to start camera. Please try again.';
			}
			
			onError?.(error);
		}
	});

	async function stopScanner() {
		if (html5QrCode) {
			try {
				const state = html5QrCode.getState();
				if (state === Html5QrcodeScannerState.SCANNING || state === Html5QrcodeScannerState.PAUSED) {
					await html5QrCode.stop();
				}
			} catch (err) {
				console.warn('Error stopping scanner:', err);
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
</script>

<!-- Full-screen modal overlay -->
<div class="fixed inset-0 z-[100] bg-black flex flex-col">
	<!-- Header -->
	<div class="flex items-center justify-between p-4 bg-black/80">
		<h2 class="text-white font-semibold">Scan Location QR Code</h2>
		<button
			type="button"
			onclick={handleClose}
			class="p-2 text-white/70 hover:text-white transition-colors"
			aria-label="Close scanner"
		>
			<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
				<path d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	</div>

	<!-- Scanner area -->
	<div class="flex-1 flex items-center justify-center p-4">
		{#if error}
			<div class="text-center p-6 max-w-sm">
				<div class="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
					<svg class="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
						<path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
				</div>
				<p class="text-white/80 mb-4">{error}</p>
				<button
					type="button"
					onclick={handleClose}
					class="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
				>
					Close
				</button>
			</div>
		{:else}
			<div class="relative">
				<!-- QR Reader container -->
				<div 
					id="qr-reader" 
					bind:this={scannerRef}
					class="rounded-xl overflow-hidden bg-black"
					style="width: min(90vw, 400px); height: min(90vw, 400px);"
				></div>

				<!-- Scanning overlay -->
				{#if isStarting}
					<div class="absolute inset-0 flex items-center justify-center bg-black/50 rounded-xl">
						<div class="text-center">
							<div class="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
							<p class="text-white/80 text-sm">Starting camera...</p>
						</div>
					</div>
				{/if}

				<!-- Scanning frame corners (visual aid) - dynamically sized -->
				{#if !isStarting}
					<div class="absolute inset-0 pointer-events-none flex items-center justify-center">
						<div class="relative" style="width: {scanBoxSize}px; height: {scanBoxSize}px;">
							<!-- Top left corner -->
							<div class="absolute top-0 left-0 w-8 h-8 border-t-3 border-l-3 border-primary rounded-tl-lg"></div>
							<!-- Top right corner -->
							<div class="absolute top-0 right-0 w-8 h-8 border-t-3 border-r-3 border-primary rounded-tr-lg"></div>
							<!-- Bottom left corner -->
							<div class="absolute bottom-0 left-0 w-8 h-8 border-b-3 border-l-3 border-primary rounded-bl-lg"></div>
							<!-- Bottom right corner -->
							<div class="absolute bottom-0 right-0 w-8 h-8 border-b-3 border-r-3 border-primary rounded-br-lg"></div>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Footer with instructions -->
	<div class="p-4 bg-black/80 text-center">
		<p class="text-white/60 text-sm">
			Point your camera at a Homebox location QR code
		</p>
	</div>
</div>

<style>
	/* Override html5-qrcode default styles */
	:global(#qr-reader video) {
		border-radius: 0.75rem;
		object-fit: cover;
	}
	
	:global(#qr-reader__scan_region) {
		min-height: auto !important;
	}
	
	/* Hide the library's internal scan region border/image */
	:global(#qr-reader__scan_region > img) {
		display: none !important;
	}
	
	/* Hide the library's internal scan region border elements */
	:global(#qr-reader__scan_region > div) {
		border: none !important;
		outline: none !important;
		box-shadow: none !important;
	}
	
	/* Hide any SVG borders the library might create */
	:global(#qr-reader__scan_region svg) {
		display: none !important;
	}
	
	/* Ensure video fills container properly */
	:global(#qr-reader video) {
		width: 100% !important;
		height: 100% !important;
	}
	
	:global(#qr-reader__dashboard) {
		display: none !important;
	}
	
	:global(#qr-reader__dashboard_section) {
		display: none !important;
	}
	
	:global(#qr-reader__dashboard_section_swaplink) {
		display: none !important;
	}

	/* Custom border widths for the corners */
	.border-t-3 {
		border-top-width: 3px;
	}
	.border-b-3 {
		border-bottom-width: 3px;
	}
	.border-l-3 {
		border-left-width: 3px;
	}
	.border-r-3 {
		border-right-width: 3px;
	}
</style>
